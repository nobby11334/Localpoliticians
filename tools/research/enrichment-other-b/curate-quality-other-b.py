"""Final factual compression and separation of self-reported council activity from biography."""
import json, re, collections
from pathlib import Path
import research_config as cfg
cfg.require_snapshot_curations()
cfg.prepare_output()
R = Path(__file__).resolve().parent
A = json.loads(cfg.RESULT_PATH.read_text(encoding='utf-8'))
raw = {p['id']: p for p in json.loads(cfg.INPUT_PATH.read_text(encoding='utf-8'))}
changes = []

def norm(s):
    return re.sub('\\s+', '', s)
for x in A:
    kept = []
    p = raw[x['id']]
    for f in x['findings']:
        v = f['summary']
        reason = None
        n = norm(x['name'])
        core = norm(v.removeprefix('掲載経歴：').rstrip('。'))
        generic = {norm(p.get('office', '')), norm(p.get('municipalityName', '') + '議会議員'), '市議会議員', '区議会議員', '町議会議員', '村議会議員', '地方議会議員'}
        if core in generic:
            reason = '既存の議員職名のみの再掲'
        elif f['category'] != 'policy' and re.search('歳の子育て|子育てをしながら|子育てしながら|家庭では|母親として|父親として', v):
            reason = '家族の状況を含む記述'
        elif n == '東みちよ' and '2023年10月3日' in v and ('消防局' in v):
            f['category'] = 'activity'
            f['title'] = '本人報告：消防局への質疑（2023年10月3日）'
            f['summary'] = '本人の活動欄に、救急需要、消防団の活動服、防災啓発などに関する消防局への質疑を掲載。議会記録との照合は未実施。'
        elif n == '東みちよ' and '2024年2月29日' in v and ('市民局' in v):
            f['category'] = 'activity'
            f['title'] = '本人報告：市民局への質疑（2024年2月29日）'
            f['summary'] = '本人の活動欄に、市民局関係の予算特別委員会で戸籍業務のデジタル化などを質問した旨を掲載。議会記録との照合は未実施。'
        elif n == '東みちよ' and '2025年3月4日' in v and ('医療局' in v):
            f['category'] = 'activity'
            f['title'] = '本人報告：医療局への質疑（2025年3月4日）'
            f['summary'] = '本人の活動欄に、医療局関係の予算特別委員会でがん対策、小児・周産期医療、看護職員の確保などを扱った旨を掲載。議会記録との照合は未実施。'
        elif f['category'] != 'policy' and re.search('記事掲載|インタビュー|議会報告|インターネット中継|インターネット動画|質問に立ちました|〈?活動報告', v):
            reason = '略歴に混在した記事・第三者の記述'
        elif n == 'さいとう誠' and '平成１１年４月' in v and ('民進党千葉県連第４区支部幹事長' in v):
            f['summary'] = '平成11年4月に船橋市議選で初当選。農業委員、四市複合事務組合議会議員などの歴任と、民進党千葉県連第4区支部幹事長の経歴を掲載。'
        elif n == '甲斐行雄' and '部活指導者' in v:
            f['summary'] = '野球、女子ソフトボール、駅伝、硬式テニスの部活動指導者を歴任したと紹介。'
        elif n == '倉田れいか' and '2007年初当選' in v and ('練馬区監査委員' in v):
            f['summary'] = '2007年に初当選。練馬区監査委員や、清掃リサイクル・文教児童青少年などの委員会で委員長・副委員長を歴任したと紹介。'
        elif n == '藤崎浩太郎' and '2005年 衆議院議員江田けんじの秘書に' in v:
            f['summary'] = '2005年に江田けんじ衆議院議員の秘書となり、2009年11月から公設第一秘書を務めたと紹介。'
        elif n == '岡本としなが' and '近畿日本ツーリスト株式会社、ソニー生命保険部長職' in v:
            f['summary'] = '近畿日本ツーリストとソニー生命保険（部長職）の勤務歴、MDRT日本会会長と米国本部の役職を紹介。'
        if reason:
            changes.append({'id': x['id'], 'url': f['url'], 'reason': reason})
            continue
        if f['category'] == 'activity':
            f['evidence']['rule'] = '本人名を確認したサイト内の本人活動記載を要約。第三者の業績を本人の経歴に含めず、議会記録との照合は未実施と明示。'
        kept.append(f)
    x['findings'] = kept
    if kept:
        x['enrichment']['status'] = '情報追加'
    elif x['enrichment']['status'] == '情報追加':
        x['enrichment']['status'] = '既存内容確認'
assert len(A) == len(raw) and {x['id'] for x in A} == set(raw)
cfg.RESULT_PATH.write_text(json.dumps(A, ensure_ascii=False, indent=2), encoding='utf-8')
report = json.loads(cfg.AUDIT_PATH.read_text(encoding='utf-8'))
report['finalQualityRemovals'] = changes
report['counts'] = {'people': len(A), 'peopleAdded': sum((bool(x['findings']) for x in A)), 'findings': sum((len(x['findings']) for x in A)), 'statuses': dict(collections.Counter((x['enrichment']['status'] for x in A))), 'categories': dict(collections.Counter((f['category'] for x in A for f in x['findings'])))}
cfg.AUDIT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(report['counts'], 'removed', len(changes))
