import json,re,urllib.request,urllib.parse,time,concurrent.futures
from pathlib import Path
from bs4 import BeautifulSoup
BASE=Path(__file__).resolve().parent
REG=Path('../../data/national.json')
ASOF='2026-11-04'
municipalities=json.loads(REG.read_text())['municipalities']
bycode={m['code']:m for m in municipalities}
prefs=list(dict.fromkeys(m['pref'] for m in municipalities))
cache=BASE/'cache';cache.mkdir(exist_ok=True)
def get(pref):
 url='https://www.jcp.or.jp/list/search/?'+urllib.parse.urlencode({'keyword':pref})
 path=cache/('jcp-'+pref+'.html')
 if path.exists():return pref,url,path.read_text()
 for attempt in range(3):
  try:
   data=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (public civic directory research)'}),timeout=40).read().decode()
   path.write_text(data);return pref,url,data
  except Exception:
   if attempt==2:raise
   time.sleep(1)
def parse(pref,url,html):
 soup=BeautifulSoup(html,'html.parser');records=[];unmapped=[];excluded=0
 for block in soup.select('ul.locals-list > li'):
  heading=block.select_one('h3.local-summary')
  if not heading:continue
  locality=heading.get_text(strip=True)
  if locality==pref:
   excluded+=len(block.select('.members-list a'));continue
  for a in block.select('.members-list a'):
   href=urllib.parse.urljoin(url,a.get('href',''))
   match=re.search(r'/member/(\d{6})',href)
   code=match.group(1)[:5] if match else None
   if code and code.endswith('000'):excluded+=1;continue
   m=bycode.get(code)
   if m and (m['pref']!=pref or not (locality==m['name'] or locality.startswith(m['name']) and locality.endswith('区'))):m=None
   if not m:
    candidates=[x for x in municipalities if x['pref']==pref and (locality==x['name'] or locality.startswith(x['name']) and locality.endswith('区'))]
    m=max(candidates,key=lambda x:len(x['name'])) if candidates else None
   if not m:
    unmapped.append({'pref':pref,'locality':locality,'profile':href});continue
   sp=a.find('span')
   if not sp:continue
   name=''.join(str(s) for s in sp.find_all(string=True,recursive=False)).strip()
   if not name:continue
   suffix=m['name'][-1];office={'市':'市議会議員','区':'区議会議員','町':'町議会議員','村':'村議会議員'}.get(suffix,'地方議会議員')
   source='日本共産党中央委員会 地方議員検索（'+pref+'）'
   note='掲載日時不明。2026-11-04取得。党公式名簿の掲載情報であり、現在の在職および次回選挙への立候補は未確認。'
   records.append({'municipalityCode':m['code'],'name':name,'office':office,'party':'日本共産党','asOf':ASOF,'sourceURL':url,'sourceTitle':source,'website':href,'findings':[{'category':'party','title':'日本共産党の公式地方議員名簿に掲載','summary':locality+'の地方議員として掲載。'+note,'period':'掲載日時不明','url':url,'sourceType':'政党公式','asOf':ASOF}],'researchNotes':note})
 return records,unmapped,excluded
if __name__=='__main__':
 allrecords=[];unmapped=[];errors=[];excluded=0;counts={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  tasks={pool.submit(get,p):p for p in prefs}
  for future in concurrent.futures.as_completed(tasks):
   pref=tasks[future]
   try:
    p,u,h=future.result();r,un,ex=parse(p,u,h);allrecords+=r;unmapped+=un;excluded+=ex;counts[p]=len(r);print(p,len(r),flush=True)
   except Exception as e:errors.append({'pref':pref,'error':str(e)});print('ERROR',pref,str(e),flush=True)
 seen={}
 for r in allrecords:seen[(r['municipalityCode'],r['party'],re.sub(r'\s+','',r['name']))]=r
 records=sorted(seen.values(),key=lambda r:(r['municipalityCode'],r['party'],r['name']))
 (BASE/'jcp-members.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
 report={'retrievedAt':ASOF,'count':len(records),'municipalityCount':len(set(r['municipalityCode'] for r in records)),'partyCounts':{'日本共産党':len(records)},'prefCounts':counts,'excludedPrefectureMembers':excluded,'unmapped':unmapped,'errors':errors,'notes':['政党公式名簿のみ。掲載更新日不明につき取得日をasOfに設定し、各レコードに掲載日時不明を明記。','都道府県議員は除外。政令指定都市の行政区は親市コードに集約。','websiteは党公式議員プロフィールURLであり、個人ホームページとは区別が必要。','過去の名簿情報である可能性があるため現職・次回選挙候補確定の根拠として使用しない。']}
 (BASE/'jcp-members-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print('DONE',json.dumps({k:report[k] for k in ['count','municipalityCount','excludedPrefectureMembers','errors']},ensure_ascii=False),flush=True)
