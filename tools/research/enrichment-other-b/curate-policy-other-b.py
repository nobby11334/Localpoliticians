"""Replace copied policy sentences with short factual summaries of specific proposals.
All source text is drawn from the already retrieved, name-matched individual section.
"""
import json, importlib.util, hashlib, collections
from pathlib import Path
import research_config as cfg
cfg.require_snapshot_curations()
cfg.prepare_output()
R = Path(__file__).resolve().parent
sp = importlib.util.spec_from_file_location('research_b', R / 'research-other-b.py')
m = importlib.util.module_from_spec(sp)
sp.loader.exec_module(m)
A = json.loads(cfg.RESULT_PATH.read_text(encoding='utf-8'))
raw = {p['id']: p for p in m.PEOPLE}
MAP = {'田村勝': [('ICT教育', '学校でのICT・外国語教育', '児童生徒の情報活用力を育てるICT教育と、小学校の外国語教育を進める方針を掲載。'), ('地下鉄東西線', '地下鉄東西線の延伸検討', '仙台港まで地下鉄東西線を延ばす構想について、議論を進める方針を掲載。'), ('強靭なまちづくり', '災害への備え', '災害に耐えられる都市づくりを政策テーマとして掲載。')], '西山さちよ': [('産後ケア', '産後ケアの拡充', '出産後のケアを充実させ、産後うつや育児不安を支える方針を掲載。'), ('福祉避難所', '妊産婦・乳幼児向け避難所', '妊産婦と乳幼児のための福祉避難所を設ける方針を掲載。'), ('妊娠→出産→育児', '妊娠から育児までの支援', '妊娠・出産・育児の各段階を継続して支援する方針を掲載。'), ('保育園の施設拡充', '保育施設・保育の質', '保育所の施設を整え、保育の質も高める方針を掲載。'), ('障害児・医療的ケア児', '障害・医療的ケアのある子の支援', '障害児と医療的ケアを必要とする子どもの支援を政策に掲げる。'), ('学校給食の無償化', '給食費の負担軽減', '学校給食を無料にする方針を掲載。')], 'しらくに高太郎': [('産前産後ケアの充実', '出産前後の支援・子どもの医療費', '出産前後のケアを充実させ、子どもの医療費助成を広げる方針を掲載。'), ('介護・福祉職の待遇改善', '介護福祉の処遇・医療提供', '介護・福祉分野で働く人の処遇を改善し、質の高い医療を安定して提供する方針を掲載。'), ('有機農業と地産地消', '有機農業・地域の農業', '有機栽培と地元産品の消費を進め、農業を担う人を育てる方針を掲載。'), ('食やつどい', '地域での健康づくり', '食や交流を通して身近な場所で健康を育む活動を支える方針を掲載。')], '山本のりかず': [('地域包括ケアシステム', '地域で支える介護・福祉', '地域包括ケアの仕組みを整え、高齢者と障害者の福祉を充実させる方針を掲載。'), ('民間活力', '神戸の経済政策', '神戸の経済を活性化するため、民間の力を取り入れる方針を掲載。'), ('子育て世代への支援教育', '子育て・教育への支援', '子育て世帯への支援と教育の充実を政策に掲げる。'), ('二重行政', '兵庫県・神戸市の行政分担', '兵庫県と神戸市の行政の重複を解消する方針を掲載。'), ('議員報酬・議員定数削減', '議会費用・政務活動費の公開', '議員の報酬と定数を減らし、政務活動費の情報公開を徹底する方針を掲載。')]}
from functools import lru_cache

@lru_cache(maxsize=2048)
def parse(f):
    return m.soupof(Path(f).read_bytes())
curated = 0
for x in A:
    key = m.norm(x['name'])
    if key not in MAP:
        continue
    p = raw[x['id']]
    fs = [f for f in x['findings'] if f['category'] == 'policy']
    for att in x['enrichment']['attempted']:
        u = att['url'].split('#')[0]
        f = cfg.CACHE_DIR / (hashlib.sha256(u.encode()).hexdigest()[:24] + '.html')
        if not f.exists():
            f = m.LOCAL.get(u)
        if not f or not f.exists() or (not f.stat().st_size):
            continue
        try:
            scope, h, sel = m.isolate(parse(str(f)), p)
            if scope:
                fs += m.facts(scope, p, u, m.stype(u), h, sel)
        except:
            pass
    selected = []
    for marker, title, summary in MAP[key]:
        src = next((f for f in fs if f['category'] == 'policy' and marker in f['summary']), None)
        if not src:
            continue
        f = src.copy()
        f['evidence'] = src['evidence'].copy()
        f['title'] = '掲げる政策：' + title
        f['summary'] = summary + '実現状況は未確認。'
        f['evidence']['rule'] = '本人名一致の独立した政策範囲から対象と方針を短く要約。達成・因果関係を判断しない。'
        assert m.matching(f['evidence']['sectionHeading'], p) and (not m.BAD.search(f['summary']))
        selected.append(f)
    x['findings'] = [f for f in x['findings'] if f['category'] != 'policy'] + selected
    curated += len(selected)
    if x['findings']:
        x['enrichment']['status'] = '情報追加'
    elif x['enrichment']['status'] == '情報追加':
        x['enrichment']['status'] = '既存内容確認'
assert len(A) == len(raw) and {x['id'] for x in A} == set(raw)
cfg.RESULT_PATH.write_text(json.dumps(A, ensure_ascii=False, indent=2), encoding='utf-8')
report = json.loads(cfg.AUDIT_PATH.read_text(encoding='utf-8'))
report['policyCuration'] = {'specificProposalsSummarized': curated, 'method': '氏名一致の既取得政策欄から対象・方針を短く要約。重複表現・抽象標語・過去の功績主張を除外。'}
report['counts'] = {'people': len(A), 'peopleAdded': sum((bool(x['findings']) for x in A)), 'findings': sum((len(x['findings']) for x in A)), 'statuses': dict(collections.Counter((x['enrichment']['status'] for x in A))), 'categories': dict(collections.Counter((f['category'] for x in A for f in x['findings'])))}
cfg.AUDIT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(report['counts'], 'policy', curated)
