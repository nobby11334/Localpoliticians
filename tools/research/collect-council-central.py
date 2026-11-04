#!/usr/bin/env python3
"""Re-fetch and parse municipal council official HTML rosters. Python stdlib + lxml.
Run --refresh to renew snapshots. Never exports private addresses, phones, email or birth dates.
Listed officeholders are valid only for source date / observed page date, not a real-time guarantee.
"""
import sys,re,json,datetime,urllib.request,concurrent.futures,pathlib,collections
from lxml import html
from urllib.parse import urljoin
from importlib.machinery import SourceFileLoader
B=pathlib.Path(__file__).parent
SOURCES=SourceFileLoader('fetchcentral',str(B/'fetch-central.py')).load_module().SOURCES
TODAY=datetime.date.today().isoformat(); REFRESH='--refresh' in sys.argv

def load(k,u):
 p=B/(k+'.html')
 if REFRESH or not p.exists():
  p.write_bytes(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0 (public council roster research)'}),timeout=40).read())
 t=html.fromstring(p.read_bytes());t.make_links_absolute(u);return t

def text(e):return '' if not isinstance(e.tag,str) else re.sub(r'[\s\u200b\ufeff]+',' ',e.text_content()).strip()
def name(s):return re.sub(r'[\s\u200b\ufeff]+','',re.sub(r'[（(][^）)]*[）)]','',s)).strip('・')
def dateof(t):
 txt=text(t)
 # Explicit roster cutoff is preferable. Restrict to matches with 現在 immediately following date.
 for pattern in [r'((?:20\d\d|令和\s*[0-9０-９]+)年\s*[0-9０-９]+月\s*[0-9０-９]+日)\s*現在',r'更新日[：:\s\[\]]*((?:20\d\d|令和\s*[0-9０-９]+)年\s*[0-9０-９]+月\s*[0-9０-９]+日)']:
  m=re.search(pattern,txt)
  if m:
   s=m.group(1);a=list(map(int,re.findall(r'\d+',s)));y=a[0]+2018 if '令和' in s else a[0]
   try:return datetime.date(y,a[1],a[2]).isoformat(),'名簿の現在日' if '現在' in pattern else 'ページ更新日'
   except:pass
 return TODAY,'取得日のページ掲載確認（名簿基準日不明）'

people=[]; reports=[]
def make(k,t,n,group=None,party=None,profile=None):
 code,city,url=SOURCES[k];d,basis=dateof(t);n=name(n)
 if not n or len(n)>20:raise ValueError((k,'invalid name',n))
 p={'municipalityCode':code,'municipality':city,'name':n,'office':'市議会議員','asOf':d,'asOfBasis':basis,'retrievedAt':TODAY,'sourceURL':url,'sourceTitle':text(t.xpath('//title')[0]),'findings':[]}
 if group:p['group']=re.sub(r'[（(][^）)]*[）)]','',group).strip()
 if party:p['party']=party
 if profile:p['officialProfileURL']=profile
 people.append(p);return p

def finding(p,title,summary,url=None,category='activity',period=None):
 p['findings'].append({'category':category,'title':title,'summary':summary,'period':period or p['asOf']+'資料時点','url':url or p['sourceURL'],'sourceType':'行政・議会','asOf':p['asOf']})

def cells(r):return r.xpath('./th|./td')
def link(c):
 a=c.xpath('.//a[@href]');return a[0].get('href')if a else None

def parse(k,t):
 tables=t.xpath('//table')
 if k in ['kyoto','kobe','sakai','nagano','shizuoka','hamamatsu','suita']:
  tables=tables if k in ['kyoto','kobe']else tables[:1]
  for tb in tables:
   for r in tb.xpath('.//tr'):
    c=cells(r);v=[text(x)for x in c]
    if not c:continue
    n=g=prof=None
    if k=='kyoto' and len(c)==3 and v[0]!='名前':n,g,prof=v[0],v[1],link(c[0])
    elif k=='kobe' and len(c)==2:n,prof=v[0],link(c[0])
    elif k=='sakai' and len(c)==6 and v[0].isdigit():n,g,prof=v[1],v[4],link(c[1])
    elif k=='nagano' and len(c)==4 and v[0]!='議席番号':n,g,prof=v[1],v[3],link(c[1])
    elif k=='shizuoka' and len(c)>=3 and v[-1].endswith('区'):
     nc=c[-3];br=nc.xpath('.//br');n=br[-1].tail if br else text(nc);g=text(c[-2]);prof=link(nc)
    elif k=='hamamatsu' and len(c)>=6 and c[0].xpath('.//strong'):n=text(c[0].xpath('.//strong')[0]);g=v[-1]
    elif k=='suita' and len(c)>=5 and re.match(r'^\d+',v[0]):n=v[1];g=v[-1];prof=link(c[1])
    if n and name(n) not in ['氏名','―','－','欠員']:
     p=make(k,t,n,g,profile=prof)
     if k=='sakai':finding(p,'所属常任委員会',v[5])
     elif k=='hamamatsu':finding(p,'所属委員会','常任委員会：'+v[1]+'／特別委員会：'+v[2])
  return
 if k=='nagoya':
  for dl in t.xpath('//div[@id="voice"]/dl'):
   h=dl.xpath('preceding-sibling::h2[1]');g=re.sub(r'（\d+人）.*','',text(h[0]))
   for dd in dl.xpath('./dd'):
    role=text(dd.getprevious());ss=html.fromstring('<div>'+''.join(html.tostring(x,encoding='unicode')for x in dd)+'</div>')if False else None
    parts=re.split(r'<br\s*/?>',html.tostring(dd,encoding='unicode'))
    for part in parts:
     n=re.sub('<[^>]+>','',part).strip()
     if n:
      p=make(k,t,n,g)
      if role!='団員':finding(p,'会派内役職',g+'：'+role)
  return
 if k=='osaka':
  for i,a in enumerate(t.xpath('//table//a')):
   u=a.get('href');sub=load('osaka-'+str(i),u);g=text(a)
   for r in sub.xpath('//table//tr'):
    c=cells(r);v=[text(x)for x in c]
    if c and any('氏名' in x for x in v):continue
    if len(c)==3 and v[0]!='氏名':
     n=re.sub(r'\[正字\]|［正字］','',v[0]);p=make(k,sub,n,g)
     p['sourceURL']=u
     if v[2]:finding(p,'会派内役職',g+'：'+v[2],u)
  return
 if k=='toyama':
  for r in tables[0].xpath('.//tr')[1:]:
   c=cells(r)
   if len(c)!=3:continue
   for n in re.split('、',text(c[2])):
    if n.strip():make(k,t,n,text(c[0]))
  return
 if k=='kanazawa':
  for tb in tables:
   g=re.sub(r'（\d+人）.*','',text(tb.xpath('preceding::h2[1]')[0]))
   for r in tb.xpath('.//tr')[1:]:
    c=cells(r)
    if len(c)==2:
     p=make(k,t,text(c[1]),g,profile=link(c[1]));role=text(c[0]);
     if role:finding(p,'会派内役職',g+'：'+role)
  return
 if k in ['himeji','fukui','nara','otsu']:
  for tb in tables:
   d={text(cells(r)[0]):cells(r)[1]for r in tb.xpath('.//tr')if len(cells(r))==2}
   key=next((key for key in d if key in ['名前','氏名','氏名、当選回数']),None)
   if not key and k=='nara':
    hh=tb.xpath('preceding::h2[1]')
    if not hh:continue
    n=re.sub(r'^\d+\s*','',text(hh[0]));g=text(d['所属会派']) if '所属会派' in d else None
    p=make(k,t,n,g)
    if '所属委員会' in d:finding(p,'所属委員会',text(d['所属委員会']))
    if '役職' in d:finding(p,'議会役職',text(d['役職']))
    continue
   if not key:continue
   n=re.sub(r'\s*\d+期目.*','',text(d[key]));g=None;party=None
   for key2 in d:
    if '会派' in key2:
     g=text(d[key2]);m=re.match(r'(.*?)[（(](.*?)[）)]',g)
     if m and '党派' in key2:g,party=m.groups()
   p=make(k,t,n,g,party)
   for key2 in d:
    if key2 in ['常任委員会','特別委員会等']and text(d[key2]):finding(p,key2,text(d[key2]))
    if '当選回数'==key2:finding(p,'当選回数',text(d[key2]))
    if key2 in ['ホームページ','個人ホームページ']:
     u=link(d[key2]);
     if u:p['website']=u
  return
 if k=='niigata':
  g=None
  for e in t.iter():
   if e.tag=='h2' and re.search(r'（\d+人）',text(e)):g=re.sub(r'（\d+人）.*','',text(e))
   if e.tag=='p' and text(e).startswith('氏名') and '郵便番号' in text(e):
    n=text(e).split('郵便番号')[0].removeprefix('氏名').strip();make(k,t,n,g)
  return
 if k=='matsumoto':
  for h in t.xpath('//h3'):
   if not re.match(r'議席番号\d+',text(h)):continue
   elems=[]
   for e in h.itersiblings():
    if e.tag in ['h2','h3']:break
    elems.append(e)
   s='\n'.join(html.tostring(x,encoding='unicode')for x in elems);lines=re.split(r'<br\s*/?>|</p>',s);fields={}
   for ln in lines:
    a=html.fromstring('<div>'+ln+'</div>');st=text(a)
    for key in ['氏名','会派','政党等','当選回数']:
     if st.startswith(key):fields[key]=st.removeprefix(key).strip()
   if '氏名'not in fields:continue
   p=make(k,t,fields['氏名'],re.sub(r'（.*','',fields.get('会派','')),fields.get('政党等'))
   if fields.get('当選回数'):finding(p,'当選回数',fields['当選回数'])
   for e in elems:
    if 'ホームページ' in text(e):
     aa=e.xpath('.//a[starts-with(@href,"http")]');
     if aa:p['website']=aa[0].get('href')
  return
 if k=='hirakata':
  for h in t.xpath('//h2'):
   m=re.match(r'\d+番\s*(.+?)[（(]',text(h))
   if not m:continue
   p=make(k,t,m.group(1));e=h.getnext()
   if e is None:continue
   s=text(e);m=re.search(r'・([^・]+?)\s*現在(\d+)期目',s)
   if m:p['group']=m.group(1).strip();finding(p,'議員期数',m.group(2)+'期目')
   m=re.search(r'ホームページ\s*(https?://[^\s・]+)',s)
   if m:p['website']=m.group(1)
  return
 if k=='okazaki':
  for tb in tables:
   h=tb.xpath('preceding::h2[1]');g=re.sub(r'（\d+人）.*','',text(h[0]))if h else None
   for r in tb.xpath('.//tr'):
    c=cells(r)
    if len(c)<2:continue
    role=text(c[0])
    n=text(c[1])
    if n and n!='氏名':
     p=make(k,t,n,g)
     if role and role not in ['議員','']:
      finding(p,'会派内役職',str(g)+'：'+role)
  return
 if k.startswith('takatsuki-'):
  for h in t.xpath('//h2'):
   es=[]
   for e in h.itersiblings():
    if e.tag=='h2':break
    es.append(e)
   ss=' '.join(text(e)for e in es);m=re.search(r'会派[:：]([^\s]+)',ss)
   if m:
    p=make(k,t,text(h),m.group(1))
    for e in es:
     if 'ホームページ' in text(e):
      aa=e.xpath('.//a[starts-with(@href,"http")]')
      if aa:p['website']=aa[0].get('href')
  return
 if k=='kasugai':
  for li in t.xpath('//li[contains(@class,"imglows")]'):
   img=li.xpath('.//img[@alt]');pp=li.xpath('./p')
   if img and pp:
    n=img[0].get('alt').removeprefix('写真：').removesuffix('議員');raw=html.tostring(pp[0],encoding='unicode');lines=[text(html.fromstring('<div>'+v+'</div>'))for v in re.split(r'<br\s*/?>',raw)]
    make(k,t,n,lines[-1])
  return
 if k=='toyonaka':
  for a in t.xpath('//a[@href]'):
   u=a.get('href')
   if '/giinsyokai/giin/'in u and '/index.html' not in u and len(name(text(a)))in range(2,13):make(k,t,text(a),profile=u)
  return
 if k=='toyota':
  for a in t.xpath('//table//a[@href]'):
   n=text(a)
   if n and len(name(n))in range(2,13):make(k,t,n,profile=a.get('href'))
  return
 if k=='toyohashi':
  g=None
  for r in tables[0].xpath('.//tr')[1:]:
   c=cells(r)
   if len(c)==3:g=re.sub(r'（\d+名）.*','',text(c[0]))
   if len(c)>=1:
    p=make(k,t,text(c[-1]),g);role=text(c[-2]) if len(c)>=2 else ''
    if role and role!='団員':finding(p,'会派内役職',str(g)+'：'+role)
  return
 if k=='kusatsu':
  for h in t.xpath('//h2'):
   m=re.match(r'(.+?)[（(].*?当選回数(\d+)回',text(h))
   if m:
    p=make(k,t,m.group(1));finding(p,'当選回数',m.group(2)+'回')
  return

def run():
 for k,(_,city,u)in SOURCES.items():
  before=len(people)
  try:parse(k,load(k,u));reports.append({'key':k,'municipality':city,'count':len(set(p['name']for p in people[before:])),'url':u})
  except Exception as e:reports.append({'key':k,'municipality':city,'count':len(set(p['name']for p in people[before:])),'url':u,'error':str(e)})
 # merge only exact within-municipality repeats, do not infer spellings.
 unique={}
 for p in people:
  key=(p['municipalityCode'],p['name'])
  if key not in unique:unique[key]=p
 out={'meta':{'retrievedAt':TODAY,'count':len(unique),'sourceType':'行政・議会','scope':'中部・近畿の公式市議会名簿。掲載日・名簿基準日現在の在職者。政党と会派は別項目。経歴・PTA等は網羅調査未実施。','privateContactInformationExcluded':True},'sources':reports,'people':list(unique.values())}
 (B/'council-central.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(reports,ensure_ascii=False,indent=2));print('TOTAL',len(unique))
if __name__=='__main__':run()
