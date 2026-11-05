#!/usr/bin/env python3
"""Audit collected records and merge dated, same-person reviewed supplements."""
import argparse
import collections
import copy
import datetime
import importlib.util
import json
from pathlib import Path
import re
import urllib.parse
import settings as cfg

spec = importlib.util.spec_from_file_location('mayor_audit', cfg.PACKAGE_DIR / 'audit-mayors.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

def urlkey(url):
    u = urllib.parse.urlsplit(url)
    return (u.netloc.lower(), u.path.rstrip('/'), u.query)

def valid_date(value):
    try:
        datetime.date.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False

def finalize(collected, registry, supplements):
    expected = {(r['municipalityCode'], r['name']) for r in registry}
    if len(registry) != cfg.EXPECTED_COUNT or len(expected) != len(registry):
        raise ValueError('Registry count/unique identity check failed; review MAYORS_EXPECTED_COUNT')
    if len(collected) != len(registry):
        raise ValueError('Collected rows do not cover the full registry')
    if {(r['municipalityCode'], r['name']) for r in collected} != expected:
        raise ValueError('Collected identities differ from the registry')
    rows, auditstats = audit.audit(collected, registry=registry)
    bykey = {(r['municipalityCode'], r['name']): r for r in rows}
    merged, rejected, missing = [], [], []
    for path in supplements:
        if not path.exists():
            missing.append(str(path))
            continue
        for extra in json.loads(path.read_text(encoding='utf-8')):
            key = (extra['municipalityCode'], extra['name'])
            if key not in bykey:
                rejected.append({'file': path.name, 'code': key[0], 'name': key[1], 'reason': 'code+name mismatch'})
                continue
            row = bykey[key]
            facts = copy.deepcopy(extra.get('findings', []))
            if not facts:
                review = extra.get('enrichment', {})
                row['enrichment']['attempted'].extend(review.get('attempted', []))
                if not row['findings'] and review.get('status') in ('追加根拠未確認', '既存内容確認'):
                    row['enrichment']['status'] = '追加根拠未確認'
                    row['enrichment']['note'] = review.get('note', '補助調査でも追加の本人経歴を確認できなかった。')
                continue
            if any(f.get('evidence', {}).get('matchedName') != extra['name'] for f in facts):
                rejected.append({'file': path.name, 'code': key[0], 'name': key[1], 'reason': 'evidence name mismatch'})
                continue
            manual_urls = {urlkey(f['url']) for f in facts}
            unique = [f for f in row['findings'] if urlkey(f['url']) not in manual_urls]
            row['findings'] = facts + unique
            if extra.get('profileURL') or extra.get('sourceURL'):
                row['profileURL'] = extra.get('profileURL') or extra['sourceURL']
            row['enrichment']['status'] = '情報追加'
            row['enrichment']['note'] = '本人のcode+nameを完全一致で照合し、公式本文の補助手動調査を優先して統合。同一URL由来の通常抽出は置き換え、別の公式出典の事実は残した。掲載時点の経歴・役職であり、現在の継続や網羅性を意味しない。'
            for url in dict.fromkeys(f['url'] for f in facts):
                row['enrichment']['attempted'].append({'url': url, 'status': '200（公式Web本文を補助手動調査で照合）'})
            merged.append({'file': path.name, 'code': key[0], 'name': key[1], 'manualFindings': len(facts), 'distinctOtherSourceFindings': len(unique)})
    out = [bykey[(r['municipalityCode'], r['name'])] for r in registry]
    privacy = []
    for row, original in zip(out, registry):
        if row['snapshotAsOf'] != original['snapshotAsOf']:
            raise ValueError('snapshotAsOf changed')
        if not valid_date(row['enrichment']['checkedAt']) or not row['enrichment']['attempted']:
            raise ValueError('Missing/invalid inspection metadata')
        for fact in row['findings']:
            if not valid_date(fact.get('checkedAt')) or fact.get('evidence', {}).get('matchedName') != row['name']:
                raise ValueError('Invalid fact date or identity')
            if re.search(r'生年月日|誕生日|家族構成|電話番号|ファクス番号|〒|住所[：:]', fact['summary']):
                privacy.append({'code': row['municipalityCode'], 'name': row['name'], 'summary': fact['summary']})
            # The public artifact contains the short summaries and attribution only.
            fact.get('evidence', {}).pop('sourceFragment', None)
    if privacy:
        raise ValueError('Private-information review required: ' + json.dumps(privacy, ensure_ascii=False))
    report = {'checkedAt': cfg.CHECKED_AT, 'inputCount': len(registry), 'outputCount': len(out), 'sameCodeAndName': True,
              'peopleWithFindings': sum(bool(r['findings']) for r in out), 'findings': sum(len(r['findings']) for r in out),
              'statuses': dict(collections.Counter(r['enrichment']['status'] for r in out)),
              'categories': dict(collections.Counter(f['category'] for r in out for f in r['findings'])),
              'sourceTypes': dict(collections.Counter(f['sourceType'] for r in out for f in r['findings'])),
              'audit': auditstats, 'manualSupplementMerged': merged, 'rejectedSupplement': rejected,
              'missingSupplementFiles': missing, 'privacyReviewFlags': privacy}
    return out, report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=cfg.COLLECTED)
    parser.add_argument('--registry', type=Path, default=cfg.INPUT)
    parser.add_argument('--output', type=Path, default=cfg.OUTPUT)
    parser.add_argument('--supplement', type=Path, action='append')
    args = parser.parse_args()
    out, report = finalize(json.loads(args.input.read_text(encoding='utf-8')), json.loads(args.registry.read_text(encoding='utf-8')), args.supplement if args.supplement is not None else cfg.SUPPLEMENTS)
    cfg.write_json(args.output, out)
    cfg.write_json(cfg.REPORT, report)
    print(json.dumps({k: report[k] for k in ['inputCount', 'outputCount', 'peopleWithFindings', 'findings', 'statuses']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
