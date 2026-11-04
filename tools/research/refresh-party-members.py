"""Rebuild the official party directory import. Python3 + beautifulsoup4.
Run with --refresh to discard cached pages before collecting.
"""
import sys,subprocess,json,re
from pathlib import Path
from collections import Counter
base=Path(__file__).resolve().parent
if '--refresh' in sys.argv:
 for p in (base/'cache').glob('jcp-*.html'):p.unlink()
 for p in (base/'cache').glob('kokumin*.html'):p.unlink()
for name in ['collect-party-members.py','collect-kokumin.py']:
 subprocess.run([sys.executable,str(base/name)],check=True)
rows=[]
for name in ['jcp-members.json','kokumin-members.json']:rows+=json.loads((base/name).read_text())
seen={}
for r in rows:
 r['profileURL']=r.pop('website')
 r['profileType']='party'
 seen[(r['municipalityCode'],r['party'],re.sub(r'\s+','',r['name']))]=r
rows=sorted(seen.values(),key=lambda r:(r['municipalityCode'],r['party'],r['name']))
(base/'party-members.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
report={'retrievedAt':'2026-11-04','count':len(rows),'municipalityCount':len(set(r['municipalityCode'] for r in rows)),'partyCounts':dict(Counter(r['party'] for r in rows)),'notes':['資料掲載日時不明。asOfは取得日であり在職の確認日ではない。','次回出馬情報を表す名簿ではない。','profileURLは党公式議員紹介ページ。個人ホームページを示すwebsiteは未収録。','公明党は別担当のため収録しない。','都道府県議員を除外し、政令市行政区は親市コードに集約。'], 'sourceReports':{n:json.loads((base/n).read_text()) for n in ['jcp-members-report.json','kokumin-report.json']}}
(base/'party-members-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('MERGED',report['count'],report['municipalityCount'],report['partyCounts'])
