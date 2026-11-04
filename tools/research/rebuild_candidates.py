#!/usr/bin/env python3
"""Rebuild 2027 municipal candidate records from fetched official party sources.
Requires: Python 3.10+, pdfplumber, lxml. Raw sources live only in TemporaryDirectory.
"""
import argparse
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

SOURCES = {
    'ldp2027.pdf': 'https://election-special.tokyo-jimin.jp/wp-content/uploads/2026/10/%E8%B3%87%E6%96%99%EF%BC%9AR9%E7%B5%B1%E4%B8%80%E5%9C%B0%E6%96%B9%E9%81%B8_%E7%AC%AC1%E6%AC%A1%E5%85%AC%E8%AA%8D%E6%8E%A8%E8%96%A6%E6%B1%BA%E5%AE%9A%E8%80%85%E4%B8%80%E8%A6%A720261013.pdf',
    'ishin2027.html': 'https://o-ishin.jp/election/candidate/2027kounin/',
    'cdp2027.html': 'https://cdp-japan.jp/election/unified_local_elections/2027/',
    'dpfp2027.html': 'https://r9-toitsu.new-kokumin.tokyo/candidates.html',
    'komei2027.html': 'https://komei-fukuoka.jp/news/xz4n74n_u/',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True, help='national.json with municipalities[].code/name/pref')
    parser.add_argument('--output', type=Path, required=True, help='New output JSON; existing file will be replaced only after successful extraction')
    parser.add_argument('--as-of', default=datetime.date.today().isoformat())
    args = parser.parse_args()
    args.registry = args.registry.resolve()
    args.output = args.output.resolve()
    root = Path(__file__).resolve().parent / 'candidate_sources'
    with tempfile.TemporaryDirectory(prefix='municipal-candidates-') as tmp:
        work = Path(tmp)
        output = work / 'candidates.json'
        env = dict(os.environ, CANDIDATE_OUTPUT=str(output), MUNICIPALITY_REGISTRY=str(args.registry), CANDIDATE_WORKDIR=str(work), CANDIDATE_AS_OF=args.as_of)

        def fetch(item):
            name, url = item
            req = urllib.request.Request(url, headers={'User-Agent': 'MunicipalCandidateResearch/1.0 (public-source verification)'})
            with urllib.request.urlopen(req, timeout=45) as response:
                payload = response.read()
            (work / name).write_bytes(payload)
            return name, len(payload)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for name, size in executor.map(fetch, SOURCES.items()):
                print(f'Fetched {name}: {size} bytes', flush=True)
        for script in ['build_ldp_tokyo.py', 'add_ishin.py', 'add_cdp.py', 'add_dpfp_tokyo.py', 'add_komei_fukuoka.py']:
            subprocess.run([sys.executable, str(root / script)], env=env, check=True, cwd=work)
        records = json.loads(output.read_text())
        # Four manually cross-checked records retain the historical source dates.
        # These records are not a new live confirmation; review their cited documents separately.
        records.extend(json.loads((root / 'verified_bunkyo_additions.json').read_text()))
        registry = json.loads(args.registry.read_text())['municipalities']
        valid_codes = {m['code'] for m in registry}
        seen = set()
        for record in records:
            assert record['municipalityCode'] in valid_codes, record
            assert record['name'] and record['candidate']['sources'], record
            key = (record['municipalityCode'], record['name'])
            assert key not in seen, f'Duplicate candidate: {key}'
            seen.add(key)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
        print(f'Saved {len(records)} records to {args.output}', flush=True)


if __name__ == '__main__':
    main()
