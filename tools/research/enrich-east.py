import os,urllib.request,urllib.parse,json,concurrent.futures,pathlib,re,hashlib,time
from bs4 import BeautifulSoup
P=pathlib.Path(__file__).parent;CACHE=P/'east-profile-cache';CACHE.mkdir(exist_ok=True)
D=json.loads((P/'council-east.json').read_text());people=D['people']
def norm(s):return re.sub(r'\s+','',s).replace('﨑','崎').replace('髙','高')
index={(x['municipalityCode'],norm(x['name'])):x for x in people}
def fetch(u):
 f=CACHE/(hashlib.sha256(u.encode()).hexdigest()+'.html')
 try:
  if f.exists():b=f.read_bytes()
  else:
   if os.environ.get('EAST_OFFLINE')=='1':return None
   req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0 (compatible; CivicLedgerResearch/1.0)'})
   with urllib.request.urlopen(req,timeout=18) as r:b=r.read(3000000)
   f.write_bytes(b)
  return BeautifulSoup(b,'html.parser')
 except Exception:
  if u.startswith('http://'):
   return fetch('https://'+u[7:])
  return None
def parallel(urls):
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:return dict(zip(urls,ex.map(fetch,urls)))
def parse_local(n):return BeautifulSoup((P/(n+'.raw')).read_bytes(),'html.parser')
# authoritative member profile pages
jobs=[]
s=parse_local('yokohama')
for a in s.select('a[href*="/shikai/giin/kubetsu/meibo"]'):
 if '#' in a['href']:jobs.append(('14100',a.text.strip(),urllib.parse.urljoin('https://www.city.yokohama.lg.jp/',a['href'])))
for f in P.glob('chiba-list_kaiha*.raw'):
 for a in BeautifulSoup(f.read_bytes(),'html.parser').select('#tmp_contents a[href*="list_senkyoku"]'):jobs.append(('12100',a.text.strip(),urllib.parse.urljoin('https://www.city.chiba.jp/',a['href'])))
for f in P.glob('sendai-*.raw'):
 for a in BeautifulSoup(f.read_bytes(),'html.parser').select('article .page_list a'):
  parent=json.loads((P/'east-extra-sources.json').read_text()).get(f.stem)
  if parent:jobs.append(('04100',a.text.strip(),urllib.parse.urljoin(parent,a['href'])))
for a in parse_local('nerima').select('td a[href*="/50on/"]'):jobs.append(('13120',a.text.strip(),a['href']))
urls=list(dict.fromkeys(urllib.parse.urldefrag(u)[0] for _,_,u in jobs));pages=parallel(urls)
links=[]
for code,n,u in jobs:
 person=index.get((code,norm(n)));base,anchor=urllib.parse.urldefrag(u);s=pages[base]
 if not person or not s:continue
 person['officialProfileURL']=u
 if code in ['14100','12100']:
  el=s.find(id=anchor) or s.find('a',attrs={'name':anchor})
  if not el:continue
  table=el if el.name=='table' else el.find_next('table')
  if not table:continue
  # one table per member (site template)
  for a in table.select('a[href^="http"]'):
   href=a['href']
   if any(x in href for x in ['x.com/','twitter.com/','facebook.com/','instagram.com/','youtube.com/','city.yokohama','city.chiba','line.me']):continue
   links.append((code,n,href,u));break
 else:
  for a in s.select('a[href^="http"]'):
   if 'ホームページ' in a.text and not any(x in a['href'] for x in ['city.sendai.jp','city.nerima.tokyo.jp']):links.append((code,n,a['href'],u));break
for p in people:
 if p.get('website'):links.append((p['municipalityCode'],p['name'],p['website'],p['sourceURL']))
links=list({(c,n,u):(c,n,u,src) for c,n,u,src in links}.values())
(P/'east-personal-links.json').write_text(json.dumps(links,ensure_ascii=False,indent=2));print('official pages',len(urls),'personal links',len(links),flush=True)
# homepage then at most two directly linked biography pages per person
homepages=parallel(list(dict.fromkeys(u for _,_,u,_ in links)))
profilejobs=[]
for c,n,u,src in links:
 s=homepages[u]
 if s is None:continue
 profilejobs.append((c,n,u,src))
 matches=[]
 for a in s.select('a[href]'):
  label=a.get_text(' ',strip=True);h=a['href'];full=urllib.parse.urljoin(u,h)
  if full.startswith('http') and (re.search(r'プロフィール|経歴|略歴|自己紹介|[Pp]rofile|[Aa]bout',label) or re.search(r'/(profile|about|biography)([./?#_-]|$)',h)):
   if urllib.parse.urlparse(full).netloc.replace('www.','')==urllib.parse.urlparse(u).netloc.replace('www.',''):matches.append(full)
 for v in list(dict.fromkeys(matches))[:2]:profilejobs.append((c,n,v,src))
profilejobs=list({(c,n,u):(c,n,u,src) for c,n,u,src in profilejobs}.values())
(P/'east-biography-jobs.json').write_text(json.dumps(profilejobs,ensure_ascii=False,indent=2));print('biography jobs',len(profilejobs),flush=True)
pages2=parallel(list(dict.fromkeys(u for _,_,u,_ in profilejobs)))
# Only specific factual career/community/organization statements, never full page dumps
candidates=[]
for c,n,u,src in profilejobs:
 s=pages2[u]
 if s is None:continue
 for t in s(['script','style','nav','header','footer','form','noscript']):t.decompose()
 main=s.find('main') or s.find('article') or s
 lines=[]
 for el in main.find_all(['p','li','dd','td']):
  text=re.sub(r'\s+',' ',el.get_text(' ',strip=True)).strip()
  if not 5<=len(text)<=500:continue
  if re.search(r'生年月日|生まれ|出生|家族|夫婦|長男|長女|次男|次女|趣味|血液|住所|電話|TEL|FAX|〒|メール|copyright',text,re.I):continue
  if not re.search(r'卒業|修了|中退|入学|入社|勤務|退社|退職|秘書|取締役|代表理事|理事長|ＰＴＡ|PTA|自治会|町会|町内会|消防団|民生委員|保護司|校長|教員|教授|会社員|看護師|保育士|弁護士|税理士|行政書士|社会保険労務士',text,re.I):continue
  if re.search(r'議員一覧|サイトマップ|プライバシー|コメント|関連記事|この記事|投稿者|アーカイブ',text):continue
  if text not in lines:lines.append(text)
 if lines:candidates.append({'code':c,'name':n,'url':u,'officialSource':src,'lines':lines})
(P/'east-biography-candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2));print('candidate people',len({(x['code'],x['name']) for x in candidates}),'pages',len(candidates),'lines',sum(len(x['lines']) for x in candidates),flush=True)
# Save website reference enrichment separately; caller review controls findings import
(P/'east-enriched-base.json').write_text(json.dumps(D,ensure_ascii=False,indent=2))
