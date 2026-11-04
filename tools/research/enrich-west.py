"""Append explicit biography fields and personal website links from linked official profiles."""
import os,json,urllib.request,concurrent.futures,re,hashlib
from bs4 import BeautifulSoup
from urllib.parse import urljoin
ROOT=os.path.dirname(os.path.abspath(__file__));P=ROOT+'/council-west.json';data=json.load(open(P));CACHE=ROOT+'/west-profile-cache';os.makedirs(CACHE,exist_ok=True)
def f(p):
 u=p.get('profileURL')
 if not u or '#' in u or 'SrchID' in u:return
 try:
  fn=CACHE+'/'+hashlib.sha256(u.encode()).hexdigest()[:20]+'.html'
  if not os.path.exists(fn) or os.path.getsize(fn)==0:
   if '--cached-only' in __import__('sys').argv:return
  if not os.path.exists(fn) or os.path.getsize(fn)==0:open(fn,'wb').write(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read())
  s=BeautifulSoup(open(fn,'rb').read(),'html.parser')
  keys={'職歴':'career','経歴':'career','略歴':'career','主な経歴':'career','学歴':'career','最終学歴':'career','政党':'party','所属政党':'party','所属党派':'party','党派':'party','主な役職':'organization'}
  for tr in s.select('tr'):
   cells=tr.find_all(['td','th'],recursive=False)
   if len(cells)<2:continue
   key=re.sub(r'\s','',cells[0].get_text());v=' '.join(cells[1].stripped_strings)
   if key in ['ホームページ','ホームページアドレス','HP','ウェブサイト','ホームページURL']:
    a=cells[1].find('a',href=True)
    if a and a['href'].startswith('http'):p['website']=a['href'];p['websiteEvidenceURL']=u
   if key in keys and 0<len(v)<3000:
    if key in ['政党','所属政党','党派','所属党派']:p['party']=v
    p['findings'].append({'category':keys[key],'title':key+'（議会公式プロフィール）','summary':v,'period':'資料掲載時点（就任・終了年は記載のとおり）','url':u,'sourceType':'行政・議会','asOf':p['asOf']})
  for dt in s.select('dt'):
   key=re.sub(r'\s','',dt.get_text());dd=dt.find_next_sibling('dd')
   if not dd:continue
   v=dd.get_text(' ',strip=True)
   if key in ['HP等アドレス','ホームページ','個人ホームページ','ホームページURL']:
    a=dd.find('a',href=True)
    if a and a['href'].startswith('http'):p['website']=a['href'];p['websiteEvidenceURL']=u
   if key in keys and 0<len(v)<3000:
    p['findings'].append({'category':keys[key],'title':key+'（議会公式プロフィール）','summary':v,'period':'資料掲載時点','url':u,'sourceType':'行政・議会','asOf':p['asOf']})
  # Only explicit labels near an anchor, never guess homepage from external URLs.
  for a in s.select('a[href]'):
   label=a.get_text(' ',strip=True)
   if label in ['ホームページ','ホームページはこちら','個人ホームページ','ウェブサイト'] and a['href'].startswith('http'):
    p['website']=a['href'];p['websiteEvidenceURL']=u
 except Exception:pass
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:list(ex.map(f,data['people']))
for p in data['people']:
 if p.get('website'):p['websiteKind']='議会公式プロフィール掲載リンク（本人・会派等）'
json.dump(data,open(P,'w'),ensure_ascii=False,indent=2)
print('website',sum(bool(p.get('website')) for p in data['people']),'findings',sum(len(p['findings']) for p in data['people']))
