#!/usr/bin/env python3
"""Validate and serialize reviewed short summaries; does not reproduce web articles."""
import argparse
import copy
import datetime
import json
import os
from pathlib import Path
import re
import settings as cfg

RECORD_KEYS = {'municipalityCode', 'name', 'snapshotAsOf', 'profileURL', 'sourceURL', 'sourceTitle', 'findings'}
FACT_KEYS = {'category', 'title', 'summary', 'period', 'url', 'sourceType', 'asOf', 'checkedAt', 'evidence'}
EVIDENCE_KEYS = {'matchedName', 'sourceName', 'sectionHeading', 'selector', 'rule', 'aliasEvidenceURL', 'nameMatchNote'}
VERIFIED_ALIASES = {('13121', '近藤弥生'): '近藤やよい', ('24202', '森智広'): '森智広（サイト表記：森ともひろ）'}

def build(paths):
    result, seen = [], set()
    for path in paths:
        for original in json.loads(path.read_text(encoding='utf-8')):
            row = {k: copy.deepcopy(v) for k, v in original.items() if k in RECORD_KEYS}
            key = (row['municipalityCode'], row['name'])
            if key in seen:
                raise ValueError(f'Duplicate reviewed person: {key}')
            seen.add(key)
            facts = []
            for original_fact in row.get('findings', []):
                fact = {k: v for k, v in original_fact.items() if k in FACT_KEYS}
                evidence = {k: v for k, v in fact.get('evidence', {}).items() if k in EVIDENCE_KEYS}
                if evidence.get('matchedName') == VERIFIED_ALIASES.get(key):
                    evidence['sourceName'] = evidence['matchedName']
                    evidence['matchedName'] = row['name']
                if evidence.get('matchedName') != row['name']:
                    raise ValueError(f'Unreviewed name mismatch: {key}')
                if re.search(r'生年月日|誕生日|家族構成|電話番号|ファクス番号|〒|住所[：:]', fact['summary']):
                    raise ValueError(f'Private information requires review: {key}')
                datetime.date.fromisoformat(fact['checkedAt'])
                fact['evidence'] = evidence
                facts.append(fact)
            row['findings'] = facts
            result.append(row)
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, action='append', help='Repeat for reviewed source JSON arrays')
    parser.add_argument('--output', type=Path, default=cfg.path('MAYORS_SUPPLEMENT_OUTPUT', cfg.WORK_DIR / 'reviewed-supplements.json'))
    args = parser.parse_args()
    paths = args.input or cfg.paths('MAYORS_SUPPLEMENT_INPUTS', [cfg.PACKAGE_DIR / 'reviewed-supplements.json'])
    records = build(paths)
    cfg.write_json(args.output, records)
    print(f'Validated {len(records)} reviewed people / {sum(len(r["findings"]) for r in records)} short facts')

if __name__ == '__main__':
    main()
