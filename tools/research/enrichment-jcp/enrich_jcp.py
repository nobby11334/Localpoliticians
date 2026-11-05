"""Fetch every assigned party profile; follow only its explicit personal HP link.
Bounded pool8 / per-host4 (429/503:2); one retry; successful/error caches; evidence annotations.
No contact, birth or family fields are collected. Sources may be old, not current-role proof.
"""
import ssl,os,httpx,json,re,unicodedata,urllib.request,urllib.parse,hashlib,threading,time,concurrent.futures,collections,sys
from pathlib import Path
from datetime import date
from bs4 import BeautifulSoup
if __name__=='__main__' and '--help' in sys.argv:
 print('Usage: python enrich_jcp.py [--max-new=N] [--reparse]\nConfiguration: see README.md (JCP_INPUT, JCP_OUTPUT, JCP_CACHE_DIR, JCP_CHECKED_AT, etc.).')
 sys.exit(0)
def envpath(key, default):
 return Path(os.environ.get(key,str(default))).expanduser().resolve()
def bounded_int(key, default, maximum):
 value=int(os.environ.get(key,str(default)))
 if not 1<=value<=maximum:raise ValueError(f'{key} must be between 1 and {maximum}')
 return value
BASE=Path(__file__).resolve().parent
INPUT=envpath('JCP_INPUT',Path.cwd()/'jcp-input.json')
OUTPUT=envpath('JCP_OUTPUT',Path.cwd()/'enriched-jcp.json')
REPORT=envpath('JCP_REPORT',OUTPUT.with_name(OUTPUT.stem+'-report.json'))
PROGRESS=envpath('JCP_PROGRESS',OUTPUT.with_suffix('.progress.jsonl'))
RETRY_OUTPUT=envpath('JCP_RETRY_OUTPUT',OUTPUT.with_name(OUTPUT.stem+'-retry.json'))
CACHE=envpath('JCP_CACHE_DIR',Path.cwd()/'.cache'/'jcp')
DATE=os.environ.get('JCP_CHECKED_AT',date.today().isoformat())
DATE=date.fromisoformat(DATE).isoformat()
WORKERS=bounded_int('JCP_WORKERS',8,8)
PER_HOST=bounded_int('JCP_PER_HOST',4,4)
TIMEOUT=float(os.environ.get('JCP_TIMEOUT_SECONDS','20'))
CLIENT_AGE=float(os.environ.get('JCP_CLIENT_MAX_AGE_SECONDS','90'))
if TIMEOUT<=0 or CLIENT_AGE<=0:raise ValueError('Timeout/client age must be positive')
RETRIES=int(os.environ.get('JCP_RETRIES','1'))
if RETRIES not in (0,1):raise ValueError('JCP_RETRIES must be 0 or 1')
REFRESH=os.environ.get('JCP_REFRESH','0')=='1'
PROXY=os.environ.get('JCP_PROXY',os.environ.get('HTTPS_PROXY'))
for path in [CACHE,OUTPUT.parent,REPORT.parent,PROGRESS.parent,RETRY_OUTPUT.parent]:path.mkdir(parents=True,exist_ok=True)
rows=json.loads(INPUT.read_text(encoding='utf-8'))
if not isinstance(rows,list):raise ValueError('Input must be a JSON array')
if any(not all(k in r for k in ['id','name','municipalityCode','municipalityName','prefecture']) for r in rows):raise ValueError('Input fields are missing: see README.md')
INPUT_IDS={r['id'] for r in rows}
if len(INPUT_IDS)!=len(rows):raise ValueError('Input IDs must be unique')
locks={};guard=threading.Lock();SOURCE_DATES={}
def remembered(result):
 fetched=result.get('checkedAt')
 for u in [result.get('url'),result.get('finalURL')]:
  if u:SOURCE_DATES[u]=fetched
 return result
def source_asof(url):
 fetched=SOURCE_DATES.get(url)
 return '掲載日時不明（'+str(fetched)+'取得）' if fetched else '掲載日時不明（取得日記録なし）'
TLS=ssl.create_default_context();LOCAL=threading.local()
def client(fresh=False):
 old=getattr(LOCAL,'client',None)
 if fresh or old is None or time.time()-getattr(LOCAL,'created',0)>CLIENT_AGE:
  if old:
   try:old.close()
   except:pass
  LOCAL.client=httpx.Client(proxy=PROXY,trust_env=False,verify=TLS,follow_redirects=True,timeout=TIMEOUT,limits=httpx.Limits(max_connections=2,max_keepalive_connections=2,keepalive_expiry=15))
  LOCAL.created=time.time()
 return LOCAL.client

class HostLimiter:
 def __init__(self, limit):
  self.limit=limit;self.active=0;self.condition=threading.Condition()
 def __enter__(self):
  with self.condition:
   while self.active>=self.limit:self.condition.wait()
   self.active+=1
  return self
 def __exit__(self,*args):
  with self.condition:
   self.active-=1;self.condition.notify_all()
 def reduce(self,limit):
  with self.condition:
   self.limit=min(self.limit,limit);self.condition.notify_all()
slow_hosts={}
def norm(x):return re.sub(r'[\s\u3000・･]','',unicodedata.normalize('NFKC',x or ''))
def cachepath(u):return CACHE/(hashlib.sha256(u.encode()).hexdigest()+'.json')
def fetch(url):
 original=urllib.parse.urldefrag(url)[0]
 url='https://'+original[7:] if original.startswith('http://') else original
 path=cachepath(url)
 if not REFRESH and path.exists():
  cached=json.loads(path.read_text())
  if cached.get('status')=='取得失敗' and (not cached.get('error') or 'CERTIFICATE_VERIFY_FAILED' in cached.get('error','')):path.unlink(missing_ok=True)
  else:return remembered(cached)
 if not REFRESH and original!=url:
  oldpath=cachepath(original)
  if oldpath.exists():
   old=json.loads(oldpath.read_text())
   if old.get('status')=='取得成功':return remembered(old)
 host=urllib.parse.urlsplit(url).hostname
 with guard:sem=locks.setdefault(host,HostLimiter(PER_HOST))
 with sem:
  if not REFRESH and path.exists():
   cached=json.loads(path.read_text())
   if cached.get('status')=='取得失敗' and (not cached.get('error') or 'CERTIFICATE_VERIFY_FAILED' in cached.get('error','')):path.unlink(missing_ok=True)
   else:return remembered(cached)
  out=None
  for attempt in range(RETRIES+1):
   try:
    if host in slow_hosts:time.sleep(1)
    request_url=original if attempt>0 and original!=url else url
    resp=client(fresh=attempt>0).get(request_url,headers={'User-Agent':'Mozilla/5.0 (public elected representative profile research)'})
    if resp.status_code in [429,503]:
     with guard:
      if host not in slow_hosts:
       slow_hosts[host]=True
       sem.reduce(min(2,PER_HOST))
     time.sleep(5)
    resp.raise_for_status()
    if 'text/html' not in resp.headers.get('Content-Type','text/html'):raise ValueError('non-HTML source')
    raw=resp.content[:2_500_000];charset=resp.encoding;final=str(resp.url)
    soup=BeautifulSoup(raw,'html.parser',from_encoding=charset)
    out={'url':url,'finalURL':final,'status':'取得成功','html':str(soup),'checkedAt':DATE};break
   except Exception as e:
    out={'url':url,'status':'取得失敗','error':type(e).__name__+': '+str(e)[:180],'checkedAt':DATE}
    if isinstance(e,httpx.HTTPStatusError) and e.response.status_code in [404,410]:break
  path.write_text(json.dumps(out,ensure_ascii=False))
  return remembered(out)
PRIVATE=re.compile(r'娘|息子|孫|夫婦|[一二三四五六0-9]児の|[一二三四五六0-9]男[一二三四五六0-9]女|生まれ|生れ|生年月日|誕生|\d{4}年[^。]{0,8}出生|住所|電話|FAX|メール|[\w.+-]+@[\w.-]+|〒|\d{2,4}[-ー－]\d{2,4}[-ー－]\d{3,4}|家族|妻|夫と|長男|長女|次男|次女|二児|三児|父親|母親|両親|結婚|離婚|配偶者')
RULES=[('career','職歴',r'議員.{0,8}(?:事務所|秘書)|議員団.{0,5}(?:事務|職員)|議員事務|議員秘書'),('community','PTA・地域活動',r'PTA|ＰＴＡ|自治会|町内会|子ども会|消防団|民生委員'),('career','学歴',r'卒業|卒|修了|中退|入学|在学|(?:大学|高校|高等学校|専門学校).{0,20}出身'),('organization','団体・議会等の役職',r'会長|副会長|理事|代表|委員長|副委員長|議長|副議長|監事|事務局長|幹事|支部長|団長|書記|会員|組合|委員(?!会)'),('career','議員歴',r'初当選|当選|[0-9一二三四五六七八九十]+期|議員歴|議員に就任|議員を務め|議員として活動|(?:市|区|町|村|府|県|都|道)議会議員'),('career','職歴',r'勤務|入社|退職|職員|社員|教員|教諭|教師|看護師|保育士|医師|弁護士|労働|従事|就職|入職|開業|経営|所長|院長|会社|助手|自営|農業|公務|職歴|民商|新婦人|民医連|労連|相談員')]
def factual_parts(text):
 text=unicodedata.normalize('NFKC',text);text=re.sub(r'[ \t\r]+',' ',text)
 parts=re.split(r'[。\n\r●■◆]|(?<=\S)[、；;](?=\S)',text)
 return [p.strip(' ・/／　:：●○■◆') for p in parts if 3<len(p.strip())<230]
def facts(text,url,person,section,source_type,selector,policy=False):
 out=[]
 for part in factual_parts(text):
  if PRIVATE.search(part):continue
  if not policy and re.search(r'と思い|と思って|と思う|と考え|と感じ|先生方|人々|皆さん|みなさん|仕事とは',part):continue
  if policy:
   if len(part)>=10 and not re.search(r'ました|開催|参加|集会|講演|報告|写真|動画|コメント',part) and re.search(r'無償化|支援|拡充|充実|廃止|削減|反対|守る|めざ|目指|取り組|とりく|負担軽減|子育て|防災|減税',part):
    out.append({'category':'policy','title':'本人が掲げる政策','summary':part[:160],'period':'掲載時点・時期不明','url':url,'sourceType':source_type,'asOf':source_asof(url),'checkedAt':DATE,'evidence':{'matchedName':person,'sectionHeading':section,'selector':selector,'rule':'本人一致済み個人ページの政策・公約区画の記載（達成実績ではない）'}})
   continue
  if re.search(r'facebook|twitter|copyright|記事を読む|続きを読む|シェア|コメント|ブログ村|このページ',part,re.I):continue
  for category,title,pattern in RULES:
   if re.search(pattern,part):
    if re.search(r'目指|めざ|したい|します|していき|が必要|求め|実現|反対|廃止|無償化',part):break
    # Facts contain a concrete school, role, employment or election history.
    out.append({'category':category,'title':title,'summary':part.replace('現在','掲載時点で'),'period':next(iter(re.findall(r'(?:19|20)\d{2}年(?:\d{1,2}月)?',part)),'掲載時点・時期不明'),'url':url,'sourceType':source_type,'asOf':source_asof(url),'checkedAt':DATE,'evidence':{'matchedName':person,'sectionHeading':section,'selector':selector,'rule':'本人一致済みのプロフィール区画内の具体的経歴・役職記載'}});break
  else:
   if policy and len(part)>=10 and re.search(r'実現|無償化|支援|拡充|充実|廃止|削減|反対|守|めざ|目指|取り組|とりく|負担|子育て|医療|福祉|教育|防災|減税',part):
    out.append({'category':'policy','title':'本人が掲げる政策','summary':part[:160],'period':'掲載時点・時期不明','url':url,'sourceType':source_type,'asOf':source_asof(url),'checkedAt':DATE,'evidence':{'matchedName':person,'sectionHeading':section,'selector':selector,'rule':'本人一致済み個人ページの政策・公約区画の記載（達成実績ではない）'}})
 return out[:12]
def identity(soup,person):
 aliases=[person['name']]+person.get('sourceNames',[])
 headings=[soup.title.get_text(' ',strip=True) if soup.title else '']+[h.get_text(' ',strip=True) for h in soup.select('h1')]
 return any(norm(n) in norm(h) for n in aliases for h in headings if n)
def hp_source_type(url):
 host=(urllib.parse.urlsplit(url).hostname or '').lower()
 if host=='jcp.or.jp' or host.endswith('.jcp.or.jp'):return '政党公式'
 if 'jcp' in host or 'kyousan' in host or 'kyosan' in host:return '政党関連（党公式リンク先）'
 return '本人公式'
def website_info(url):
 party=hp_source_type(url)!='本人公式'
 return {'url':url,'title':'党サイト内の本人ページ' if party else '本人公式ページ（党個人プロフィールからリンク）','kind':'party' if party else 'personal'}
def personal_extract(soup,url,person):
 """Only titled/heading-confirmed personal page; no generic blog articles or footer."""
 soup=BeautifulSoup(str(soup),'html.parser')
 if not identity(soup,person):return [],'本人一致未確認'
 group_scope=bool(re.search(r'議員団|[市区町村]議団|会派|党の(?:政策|実績|公約)',(soup.title.get_text(' ',strip=True) if soup.title else '')+' '+urllib.parse.unquote(url)))
 for el in soup.select('script,style,header,footer,nav,aside,.sidebar,#sidebar,.comments,#comments'):el.decompose()
 root=soup.select_one('main') or soup.select_one('article') or soup.body or soup
 out=[]
 # Heading-bound profile/policy sections. Stop at the next same-or-higher heading.
 for h in root.find_all(re.compile('^h[1-6]$')):
  heading=h.get_text(' ',strip=True)
  if not re.search(r'プロフィール|略歴|経歴|学歴|職歴|自己紹介|歩み|政策|公約|お約束|重点',heading):continue
  if group_scope and re.search(r'政策|公約|約束|重点',heading):continue
  text=[];level=int(h.name[1])
  for sib in h.next_siblings:
   if getattr(sib,'name',None) and re.match('^h[1-6]$',sib.name) and int(sib.name[1])<=level:break
   val=sib.get_text('\n',strip=True) if hasattr(sib,'get_text') else str(sib).strip()
   text.append(val)
   if sum(len(t) for t in text)>6000:break
  out+=facts('\n'.join(text),url,person['name'],heading,hp_source_type(url),'heading-following-siblings',bool(re.search(r'政策|公約|約束|重点',heading)))
 # Standalone profile page has personal identity plus page title/profile heading.
 title=(soup.title.get_text(' ',strip=True) if soup.title else '')
 if not out and re.search(r'プロフィール|略歴|経歴|自己紹介|政策|公約|約束',title) and not (group_scope and re.search(r'政策|公約|約束',title)):
  out+=facts(root.get_text('\n',strip=True)[:9000],url,person['name'],title,hp_source_type(url),'main/article body on named profile page',bool(re.search(r'政策|公約|約束',title)))
 return out[:16],'本人一致確認'
def fallback_enrich(person,result):
 attempted=[];found=[];note=[];w=person.get('website',{});home=w.get('url') if isinstance(w,dict) else w
 initial=home or person.get('sourceURL') or next((x.get('url') for x in person.get('sources',[]) if x.get('url')),None)
 if not initial:
  result['enrichment']={'checkedAt':DATE,'status':'追加根拠未確認','attempted':[],'note':'党DB・本人HP・一次資料のURLが入力に収録されていない。経歴がないと判断したものではない。'};return result
 targets=[initial];visited=set()
 while targets and len(visited)<3:
  url=targets.pop(0)
  if url in visited:continue
  visited.add(url);f=fetch(url);attempted.append({k:f[k] for k in ['url','status','error'] if k in f})
  if f['status']!='取得成功':continue
  soup=BeautifulSoup(f['html'],'html.parser');final=f.get('finalURL',url);host=urllib.parse.urlsplit(final).hostname or ''
  fs,check=personal_extract(soup,final,person)
  administrative=host.endswith('.lg.jp') or host.endswith('.go.jp')
  if administrative:
   for x in fs:x['sourceType']='行政・議会'
  found+=fs
  if home and check=='本人一致確認':result['website']=website_info(final)
  for a in soup.select('a[href]'):
   label=a.get_text(' ',strip=True)
   if len(label)>60:continue
   named=any(norm(n) in norm(label) for n in [person['name']]+person.get('sourceNames',[]) if n)
   if not (re.search(r'プロフィール|略歴|経歴|自己紹介|政策|公約|お約束',label) or named):continue
   link=urllib.parse.urldefrag(urllib.parse.urljoin(final,a['href']))[0];parsed=urllib.parse.urlsplit(link)
   if parsed.scheme not in ['http','https'] or parsed.hostname!=host or link in visited or link in targets:continue
   if re.search(r'\.(pdf|jpg|png|zip)$|/search/|/tag/|/tags/|/category/|/label/|/archives/',link,re.I):continue
   targets.append(link)
   if len(targets)+len(visited)>=3:break
 seen=set();result['findings']=[]
 for x in found:
  key=norm(x['summary'])
  if key not in seen:seen.add(key);result['findings'].append(x)
 result['enrichment']={'checkedAt':DATE,'status':'情報追加' if found else ('取得失敗' if all(a['status']=='取得失敗' for a in attempted) else '追加根拠未確認'),'attempted':attempted,'note':'党個人DBのURL未収録のため、既存の本人HPまたは行政等の一次資料から個別に実取得。氏名が一致しないページ、共有名簿の汎用本文は経歴に転用しない。未確認は経歴がないことを意味しない。'}
 return result
def enrich(person):
 result={'id':person['id'],'municipalityCode':person['municipalityCode'],'name':person['name'],'findings':[]}
 attempted=[];notes=[];seen=set()
 def add_attempt(f):attempted.append({k:f[k] for k in ['url','status','error'] if k in f})
 w=person.get('website',{});u=w.get('url') if isinstance(w,dict) else w
 if not u or 'jcp.or.jp/list/member/' not in u:
  u=next((f['url'] for f in person.get('findings',[]) if '/list/member/' in f.get('url','')),None)
 if not u:
  return fallback_enrich(person,result)
 f=fetch(u);add_attempt(f)
 if f['status']=='取得成功':
  soup=BeautifulSoup(f['html'],'html.parser');heading=soup.select_one('.shoukai-name')
  actual=''.join(heading.find_all(string=True,recursive=False)).strip() if heading else ''
  municipality=next((tr.get_text(' ',strip=True) for tr in soup.select('.shoukai-descliptions tr') if tr.find('th') and '自治体' in tr.find('th').get_text()),'')
  locality_ok=not municipality or (norm(person.get('municipalityName','')) in norm(municipality) and norm(person.get('prefecture','')) in norm(municipality))
  if not locality_ok or not any(norm(n)==norm(actual) for n in [person['name']]+person.get('sourceNames',[]) if n):notes.append('党プロフィールの本人氏名・自治体一致を確認できず自動補完を保留。')
  else:
   bio=soup.select_one('.shoukai-ryakureki')
   if bio:result['findings']+=facts(bio.get_text('\n',strip=True),f.get('finalURL',u),person['name'],'略歴','政党公式','.shoukai-ryakureki')
   links=soup.select('.shoukai-link a[title="HP"]')
   if links:
    hp=urllib.parse.urljoin(u,links[0]['href']);hf=fetch(hp);add_attempt(hf)
    if hf['status']=='取得成功':
     hs=BeautifulSoup(hf['html'],'html.parser');hurl=hf.get('finalURL',hp)
     extracted,check=personal_extract(hs,hurl,person);result['findings']+=extracted;notes.append('本人HP: '+check)
     if check=='本人一致確認':
      result['website']=website_info(hurl)
     # Profile and policies: at most two explicit links, same host, no guessed URLs.
     targets=[]
     for a in hs.select('a[href]'):
      label=a.get_text(' ',strip=True)
      if not re.search(r'プロフィール|略歴|経歴|自己紹介|政策|公約|お約束',label) or len(label)>40:continue
      link=urllib.parse.urljoin(hurl,a['href']);link=urllib.parse.urldefrag(link)[0]
      if urllib.parse.urlsplit(link).hostname!=urllib.parse.urlsplit(hurl).hostname or link.rstrip('/')==hurl.rstrip('/') or link in targets:continue
      if re.search(r'\.(pdf|jpg|png|zip)$|/search/|/tag/|/tags/|/category/|/label/|/archives/',link,re.I):continue
      targets.append(link)
      if len(targets)>=2:break
     for link in targets:
      sf=fetch(link);add_attempt(sf)
      if sf['status']=='取得成功':
       ss=BeautifulSoup(sf['html'],'html.parser');fs,ch=personal_extract(ss,sf.get('finalURL',link),person);result['findings']+=fs
       if ch=='本人一致確認' and 'website' not in result:result['website']=website_info(sf.get('finalURL',link))
     if check!='本人一致確認':notes.append('個人HPの本文は氏名一致未確認のため事実の取得を保留。明示プロフィールリンク先は個別に本人照合。')
   else:notes.append('党個人プロフィールに本人HPリンクの掲載なし。')
 unique=[]
 for x in result['findings']:
  k=norm(x['summary'])
  if k not in seen:seen.add(k);unique.append(x)
 result['findings']=unique
 existing={norm(f.get('summary','')) for f in person.get('findings',[])}
 added=any(norm(f['summary']) not in existing for f in unique)
 status='情報追加' if added else ('既存内容確認' if unique else ('取得失敗' if all(a['status']=='取得失敗' for a in attempted) else '追加根拠未確認'))
 result['enrichment']={'checkedAt':DATE,'status':status,'attempted':attempted,'note':' '.join(notes)+' 未取得・未確認は経歴や役職がないことを意味しない。掲載日時不明の情報から現在の在職・所属や次回立候補は推定しない。'}
 return result
def audit_shared_sources(output):
 owners=collections.defaultdict(set)
 for r in output:
  for f in r['findings']:
   if '/list/member/' not in f['url']:owners[f['url']].add(r['id'])
  if r.get('website'):owners[r['website']['url']].add(r['id'])
 shared={u for u,ids in owners.items() if len(ids)>1}
 policy_urls={f['url'] for r in output for f in r['findings'] if f['category']=='policy'}
 group_urls=set();group_pattern=r'議員団|[市区町村]議団|会派|党の(?:政策|実績|公約)'
 for p in CACHE.glob('*.json'):
  try:c=json.loads(p.read_text())
  except:continue
  matched={c.get('url'),c.get('finalURL')} & policy_urls
  if not matched or not c.get('html'):continue
  soup=BeautifulSoup(c['html'],'html.parser')
  title=(soup.title.get_text(' ',strip=True) if soup.title else '')+' '+' '.join(h.get_text(' ',strip=True) for h in soup.select('h1'))
  if re.search(group_pattern,title):group_urls|=matched
 dropped=0
 for r in output:
  keep=[]
  for f in r['findings']:
   if PRIVATE.search(f['summary']):dropped+=1
   elif f['title']=='学歴' and not re.search(r'卒業|卒|修了|中退|入学|在学|(?:大学|高校|高等学校|専門学校).{0,20}出身',f['summary']):dropped+=1
   elif f['title']=='議員歴' and not re.search(r'当選|[0-9一二三四五六七八九十]+期|就任|務め|歴任|(?:19|20)[0-9]{2}年',f['summary']):dropped+=1
   elif f['category']!='policy' and re.search(r'と思い|と思って|と思う|と考え|と感じ|先生方|人々|皆さん|みなさん|仕事とは',f['summary']):dropped+=1
   elif f['category']=='policy' and (f['url'] in group_urls or re.search(group_pattern,f['evidence']['sectionHeading']+' '+urllib.parse.unquote(f['url']))):dropped+=1
   elif f['url'] in shared and norm(r['name']) not in norm(f['evidence']['sectionHeading']):dropped+=1
   else:keep.append(f)
  if len(keep)!=len(r['findings']):r['enrichment']['note']+=' 共有ページの汎用本文・党や議員団の共同政策/実績・私的事項を個人事実として採用しない最終監査を適用。'
  r['findings']=keep
  if r.get('website',{}).get('url') in shared:del r['website']
  if not keep and r['enrichment']['status']=='情報追加':r['enrichment']['status']='追加根拠未確認'
 return dropped
if __name__=='__main__':
 donepath=PROGRESS;done={}
 if ('--reparse' in sys.argv or os.environ.get('JCP_REPARSE','0')=='1') and donepath.exists():donepath.rename(donepath.with_name(donepath.name+'.previous-'+str(int(time.time()))))
 if donepath.exists():
  for line in donepath.read_text().splitlines():
   try:
    r=json.loads(line)
    if r['id'] in INPUT_IDS and r.get('enrichment',{}).get('checkedAt')==DATE:done[r['id']]=r
   except:pass
 todo=[r for r in rows if r['id'] not in done]
 limit=next((int(a.split('=',1)[1]) for a in sys.argv if a.startswith('--max-new=')),int(os.environ['JCP_MAX_NEW']) if os.environ.get('JCP_MAX_NEW') else None)
 if limit:todo=todo[:limit]
 started=time.time()
 with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool,donepath.open('a') as log:
  pending={pool.submit(enrich,r):r for r in todo}
  for fut in concurrent.futures.as_completed(pending):
   p=pending[fut]
   try:r=fut.result()
   except Exception as e:r={'id':p['id'],'municipalityCode':p['municipalityCode'],'name':p['name'],'findings':[],'enrichment':{'checkedAt':DATE,'status':'取得失敗','attempted':[],'note':'処理失敗: '+str(e)[:160]+'。経歴がないことを意味しない。'}}
   done[r['id']]=r;log.write(json.dumps(r,ensure_ascii=False)+'\n');log.flush()
   if len(done)%20==0:print('PROGRESS',len(done),'/',len(rows),'added',sum(bool(x['findings']) for x in done.values()),'elapsed',round(time.time()-started),flush=True)
 if len(done)<len(rows):
  print('CHECKPOINT',len(done),'/',len(rows),flush=True);sys.exit(0)
 output=[done[r['id']] for r in rows]
 shared_dropped=audit_shared_sources(output)
 OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
 report={'total':len(output),'sharedPageFindingsDropped':shared_dropped,'statusCounts':dict(collections.Counter(r['enrichment']['status'] for r in output)),'findingCount':sum(len(r['findings']) for r in output),'websiteCount':sum('website' in r for r in output),'checkedAt':DATE}
 REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('DONE',report,flush=True)
