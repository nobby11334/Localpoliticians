#!/usr/bin/env python3
"""Build a fixed-person input registry from the repository's national directory."""
import argparse
import json
import os
from pathlib import Path
import settings as cfg

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--national', type=Path, default=cfg.path('MAYORS_NATIONAL_INPUT', Path.cwd() / 'data' / 'national.json'))
    parser.add_argument('--existing', type=Path, default=Path(os.environ['MAYORS_EXISTING_PEOPLE']) if os.environ.get('MAYORS_EXISTING_PEOPLE') else None)
    parser.add_argument('--output', type=Path, default=cfg.INPUT)
    args = parser.parse_args()
    directory = json.loads(args.national.read_text(encoding='utf-8'))
    existing = json.loads(args.existing.read_text(encoding='utf-8')) if args.existing else []
    if not isinstance(existing, list):
        raise ValueError('Existing reviewed people must be a JSON array')
    groups = {}
    for person in existing:
        key = (person['municipalityCode'], person['name'])
        groups.setdefault(key, []).append(person)
    out = []
    for city in directory['municipalities']:
        mayor = city.get('mayor') or {}
        if not mayor.get('name') or not city.get('officialURL'):
            raise ValueError('Missing mayor name/official URL: ' + city['code'])
        key = (city['code'], mayor['name'])
        out.append({'municipalityCode': city['code'], 'municipalityName': city['name'],
                    'prefecture': city['pref'], 'name': mayor['name'],
                    'snapshotAsOf': mayor['asOf'], 'snapshotSource': mayor.get('sourceURL'),
                    'officialURL': city['officialURL'], 'existingPeople': groups.get(key, [])})
    if len(out) != cfg.EXPECTED_COUNT or len({r['municipalityCode'] for r in out}) != len(out):
        raise ValueError('Unexpected registry count/duplicate municipality code')
    cfg.write_json(args.output, out)
    print(f'Prepared {len(out)} fixed-person rows: {args.output}')

if __name__ == '__main__':
    main()
