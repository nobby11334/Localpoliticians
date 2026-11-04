import json,re,urllib.request,concurrent.futures,time
from pathlib import Path
from bs4 import BeautifulSoup
from importlib.machinery import SourceFileLoader
base=Path(__file__).resolve().parent
jcp=SourceFileLoader('jcp',str(base/'collect-party-members.py')).load_module()
indexpath=base/'cache/kokumin.html'
if not indexpath.exists():indexpath.write_text(urllib.request.urlopen('https://new-kokumin.jp/member',timeout=30).read().decode())
index=BeautifulSoup(indexpath.read_text(),'html.parser')
links={a.get('href'):a.get_text(strip=True) for a in index.select('a[href*="/member_tag/"]') if a.get_text(strip=True) in jcp.prefs}
def get(item):
 url,pref=item;path=base/'cache'/('kokumin-'+pref+'.html')
 if path.exists():return pref,url,path.read_text()
 for attempt in range(3):
  try:
   h=urllib.request.urlopen(url,timeout=30).read().decode();path.write_text(h);return pref,url,h
  except:
   if attempt==2:raise
   time.sleep(1)
records=[];unmapped=[];errors=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
 fs={pool.submit(get,item):item for item in links.items()}
 for f in concurrent.futures.as_completed(fs):
  try:
   pref,url,h=f.result();s=BeautifulSoup(h,'html.parser');n=0
   for sec in s.select('section.member_sec[id^="assembly"]'):
    head=sec.select_one('h2');heading=head.get_text(' ',strip=True) if head else ''
    office=re.sub(r'\s*（.*','',heading)
    locality=re.sub(r'議?会議員$','',office)
    if locality==pref:continue
    candidates=[m for m in jcp.municipalities if m['pref']==pref and (m['name']==locality or locality.startswith(m['name']) and locality.endswith('区'))]
    if not candidates:
     unmapped.append({'pref':pref,'heading':heading,'url':url});continue
    m=max(candidates,key=lambda x:len(x['name']))
    for li in sec.select('.member_list > li'):
     a=li.select_one('.name a')
     if not a:continue
     note='掲載日時不明。2026-11-04取得。党公式名簿の掲載情報であり、現在の在職および次回選挙への立候補は未確認。'
     findings=[{'category':'party','title':'国民民主党の公式地方自治体議員名簿に掲載','summary':office+'として掲載。'+note,'period':'掲載日時不明','url':url,'sourceType':'政党公式','asOf':jcp.ASOF}]
     area=li.select_one('.area')
     if area and '当選' in area.get_text():findings.append({'category':'career','title':'当選回数（党公式掲載）','summary':area.get_text(' ',strip=True),'period':'掲載日時不明','url':url,'sourceType':'政党公式','asOf':jcp.ASOF})
     records.append({'municipalityCode':m['code'],'name':a.get_text(' ',strip=True),'office':office,'party':'国民民主党','asOf':jcp.ASOF,'sourceURL':url,'sourceTitle':'国民民主党 議員 - '+pref,'website':a['href'],'findings':findings,'researchNotes':note});n+=1
   print(pref,n,flush=True)
  except Exception as e:errors.append({'item':fs[f],'error':str(e)})
(base/'kokumin-members.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
(base/'kokumin-report.json').write_text(json.dumps({'count':len(records),'errors':errors,'unmapped':unmapped},ensure_ascii=False,indent=2)+'\n')
print('DONE',len(records),'errors',len(errors),'unmapped',len(unmapped),flush=True)
