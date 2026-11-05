"""Regenerate the 30 reviewed mayor supplements from short factual JSON, without HTTP.
The stored checkedAt dates are historical review dates and are never advanced here.
"""
import copy
import json
import re
from collections import Counter
import research_config as cfg


def main():
    targets = json.loads(cfg.MAYORS_INPUT_PATH.read_text(encoding='utf-8'))
    facts = json.loads(cfg.MAYORS_FACTS_PATH.read_text(encoding='utf-8'))
    indexed = {(p['municipalityCode'], p['name']): p for p in facts}
    if len(indexed) != len(facts):
        raise ValueError('Reviewed facts contain duplicate municipality/name keys')
    result = []
    seen = set()
    for target in targets:
        key = (target['municipalityCode'], target['name'])
        if key in seen:
            raise ValueError(f'Duplicate target: {key}')
        seen.add(key)
        source = indexed.get(key)
        if source is None:
            result.append({
                'municipalityCode': key[0], 'name': key[1],
                'snapshotAsOf': target.get('snapshotAsOf', '不明'),
                'findings': [],
                'enrichment': {
                    'checkedAt': '不明', 'status': '追加根拠未確認', 'attempted': [],
                    'note': '確認済みfact JSONに該当人物なし。Web調査はこの再生成処理では行わない。'
                }
            })
            continue
        record = copy.deepcopy(source)
        if target.get('snapshotAsOf') != record['snapshotAsOf']:
            raise ValueError(f'Snapshot mismatch: {key}; review the target before joining')
        if len(record['findings']) > 20:
            raise ValueError(f'More than 20 reviewed facts: {key}')
        for finding in record['findings']:
            if finding['evidence']['matchedName'] != record['name']:
                raise ValueError(f'Evidence identity mismatch: {key}')
            if re.search(r'〒|生年月日|家族|妻(?!女子)|夫婦|\d{2,4}-\d{2,4}-\d{4}', finding['summary']):
                raise ValueError(f'Unexpected private details: {key}')
        result.append(record)
    cfg.prepare_output()
    cfg.MAYORS_OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'people': len(result), 'findings': sum(len(p['findings']) for p in result),
        'statuses': dict(Counter(p['enrichment']['status'] for p in result)),
        'output': str(cfg.MAYORS_OUTPUT_PATH),
        'reviewDatesPreserved': True,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
