"""Re-fetch and parse official west-Japan council rosters; excludes contact details.
Run: python build-west.py [--refresh]
Sources and cached raw HTML live alongside this script. Standard lib + BeautifulSoup4.
"""
import json,os,re,sys,urllib.request,concurrent.futures
from urllib.parse import urljoin
from bs4 import BeautifulSoup
ROOT=os.path.dirname(os.path.abspath(__file__));CACHE=ROOT+'/west-cache'
SOURCES=json.load(open(ROOT+'/west-sources.json'))
from datetime import date as calendar_date
TODAY=calendar_date.today().isoformat()
def clean(x):
 x=re.sub(r'[\u200b\ufeff]','',x)
 return re.sub(r'\s+',' ',x).strip()
def name(x):return clean(re.split(r'[（(【]',x)[0])
def load(k):
 p=f'{CACHE}/{k}.html';u=SOURCES[k][2]
 if '--refresh' in sys.argv or not os.path.exists(p):
  b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=45).read();open(p,'wb').write(b)
 return BeautifulSoup(open(p,'rb').read(),'html.parser')
def date(s,k):
 fixed={'hiroshima':'2026-06-11','fukuyama':'2026-06-05','tokushima':'2026-10-19','matsuyama':'2026-10-30','kochi':'2026-06-15','nagasaki':'2026-08-01','kurashiki':'2026-09-08','okayama':'2025-10-06','takamatsu':'2026-05-13','tottori':'2026-08-24','yamaguchi':'2026-05-01','kure':'2026-10-16','higashihiroshima':'2026-01-23','shunan':'2026-09-03','ube':'2026-09-29','sasebo':'2026-07-01'}
 # Date visible on original roster or its official index, not an assertion of current tenure.
 text=s.get_text(' ',strip=True)
 for pat in [r'令和([0-9０-９]+)年([0-9０-９]+)月([0-9０-９]+)日現在', r'(?:更新日|掲載日|最終更新日)[： :]*(20[0-9]{2})年([0-9]+)月([0-9]+)日']:
  m=re.search(pat,text)
  if m:
   a,b,c=map(int,m.groups());a=a+2018 if a<100 else a
   return f'{a:04d}-{b:02d}-{c:02d}'
 return fixed.get(k,TODAY)
def parse(k):
 s=load(k);code,city,url=SOURCES[k];asof=date(s,k); out=[]
 def add(n,g=None,u=None,p=None,extra=None):
  n=name(n)
  if not n or len(n)>20:return
  d={'municipalityCode':code,'name':n,'office':'市議会議員','asOf':asof,'sourceURL':url,'sourceTitle':city+'議会 公式議員名簿','findings':[], 'asOfBasis':'名簿・掲載更新日' if asof!=TODAY else '取得日（資料基準日未確認）','currentStatus':'資料時点の掲載議員・現職継続未確認'}
  if g:d['group']=clean(g)
  if p:d['party']=clean(p)
  if u:d['profileURL']=urljoin(url,u)
  if extra:d['findings'].append({'category':'activity','title':'議会役職・所属委員会','summary':clean(extra),'period':'資料掲載時点','url':urljoin(url,u) if u else url,'sourceType':'行政・議会','asOf':asof})
  out.append(d)
 if k in ['hiroshima','kumamoto','fukuyama','fukuoka','kochi','tokushima','naha','tottori']:
  for t in s.select('table'):
   if not re.search('氏名|議員名|名前',t.get_text()[:200]):continue
   for tr in t.select('tr'):
    c=tr.find_all(['td','th'],recursive=False)
    if not c or tr.find('th'):continue
    tx=[clean(v.get_text(' ',strip=True)) for v in c]
    if k=='fukuoka':
     nc=tr.select_one('.column-2');gc=tr.select_one('.column-4')
     if nc and gc:add(nc.text,gc.text,nc.a.get('href') if nc.a else None)
    elif k=='hiroshima' and len(c)>=3:add(tx[0],tx[2],c[0].a.get('href') if c[0].a else None)
    elif k=='kumamoto' and len(c)>=4 and tx[0].isdigit():add(tx[1],tx[2],c[1].a.get('href') if c[1].a else None,extra=tx[3])
    elif k=='fukuyama' and len(c)>=2 and tx[0].isdigit():add(tx[1])
    elif k=='tokushima' and len(c)>=4 and re.match(r'^\d{3}',tx[1]):add(tx[0])
    elif k=='naha' and len(c)>=3 and tx[0].isdigit():add(tx[1],tx[2])
    elif k=='tottori' and len(c)>=7 and tx[0].isdigit():add(tx[2],tx[6],extra='所属委員会：'+tx[5])
    elif k=='kochi' and len(c)>=4 and '歳' in tx[2]:
     a=re.split('[（(]',tx[3]);add(tx[0],a[0],p=re.sub('[）)]','',a[1]) if len(a)>1 else None)
 elif k in ['okayama','kagoshima','saga']:
  for a in s.select('a[href]'):
   tx=clean(a.text);h=a['href']
   if k=='okayama' and re.search('[（(].*[）)].*区',tx):add(tx,u=h)
   if k=='kagoshima' and re.search('/shokai/(a-o2|ka-ko2|sa-to2|na-ho2|ma-wa2).html#',h) and 2<=len(tx)<=12:add(tx,u=h)
   if k=='saga' and 'SrchID=' in h:add(tx,u=h)
 elif k=='matsuyama':
  for x in s.select('div.img-area-l,div.img-area-r'):
   ls=x.select('li')
   if ls and re.search('[（(]',ls[0].text):add(ls[0].text,ls[1].text if len(ls)>1 else None)
 elif k in ['nagasaki','takamatsu','kurashiki']:
  for h in s.select('h2'):
   tx=clean(h.text)
   if k=='takamatsu':valid=bool(re.match(r'^[\w\u4e00-\u9fff﨑󠄀]+ [\w\u4e00-\u9fff]+$',tx))
   else:valid=bool(re.search('[（(].*[）)]',tx)) and len(tx)<65
   if not valid:continue
   t=h.find_next('table');g=None;ext=[]
   if t:
    for tr in t.select('tr'):
     cs=tr.find_all(['td','th']);vals=[clean(c.get_text(' ',strip=True)) for c in cs]
     for i in range(0,len(vals)-1,2):
      if vals[i] in ['会派','所属会派','会派名']:g=vals[i+1]
      if vals[i] in ['常任委員会','特別委員会','所属常任委員会','所属特別委員会']:ext.append(vals[i]+'：'+vals[i+1])
   add(tx,g,extra='。'.join(ext) if ext else None)
 elif k=='yamaguchi':
  for tr in s.select('tr'):
   cs=tr.find_all(['td','th']);tx=[clean(c.text) for c in cs]
   if len(tx)==2 and tx[0]=='氏名':
    # Furigana precedes printed name; br separates the lines.
    pieces=[clean(x) for x in cs[1].stripped_strings];add(pieces[-1])
 elif k in ['sasebo','shunan','ube']:
  for h in s.select('h2,h3'):
   tx=clean(h.text)
   if not re.search('[（(].*[）)]',tx) or len(tx)>50:continue
   tx=re.sub(r'^議席番号\d+\s*','',tx);g=None;extra=[]
   if k=='ube':
    t=h.find_next('dl')
    if t:
     for dt in t.select('dt'):
      if dt.text=='所属会派':g=dt.find_next('dd').text
   else:
    t=h.find_next('table')
    if t:
     for tr in t.select('tr'):
      cs=tr.find_all(['td','th']);v=[clean(c.text) for c in cs]
      if len(v)>1 and v[0] in ['会派','所属会派']:g=v[1]
      if len(v)>1 and v[0] in ['所属委員会','常任委員会','特別委員会','その他委員']:extra.append(v[0]+'：'+v[1])
   add(tx,g,extra='。'.join(extra) if extra else None)
 elif k=='kure':
  for t in s.select('table'):
   rows=t.select('tr')
   if len(rows)<4 or 'ふりがな' not in rows[0].text:continue
   n=rows[1].get_text(' ',strip=True);g=None
   for tr in rows:
    cs=tr.find_all(['td','th']);v=[clean(c.text) for c in cs]
    if len(v)>1 and re.sub(r'\s','',v[0])=='会派':g=v[1]
   add(n,g)
 elif k=='higashihiroshima':
  for t in s.select('table'):
   for tr in t.select('tr'):
    cs=tr.find_all('td',recursive=False)
    if len(cs)>=5 and len(list(cs[0].stripped_strings))>=2 and re.search(r'[一-龠]',list(cs[0].stripped_strings)[-1]):
     add(list(cs[0].stripped_strings)[-1])
 elif k=='kurume':
  for tr in s.select('tr'):
   cs=tr.find_all(['td','th'],recursive=False);v=[clean(c.text) for c in cs]
   if len(v)>=5 and v[0].isdigit():add(v[1],re.split('[（(]',v[2])[0],extra='役職・委員会：'+v[4])
 elif k=='urasoe':
  for tr in s.select('tr'):
   cs=tr.find_all(['td','th'],recursive=False);v=[clean(c.text) for c in cs]
   for offset in [0,4]:
    if len(v)>offset+2 and v[offset].isdigit():add(v[offset+1],v[offset+2])
 elif k=='kitakyushu':
  for h in s.select('h3'):
   heading=clean(h.text);m=re.search(r'一般的な名称及び表示：([^）]+)',heading)
   g=m.group(1) if m else re.split('[（(]',heading)[0]
   for sib in h.next_siblings:
    if getattr(sib,'name',None) in ['h3','h2']:break
    if not hasattr(sib,'get_text'):continue
    for line in sib.get_text('\n').splitlines():
     for n in re.split(r'\u3000{2,}',line):
      n=clean(n)
      if 2<len(n)<15 and re.fullmatch(r'[一-龠﨑ぁ-ゖァ-ヶ々 ]+',n):add(n,g)
 elif k=='oita':
  for h in s.select('h2'):
   tx=clean(h.text)
   if not re.match(r'^\d+\.',tx) or '欠番' in tx:continue
   tx=re.sub(r'^\d+\.','',tx);t=h.find_next('table');g=None
   if t:
    for tr in t.select('tr'):
     cs=tr.find_all(['td','th']);v=[clean(c.text) for c in cs]
     if len(v)>1 and v[0]=='会派名':g=v[1]
   add(tx,g)
 elif k=='beppu':
  for t in s.select('table.tbl_member'):
   h=t.select_one('thead');n=re.sub(r'^\d+\s*','',clean(h.text));g=None;policy=None;hp=None
   for tr in t.select('tbody tr'):
    cs=tr.find_all(['td','th'],recursive=False);v=[clean(c.text) for c in cs]
    if len(v)<2:continue
    if v[0]=='会派名':g=v[1]
    if v[0]=='任期中に取り組みたいこと':policy=v[1]
    if v[0]=='個人ホームページ' and cs[1].a:hp=cs[1].a.get('href')
   add(n,g)
   if hp and hp.startswith('http'):out[-1]['website']=hp
   if policy and policy!='－':out[-1]['findings'].append({'category':'policy','title':'任期中に取り組みたいこと','summary':policy,'period':'資料掲載時点','url':url+'#'+t.get('id',''),'sourceType':'行政・議会','asOf':asof})
 elif k=='imabari':
  for h in s.select('h2'):
   ul=h.find_next_sibling('ul')
   if ul:
    for a in ul.select('a[href]'):add(a.get_text(' ',strip=True),h.text,a['href'])
 seen={}
 for p in out:seen[p['name']]=p
 return list(seen.values())
if __name__=='__main__':
 allp=[];errors=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  fut={pool.submit(parse,k):k for k in SOURCES if k not in ['miyazaki','shimonoseki','matsue','marugame']}
  for f,k in fut.items():
   try:
    ps=f.result();allp+=ps;print(k,len(ps))
   except Exception as e:errors.append({'source':k,'error':str(e)});print(k,str(e))
 result={'meta':{'retrievedAt':TODAY,'scope':'中国・四国・九州・沖縄の市議会公式名簿','method':'行政・議会公式HTMLの氏名・会派等を抽出。個人住所・電話・メールは出力しない。名簿掲載は資料時点に限る。asOfBasisが取得日の場合、資料基準日は未確認。','errors':errors},'people':allp}
 result['meta']['count']=len(allp)
 result['meta']['municipalityCount']=len(set(p['municipalityCode'] for p in allp))
 result['meta']['unprocessedSources']=[{'municipality':SOURCES[k][1],'sourceURL':SOURCES[k][2],'reason':'PDF名簿の精確な氏名抽出未完了のため未収録'} for k in ['miyazaki','shimonoseki','matsue','marugame']]
 json.dump(result,open(ROOT+'/council-west.json','w'),ensure_ascii=False,indent=2)
 print('TOTAL',len(allp))
