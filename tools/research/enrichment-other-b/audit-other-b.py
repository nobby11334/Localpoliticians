"""Offline audit and conservative reparse of pages actually attempted for each person."""
import importlib.util, json, re, hashlib, collections
from pathlib import Path
import research_config as cfg
cfg.prepare_output()
R = Path(__file__).resolve().parent
sp = importlib.util.spec_from_file_location('research_b', R / 'research-other-b.py')
m = importlib.util.module_from_spec(sp)
sp.loader.exec_module(m)
from functools import lru_cache

@lru_cache(maxsize=2048)
def cached_soup(path):
    return m.soupof(Path(path).read_bytes())
P = cfg.RESULT_PATH
A = json.loads(P.read_text(encoding='utf-8'))
raw = {p['id']: p for p in m.PEOPLE}
report = {'removed': [], 'cacheReparsed': 0}

def valid(f, p):
    v = f['summary']
    if f['category'] != 'policy' and re.search('/ (?:政策|基本政策|重点政策|任期中に取り組みたいこと)$', f.get('evidence', {}).get('selector', '')):
        return False
    if '�' in v or '票産' in v:
        return False
    if not m.matching(f.get('evidence', {}).get('sectionHeading', ''), p):
        return False
    if re.search('cdp-japan\\.jp/election/', f['url']) and (not f.get('evidence', {}).get('selector', '').startswith('article.member-detail')):
        return False
    if re.search('wikipedia\\.org|wikidata\\.org', f['url']):
        return False
    if m.BAD.search(v) or re.search('上司|知人|友人|先輩|氏は|さんは', v):
        return False
    if len(v) > 180:
        return False
    if f['category'] == 'policy':
        if re.search('実現しました|実施しました|達成しました|働きかけ.*結果|訴えた結果', v):
            return False
        if not re.search('教育|保育|子育て|学校|給食|防災|災害|医療|介護|高齢|障害|福祉|交通|道路|公園|住宅|税|雇用|就労|財政|行政|環境|脱炭素|農業|産業|観光|経済|デジタル|防犯|犯罪|感染|健康|賃金|年金|社会保険|水道|ごみ|ゴミ|災害|避難|育児|待機児童|いじめ|不登校|ジェンダー|男女|差別|人権|民主|憲法', v):
            return False
        if not re.search('推進|整備|拡充|導入|実現|強化|廃止|削減|ゼロ|増や|目指|取り組|なく|無償|支援|助成|補助|改善|解消|充実|確保|守|改革|安全|安心|保障|減税|活性|無料', v):
            return False
    return True
for x in A:
    p = raw[x['id']]
    fs = x['findings'].copy()
    publishers = {}
    for att in x['enrichment']['attempted']:
        u = att['url'].split('#')[0]
        f = cfg.CACHE_DIR / (hashlib.sha256(u.encode()).hexdigest()[:24] + '.html')
        if not f.exists():
            f = m.LOCAL.get(u)
        if not f or not f.exists() or (not f.stat().st_size):
            continue
        try:
            s = cached_soup(str(f))
            scope, h, sel = m.isolate(s, p)
            page_title = s.title.get_text(' ', strip=True) if s.title else ''
            if m.re.search('医療法人|クリニック|医院|病院|株式会社|会社概要|法人概要', page_title) and (not m.matching(page_title, p)) and (m.stype(u) == '本人発信'):
                publishers[u] = '団体公式'
                meta = f.with_suffix('.json')
                if meta.exists():
                    publishers[json.loads(meta.read_text(encoding='utf-8')).get('finalURL', u)] = '団体公式'
            if scope:
                fs += m.facts(scope, p, u, m.stype(u), h, sel)
                report['cacheReparsed'] += 1
        except Exception:
            pass
    result = {}
    for f in fs:
        if not valid(f, p):
            report['removed'].append({'id': x['id'], 'reason': '短い具体的事実または本人範囲の監査基準を満たさず', 'url': f['url']})
            continue
        if f['url'] in publishers:
            f['sourceType'] = publishers[f['url']]
        f['evidence']['matchedName'] = m.matching(f['evidence'].get('sectionHeading', ''), p) or p['name']
        result[f['category'], m.norm(f['summary'])] = f
    ordered = sorted(result.values(), key=lambda f: len(f['summary']), reverse=True)
    kept = []
    for f in ordered:
        core = m.norm(f['summary'].replace('掲載経歴：', '').rstrip('。'))
        if any((g['category'] == f['category'] and core in m.norm(g['summary']) for g in kept)):
            continue
        kept.append(f)
    x['findings'] = kept[:24]
    if x['findings']:
        x['enrichment']['status'] = '情報追加'
    elif x['enrichment']['status'] == '情報追加':
        x['enrichment']['status'] = '既存内容確認'
    if x['enrichment']['status'] == '既存内容確認':
        x['enrichment']['note'] = '既存の出典・プロフィール内に本人氏名を確認。今回、既存記録を超える追加事実は抽出していない。旧資料・候補掲載を現職証明には用いていない。'
    if x['enrichment']['status'] == '取得失敗' and (not any((a['status'] == '取得失敗' for a in x['enrichment']['attempted']))):
        x['enrichment']['status'] = '追加根拠未確認'
        x['enrichment']['note'] = '既存資料はCSV/PDFまたは取得対象外SNS。本人プロフィール本文の追加根拠は未確認。'
assert len(A) == len(raw) and set((x['id'] for x in A)) == set(raw)
assert all((x['enrichment']['attempted'] for x in A))
assert all((f.get('evidence') and f.get('checkedAt') == cfg.CHECKED_AT for x in A for f in x['findings']))
assert not any((m.BAD.search(f['summary']) for x in A for f in x['findings']))
P.write_text(json.dumps(A, ensure_ascii=False, indent=2), encoding='utf-8')
report['counts'] = {'people': len(A), 'peopleAdded': sum((bool(x['findings']) for x in A)), 'findings': sum((len(x['findings']) for x in A)), 'statuses': dict(collections.Counter((x['enrichment']['status'] for x in A))), 'categories': dict(collections.Counter((f['category'] for x in A for f in x['findings'])))}
cfg.AUDIT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(report['counts'])
