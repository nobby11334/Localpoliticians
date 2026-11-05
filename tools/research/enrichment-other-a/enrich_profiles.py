#!/usr/bin/env python3
"""Conservative, person-scoped official/profile enrichment; stdlib+lxml.
Eight workers, per-host concurrency two, one retry. Private contact/birth/family fields excluded.
"""
import concurrent.futures,threading,urllib.request,urllib.parse,hashlib,json,pathlib,re,time,unicodedata,datetime,collections,sys
from lxml import html,etree
import httpx,os,ssl,signal
signal.signal(signal.SIGINT,lambda *args:os._exit(130))
def httpclient():
 if not hasattr(local,'http'):
  local.http=httpx.Client(proxy=os.environ.get('POLITICIAN_RESEARCH_PROXY')or os.environ.get('HTTPS_PROXY'),trust_env=False,verify=ssl.create_default_context(),follow_redirects=True,timeout=httpx.Timeout(14,connect=8,pool=8),limits=httpx.Limits(max_connections=None,max_keepalive_connections=8),headers={'User-Agent':'Mozilla/5.0 (public civic profile research)','Accept-Language':'ja'})
 return local.http

B=pathlib.Path(os.environ.get('POLITICIAN_RESEARCH_DIR',str(pathlib.Path(__file__).parent)))
INPUT=pathlib.Path(os.environ.get('POLITICIAN_RESEARCH_INPUT',str(B/'input.json')))
OUTPUT=pathlib.Path(os.environ.get('POLITICIAN_RESEARCH_OUTPUT',str(B/'enriched.json')))
CACHE=pathlib.Path(os.environ.get('POLITICIAN_RESEARCH_CACHE',str(pathlib.Path(__import__('tempfile').gettempdir())/'civic-profile-cache')))
REFERENCE_DIR=pathlib.Path(os.environ.get('POLITICIAN_RESEARCH_REFERENCE_DIR',str(INPUT.parent)))
CHECKED=os.environ.get('POLITICIAN_RESEARCH_CHECKED_AT',datetime.date.today().isoformat())
WORKERS=min(8,max(1,int(os.environ.get('POLITICIAN_RESEARCH_WORKERS','8'))))
HOST_LIMIT=min(2,max(1,int(os.environ.get('POLITICIAN_RESEARCH_HOST_LIMIT','2'))))
REFRESH='--refresh' in sys.argv
RUN_URLS=set()
CACHE.mkdir(parents=True,exist_ok=True);OUTPUT.parent.mkdir(parents=True,exist_ok=True)
PEOPLE=json.loads(INPUT.read_text())
if not isinstance(PEOPLE,list)or any(not isinstance(p,dict)or not all(p.get(k)for k in ['id','name','municipalityCode'])for p in PEOPLE):raise ValueError('Input must be a JSON array of person records with id, name and municipalityCode.')
if len({p['id']for p in PEOPLE})!=len(PEOPLE):raise ValueError('Duplicate input IDs are not allowed.')
local=threading.local();lock=threading.Lock();hostlocks={};urlocks={}

def cachewrite(path,payload):
 temp=path.with_name(path.name+'.'+str(os.getpid())+'.'+str(threading.get_ident())+'.tmp')
 temp.write_text(json.dumps(payload,ensure_ascii=False));temp.replace(path)

def norm(s):return re.sub(r'[\s\u200b\ufeff・･]+','',unicodedata.normalize('NFKC',s or ''))
def txt(e):return re.sub(r'\s+',' ',e.text_content()).strip()if isinstance(e.tag,str)else ''
def domainsame(a,b):return urllib.parse.urlsplit(a).netloc==urllib.parse.urlsplit(b).netloc

def get(url):
 url=urllib.parse.urldefrag(url)[0]
 if not url.startswith(('https://','http://')):return None,'非HTTPリンク'
 key=hashlib.sha256(url.encode()).hexdigest();p=CACHE/(key+'.json')
 with lock:
  ul=urlocks.setdefault(url,threading.Lock());sem=hostlocks.setdefault(urllib.parse.urlsplit(url).netloc,threading.Semaphore(HOST_LIMIT))
 with ul:
  if p.exists()and(not REFRESH or url in RUN_URLS):
   try:j=json.loads(p.read_text())
   except (ValueError,OSError):j={}
   if j and not (j.get('error')or'').startswith('PoolTimeout'):
    data=dict(j['data'])if j.get('data')else None
    if data:data['cacheRead']=True
    if data and data.get('url')and data['url']!=url:
     alias=CACHE/(hashlib.sha256(data['url'].encode()).hexdigest()+'.json')
     if not alias.exists():cachewrite(alias,j)
    return data,j.get('error')
  if '--cached-only' in sys.argv:return None,'本文キャッシュなし（再取得が必要）'
  err=None;data=None
  for attempt in range(2):
   try:
    with sem:
     r=httpclient().get(url)
     if r.status_code==429:
      time.sleep(min(15,int(r.headers.get('retry-after','5'))if r.headers.get('retry-after','5').isdigit()else 5))
     r.raise_for_status();raw=r.content[:2500000];ctype=r.headers.get('Content-Type','');em=re.search(r'charset=([^; ]+)',ctype);enc=em.group(1).strip(chr(34)+chr(39))if em else None
    if not any(x in ctype for x in ['html','text/','csv','xml']):err='本文解析対象外: '+ctype;break
    if enc:
     try:s=raw.decode(enc)
     except:s=raw.decode('utf-8','replace')
    else:
     m=re.search(br'charset=["\']?([\w-]+)',raw[:5000],re.I);enc=m.group(1).decode()if m else 'utf-8'
     try:s=raw.decode(enc)
     except:s=raw.decode('utf-8','replace')
    data={'text':s,'url':str(r.url),'contentType':ctype,'fetchedAt':datetime.datetime.now(datetime.timezone.utc).date().isoformat()};err=None;break
   except Exception as e:err=type(e).__name__+': '+str(e)
  cachewrite(p,{'data':data,'error':err});RUN_URLS.add(url);return data,err

def tree(data):
 try:
  if 'csv' in data.get('contentType',''):
   import csv,io
   rows=list(csv.reader(io.StringIO(data['text'].lstrip('\ufeff'))));t=html.Element('table')
   for row in rows:
    tr=etree.SubElement(t,'tr')
    for cell in row:etree.SubElement(tr,'td').text=cell
   return t
  t=html.fromstring(re.sub(r'<\?xml[^>]*\?>','',data['text']));t.make_links_absolute(data['url'])
  for e in t.xpath('//script|//style|//nav|//footer|//header|//noscript|//aside|//blockquote|//rt|//rp'):e.drop_tree()
  return t
 except:return None

def names(p):return list(set(norm(x)for x in [p['name']]+(p.get('sourceNames')or[])if x))
def hasname(s,ns):return any(n and n in norm(s)for n in ns)
ALLNAMES=set(n for person in PEOPLE for n in names(person)if len(n)>=3)
for sourcefile in REFERENCE_DIR.glob('*.json'):
 try:
  vals=json.loads(sourcefile.read_text())
  if isinstance(vals,dict):vals=vals.get('people',[])
  if isinstance(vals,list):
   for person in vals:
    if isinstance(person,dict)and person.get('name'):
     for n in names(person):
      if len(n)>=3:ALLNAMES.add(n)
 except:pass
NAMEPAT=re.compile('|'.join(re.escape(n)for n in sorted(ALLNAMES,key=len,reverse=True))or r'(?!)')
def members(s):return set(NAMEPAT.findall(norm(s)))
def scope(t,ns,url):
 title=' '.join(t.xpath('//title/text()'));h1s=t.xpath('//h1');h1=' '.join(txt(x)for x in h1s)
 sharedurl=bool(re.search(r'/election/\d+/?$|/member_tag/|/giinlist|/members?/?$|kaiha|50on|gojuon',url))
 first_h2=t.xpath('//h2[1]');descriptor=title+' '+h1+' '+(txt(first_h2[0])if first_h2 else '')
 sharedurl=sharedurl or any(w in descriptor for w in ['一覧','名簿','会派別','50音','五十音','定数','定員','選挙情報','選挙結果']) or (len(set(norm(txt(h))for h in h1s))>1)
 own=set(ns);topnames=members(title+' '+h1)
 individual=(hasname(title,ns)or (len(h1s)==1 and hasname(h1,ns)))and not sharedurl and not any(n not in own for n in topnames) and len(h1s)<=1
 if not individual and not sharedurl:
  subject_headings=[txt(h)for h in t.xpath('//h1|//h2|//h3|//h4')if len(txt(h))<100]
  subject_headings += [a for a in t.xpath('//img/@alt')if len(a)<100]
  subjectnames=members(' '.join(subject_headings))
  individual=bool(subjectnames.intersection(own))and not any(n not in own for n in subjectnames)
 if individual:return t,True
 candidates=[]
 for e in t.xpath('//h1|//h2|//h3|//h4|//dt|//td|//a|//strong'):
  if hasname(txt(e),ns)and len(txt(e))<100:candidates.append(e)
 if not candidates:return None,False
 root=html.Element('div');seen=set()
 for e in candidates:
  anc=e
  for _ in range(6):
   par=anc.getparent()
   if par is None:break
   st=txt(par)
   if len(st)>3500 or any(n not in own for n in members(st)):break
   anc=par
   if par.tag in ['tr','article']:break
  # Shared source extraction is link-only. Never harvest biography from this scope.
  ss=html.tostring(anc)
  if ss not in seen:root.append(html.fromstring(ss));seen.add(ss)
 return root,False

BADHOST=['twitter.com','x.com','facebook.com','instagram.com','youtube.com','youtu.be','line.me','t.co','google.com','google.co.jp']
BADPATH=['/cdn-cgi/','mailto:','tel:','javascript:','/images/','/documents/']

def links(sc,base,ns,individual=False):
 out=[]
 for a in sc.xpath('.//a[@href]'):
  u=a.get('href');s=' '.join([txt(a),a.get('title',''),a.get('aria-label',''),' '.join(a.xpath('.//img/@alt'))]);host=urllib.parse.urlsplit(u).netloc
  context=''
  for par in list(a.iterancestors())[:3]:
   st=txt(par)
   if len(st)<=450 and par.tag in ['tr','p','li','dd','div']:context=st
   if par.tag=='tr':break
  if a.getparent() is not None and a.getparent().tag=='dd':
   prior=a.getparent().getprevious()
   if prior is not None and prior.tag=='dt':context+=' '+txt(prior)
  if not u.startswith(('http://','https://'))or any(x in host for x in BADHOST)or any(x in u for x in BADPATH):continue
  if re.search(r'\.(?:pdf|jpg|png|zip|csv|xlsx?)(?:\?|$)',u,re.I):continue
  personal=any(x in s+' '+context for x in ['ホームページ','公式サイト','WEB','Web','HP','ウェブサイト']) or bool(re.search(r'homepage|website',s,re.I)) or hasname(s,ns)
  profile=any(x in norm(s).lower()for x in ['プロフィール','経歴','略歴','自己紹介','profile','about','政策','公約','ビジョン','policy'])
  if personal or profile or (not individual and re.search(r'/member/|/profile|/giin/|/senkyoku/|/members/',u)):
   score=(5 if profile else 0)+(7 if personal and not domainsame(u,base)else 3 if personal else 0)+(2 if not domainsame(u,base)else 0)
   if individual and domainsame(u,base) and profile and classify(base,{})=='本人発信':score+=10
   if urllib.parse.urldefrag(u)[0]!=urllib.parse.urldefrag(base)[0]:out.append((score,u,s))
 return sorted(set(out),reverse=True)

PRIV=re.compile(r'住所|所在地|連絡先|自宅|郵便番号|父親|母親|両親|祖父|祖母|\b0\d{1,4}[-ー]\d{1,4}[-ー]\d{3,4}\b|\d{3}-\d{4}|(?:19|20)\d{2}年\d{1,2}月\d{1,2}日\s*生|電話|FAX|ファックス|〒|メール|生年月日|誕生|生まれ|出身地|家族|妻|夫婦|長男|長女|次男|次女|配偶者|趣味|血液型|身長|体重|[\w.+-]+@[\w.-]+')
FACT=re.compile(r'卒業|修了|中退|入学|入社|入庁|入行|入職|入庫|採用|着任|就任|退社|勤務|就職|退職|経営|創業|設立|弁護士|税理士|看護師|薬剤師|教員|教師|秘書|PTA|ＰＴＡ|会長|理事|顧問|相談役|事務局長|初当選|当選|市長|区長|町長|村長|知事|市会議員|市議|区議|町議|村議|県議|都議|衆議院|参議院|監査委員|議長|委員長|博士|修士|幹事長|支部長|政調|入党|自治会|町会|消防団|民生委員|児童委員|保護司|防災士')
LABEL=re.compile(r'略歴|経歴|学歴|職歴|主な役職|資格|当選回数|議員歴|プロフィール|主な活動|地域活動')
POLICY=re.compile(r'政策|公約|基本方針|ビジョン|マニフェスト|政治信条')

def facts(sc,p,url,individual,stype):
 if not individual:return []
 ns=names(p);out=[];seen=set();existing=[norm(f.get('summary','')+f.get('title',''))for f in p.get('findings',[])]
 def put(s,title,cat,section=None):
  s=re.sub(r'^[\s・●○▶■◆]+','',s).strip();s=re.sub(r'^[（(]?\d{1,2}[)）.．、]\s*','',s);s=re.sub(r'[\s\u200b]+',' ',s)
  if not s or len(s)<4 or len(s)>115 or PRIV.search(s):return
  if any(n not in set(ns) for n in members(s)):return
  if s.count('。')>2:return
  if any(x in s for x in ['お問い合わせ','問合せ','選挙区','クリック','詳細はこちら','写真','ログイン','関連記事','一覧を見る']):return
  nn=norm(s)
  if nn in seen or any(nn in e for e in existing):return
  seen.add(nn)
  if cat=='career':
   if re.search(r'PTA|ＰＴＡ|町会|自治会|父母の会|消防団|民生委員|児童委員',s):cat='community'
   elif re.search(r'理事|顧問|相談役',s):cat='organization'
  if cat=='policy':
   themes=[theme for theme in ['子育て','教育','防災','高齢者','福祉','医療','交通','道路','行政改革','財政','産業','商工','環境','脱炭素','給食','学校','公園','バリアフリー','住宅','物価','障害']if theme in s]
   if not themes:return
   summary='政策・取り組みの掲載項目で'+'・'.join(themes[:4])+'に言及している。'
   title='掲載する政策・取り組み：'+'・'.join(themes[:4])
  else:summary=s.rstrip('。')+'とプロフィールに記載。'
  period='掲載時点（開始・終了時期は本文で確認できる範囲のみ）'
  years=re.findall(r'(?:19|20)\d{2}年|(?:昭和|平成|令和)\s*\d+年',s)
  if years:period='・'.join(years[:3])+'の記載（当時の経歴・役職）'
  out.append({'category':cat,'title':title,'summary':summary,'period':period,'url':url,'sourceType':stype,'asOf':'資料掲載時点（更新日不明）','checkedAt':CHECKED,'evidence':{'matchedName':p['name'],'sectionHeading':section or title,'rule':'氏名が一致する単独人物ページの明示的経歴・政策節内。共有名簿・共有党ページの記述は不採用'}})
 # Labeled single-person table / definition-list fields are safe only within scope.
 for r in sc.xpath('.//tr'):
  c=r.xpath('./th|./td')
  if len(c)==2 and LABEL.search(txt(c[0])):
   label=txt(c[0]);s=txt(c[1])
   if FACT.search(s)or '当選回数'in label:
    for line in re.split(r'[\n\r]|[。；;]|(?=(?:19|20)\d{2}年|(?:昭和|平成|令和)\d+年)',s):
     if FACT.search(line)or '当選回数'in label:put(line,label,'community'if 'PTA'in line or 'ＰＴＡ'in line else 'organization'if any(x in line for x in ['理事','顧問','相談役'])else 'career')
 for dt in sc.xpath('.//dt'):
  if LABEL.search(txt(dt)):
   dd=dt.getnext()
   if dd is not None:
    s=txt(dd)
    if FACT.search(s):put(s,txt(dt),'career')
 # Only individual pages are eligible for generic biography sentences, and only
 # within explicit profile/history sections; shared page extraction stays labeled.
 if individual:
  for h in sc.xpath('.//h2|.//h3|.//h4'):
   label=txt(h)
   if LABEL.search(label)and not hasname(label,ns):
    rest=re.sub(r'プロフィール|略歴|主な|経歴|学歴|職歴|資格|当選回数|議員歴|地域活動|活動|私の|これまでの|[\W\d_]|Profile|PROFILE','',label)
    if len(rest)>2:continue
   if any(n not in set(ns)for n in members(label)):continue
   isbio=bool(LABEL.search(label));ispolicy=bool(POLICY.search(label))
   if not(isbio or ispolicy):continue
   content=[]
   for e in h.itersiblings():
    if e.tag in ['h1','h2','h3','h4']:break
    if isinstance(e.tag,str):content.append(e)
   for e in content:
    els=e.xpath('.//li|.//tr|.//p')or[e]
    for el in els:
     s=txt(el)
     if isbio and FACT.search(s):
      cat='community'if re.search('PTA|ＰＴＡ|町会|自治会|消防団',s)else 'organization'if any(x in s for x in ['理事','顧問','相談役'])else 'career'
      put(s,'本人略歴' if stype=='本人発信'else '公式プロフィール',cat,section=label)
     elif ispolicy and len(s)<115 and any(x in s for x in ['推進','支援','充実','整備','実現','無償','防災','子育て','教育','福祉','財政','経済','環境']):put(s,'掲げる政策','policy',section=label)
  # Timeline rows can be styled paragraphs on profile page without headings.
  title=' '.join(sc.xpath('.//title/text()'))
  if re.search('プロフィール|経歴|略歴|profile|about',title,re.I)or re.search('profile|about',url,re.I):
   for e in sc.xpath('.//li|.//tr|.//p'):
    s=txt(e)
    if len(s)<160 and FACT.search(s)and(re.search(r'\d{4}|昭和|平成|令和',s)or 'PTA'in s):put(s,'プロフィールの経歴','community'if'PTA'in s else 'career',section=title)
 return sorted(out,key=lambda f:({'community':0,'organization':1,'party':2,'policy':3,'career':4}.get(f['category'],5),bool(re.search('卒業|修了|入学',f['summary']))))[:24]

def classify(url,p):
 host=urllib.parse.urlsplit(url).netloc
 if '.lg.jp'in host or 'shigikai'in host or'gikai'in host:return '行政・議会'
 if any(x in host for x in ['cdp-japan.jp','o-ishin.jp','new-kokumin.jp','tokyo-jimin.jp','jimin.jp']):return '団体公式'
 return '本人発信'

CITYSEEDS={
'01100':['https://www.city.sapporo.jp/gikai/meibo/meibo-50on.html'],
'23100':['https://www.city.nagoya.jp/shikai/about/1030778/1030800.html'],
'14130':['https://www.city.kawasaki.jp/shisei/category/40-3-4-0-0-0-0-0-0-0.html'],
}
for person in PEOPLE:
 u=person.get('sourceURL','');code=person.get('municipalityCode')
 if '.lg.jp/'in u and not re.search(r'\.(?:pdf|csv|xlsx?)(?:$|\?)',u,re.I)and any(w in u for w in ['gikai','shikai','giin','meibo','council']):
  vals=CITYSEEDS.setdefault(code,[])
  if u not in vals and len(vals)<3:vals.append(u)
for seedfile in REFERENCE_DIR.glob('*.json'):
 try:
  vals=json.loads(seedfile.read_text())
  if isinstance(vals,dict):vals=vals.get('people',[])
  for person in vals:
   u=person.get('sourceURL','');code=person.get('municipalityCode')
   if '.lg.jp/' in u and not re.search(r'\.(?:pdf|csv|xlsx?)(?:$|\?)',u,re.I)and any(w in u for w in ['gikai','shikai','giin','meibo','council']):
    vals=CITYSEEDS.setdefault(code,[])
    if u not in vals and len(vals)<3:vals.append(u)
 except:pass

RESULTS={};progress=0
if OUTPUT.exists() and '--reparse' not in sys.argv and not REFRESH:
 try:RESULTS={p['id']:p for p in json.loads(OUTPUT.read_text())}
 except:pass

def process(p):
 ns=names(p);attempts=[];find=[];todo=[];visited=set();verified=False;website=None;confirmed_existing=False;used_previous_cache=set()
 w=p.get('website');w=w.get('url')if isinstance(w,dict)else w
 for u in [w,p.get('sourceURL')]+[s.get('url')for s in p.get('sources',[])][:2]+CITYSEEDS.get(p['municipalityCode'],[])[:2]:
  if u and u not in todo:todo.append(u)
 def fetchone(u,depth):
  nonlocal verified,website,confirmed_existing,used_previous_cache
  key=urllib.parse.urldefrag(u)[0]
  if key in visited:return []
  visited.add(key);data,err=get(u)
  if err:attempts.append({'url':u,'status':'取得失敗','error':err});return []
  if data.get('cacheSource')or data.get('cacheRead'):used_previous_cache.add(data.get('fetchedAt','取得日不明'))
  t=tree(data)
  if t is None:attempts.append({'url':u,'status':'取得失敗','error':'HTML本文を解析できず'});return []
  sc,ind=scope(t,ns,data['url'])
  if sc is None:attempts.append({'url':u,'status':'本人一致未確認'});return []
  verified=True;attempts.append({'url':u,'status':'本人一致確認（個別ページ）'if ind else'本人一致確認（共有ページの該当部分）'})
  if ind and classify(data['url'],p)=='本人発信'and not website:website={'url':data['url'],'title':p['name']+' 公式・本人サイト','kind':'本人発信'}
  if ind:
   body=norm(txt(sc))
   for old in p.get('findings',[]):
    if old.get('category')=='activity':continue
    oldtext=norm(old.get('summary',''));oldtext=re.sub(r'(?:と|を)?(?:本人)?プロフィールに記載[。.]?$','',oldtext)
    if 8<=len(oldtext)<=120 and oldtext in body:confirmed_existing=True
  newfacts=facts(sc,p,data['url'],ind,classify(data['url'],p))
  for fact in newfacts:
   fact['evidence']['retrievalURL']=u
   fact['evidence']['cacheKey']=hashlib.sha256(urllib.parse.urldefrag(u)[0].encode()).hexdigest()
   fact['evidence']['contentSha256']=hashlib.sha256(data['text'].encode('utf-8')).hexdigest()
  find.extend(newfacts)
  return links(sc,data['url'],ns,ind)
 candidates=[]
 for u in todo[:4]:candidates.extend(fetchone(u,0))
 # Bound traversal: four seed URLs plus at most four onward pages (depth two).
 for _,u,label in sorted(set(candidates),reverse=True)[:2]:
  more=fetchone(u,1)
  if len(visited)<7:
   for _,v,_ in more[:2]:
    if len(visited)<7:fetchone(v,2)
 unique=[];ks=set()
 for f in find:
  k=norm(f['summary'])
  if k not in ks:unique.append(f);ks.add(k)
 status='情報追加'if unique else '既存内容確認'if confirmed_existing else '追加根拠未確認'if verified else'取得失敗'if attempts and all(a['status']=='取得失敗'for a in attempts)else'追加根拠未確認'
 note='個人名が一致する単独人物ページの経歴・政策欄のみ採用。共有名簿・共有党ページの経歴は一切追加しない。既存の名簿掲載は追加扱いにしない。'
 if used_previous_cache:note+='取得済み本文（取得日：'+'・'.join(sorted(used_previous_cache))+'）を'+CHECKED+'に再点検した。'
 if p.get('candidate'):note+='候補者掲載の資料を含むため現職の根拠に転用しない。'
 if not verified:note+='取得したページで本人と一致する範囲を確認できず、追加情報は採用していない。'
 out={'id':p['id'],'municipalityCode':p['municipalityCode'],'name':p['name'],'findings':unique[:32],'enrichment':{'checkedAt':CHECKED,'status':status,'attempted':attempts,'note':note}}
 if website:out['website']=website
 return out

def save():
 vals=[RESULTS[p['id']]for p in PEOPLE if p['id']in RESULTS];tmp=OUTPUT.with_suffix('.tmp');tmp.write_text(json.dumps(vals,ensure_ascii=False,indent=2));tmp.replace(OUTPUT)

def main():
 global progress
 pending=[p for p in PEOPLE if p['id']not in RESULTS]
 pending.sort(key=lambda p:hashlib.sha256(p['id'].encode()).hexdigest())
 print('START',len(PEOPLE),'pending',len(pending),flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS)as ex:
  fs={ex.submit(process,p):p for p in pending}
  for f in concurrent.futures.as_completed(fs):
   p=fs[f]
   try:r=f.result()
   except Exception as e:r={'id':p['id'],'municipalityCode':p['municipalityCode'],'name':p['name'],'findings':[],'enrichment':{'checkedAt':CHECKED,'status':'取得失敗','attempted':[],'note':'解析処理失敗: '+str(e)}}
   RESULTS[p['id']]=r;progress+=1
   if progress%25==0:save();print('PROGRESS',len(RESULTS),dict(collections.Counter(x['enrichment']['status']for x in RESULTS.values())),flush=True)
 save();print('DONE',len(RESULTS),dict(collections.Counter(x['enrichment']['status']for x in RESULTS.values())),flush=True)
if __name__=='__main__':main()
