#!/usr/bin/env python3
"""Bounded official-site research. Requires aiohttp and lxml; never edits the repo.
Only exact full-name matches (with explicit orthographic aliases) permit findings.
Use --limit for QA, --resume to reuse completed JSONL rows, --output to choose result.
"""
import argparse,asyncio,collections,hashlib,json,os,pathlib,re,time,unicodedata,urllib.parse
import settings as cfg
import aiohttp
from lxml import html
P=pathlib.Path(__file__).parent
CHECKED=cfg.CHECKED_AT
NAV=re.compile(r'(市長|区長|町長|村長|首長|プロフィール|プロフィル|略歴|経歴)')
PROFILE=re.compile(r'プロフィール|プロフィル|略歴|経歴|紹介')
ROLE=re.compile(r'市長|区長|町長|村長')
BADLINK=re.compile(r'交際費|記者会見|活動|日程|動き|メッセージ|あいさつ|挨拶|所信|フォト|施政|議会|副市長|副町長|副村長|選挙|歴代|退任|訃報|訓示')
PRIVATE=re.compile(r'生年月|誕生|家族|妻|夫人|長男|長女|次男|次女|住所|電話|ファクス|FAX|〒|生まれ|趣味|好きな|座右|血液|尊敬|お問い合わせ|問い合わせ|窓口|開庁|メール|copyright',re.I)
QUAL=re.compile(r'卒業|卒塾|修了|入学|入社|入庁|入省|入行|採用|勤務|退職|退官|議員|議長|副市長|副町長|副村長|助役|局長|部長|課長|室長|教授|講師|理事|取締役|会長|委員長|弁護士|医師|教諭|教員|PTA|ＰＴＡ')
DATE=re.compile(r'(?:昭和|平成|令和)\s*(?:元|[0-9０-９]+)\s*年(?:\s*[0-9０-９]+\s*月)?|(?:19|20)\d{2}\s*年(?:\s*\d{1,2}\s*月)?')
ALIASES={'仲川元庸':['仲川げん']}
def norm(s):
 s=unicodedata.normalize('NFKC',s)
 s=re.sub(r'[\s\u3000\ufe00-\ufe0f\U000e0100-\U000e01ef]','',s)
 for a,b in [('髙','高'),('廣','広'),('澤','沢'),('﨑','崎'),('齋','斎'),('齊','斉'),('邊','辺'),('邉','辺'),('𠮷','吉'),('黑','黒'),('眞','真'),('壽','寿'),('實','実'),('德','徳'),('惠','恵'),('澁','渋'),('櫻','桜'),('瀨','瀬')]:s=s.replace(a,b)
 return s

def document(body,url):
 try:tree=html.fromstring(body.encode('utf-8'),base_url=url,parser=html.HTMLParser(encoding='utf-8'))
 except Exception:return None
 linktree=html.fromstring(body.encode('utf-8'),base_url=url,parser=html.HTMLParser(encoding='utf-8'))
 for n in tree.xpath('//script|//style|//noscript|//nav|//header|//footer'):n.drop_tree()
 title=' '.join(tree.xpath('//title/text()'))
 # Most official CMSs mark main content; fall back to common content wrappers.
 main=next(iter(tree.xpath('//main|//*[@role="main"]|//*[@id="main_body"]|//*[@id="mainbody"]|//*[@id="main_text"]|//*[@id="content_main"]|//*[@id="maincontents"]')),tree)
 for n in main.xpath('.//nav|.//footer|.//aside'):n.drop_tree()
 lines=[]
 for n in main.xpath('.//tr|.//li|.//p|.//h1|.//h2|.//h3|.//h4|.//dt|.//dd|.//img'):
  # Don't duplicate nested paragraphs inside table rows/list items.
  if n.tag not in ('tr','li') and n.xpath('ancestor::tr|ancestor::li'):continue
  rawtext=n.get('alt','') if n.tag=='img' else n.text_content()
  parts=[rawtext]
  if len(DATE.findall(rawtext))>2 and n.tag in ('tr','p','li','dd'):
   serialized=html.tostring(n,encoding='unicode')
   serialized=re.sub(r'<br\b[^>]*>', '\n',serialized,flags=re.I)
   serialized=re.sub(r'</p\s*>','\n</p>',serialized,flags=re.I)
   try:parts=html.fromstring(serialized).text_content().splitlines()
   except Exception:parts=[rawtext]
  for part in parts:
   t=' '.join(part.split())
   if t and t not in lines:lines.append(t)
 text='\n'.join(lines) or ' '.join(main.text_content().split())
 whole=' '.join(tree.text_content().split())
 links=[]
 for a in linktree.xpath('//a[@href]'):
  label=' '.join(a.text_content().split())
  if not label:label=' '.join(a.xpath('.//img/@alt'))
  href=urllib.parse.urljoin(url,a.get('href'));parts=urllib.parse.urlsplit(href)
  if parts.scheme not in ('http','https') or not label:continue
  href=urllib.parse.urlunsplit((parts.scheme,parts.netloc,parts.path,parts.query,''))
  links.append((label,href))
 dates=re.findall(r'更新日(?:付)?[：:]?\s*(\d{4})年(\d{1,2})月(\d{1,2})日',whole)
 updated=f'{int(dates[0][0]):04}-{int(dates[0][1]):02}-{int(dates[0][2]):02}' if dates else CHECKED
 headings=[' '.join(n.text_content().split()) for n in main.xpath('.//h1|.//h2|.//h3|.//h4')]
 return {'headings':headings,'title':title,'text':text,'whole':whole,'lines':lines,'links':links,'asOf':updated}

def identity(doc,person,url):
 names=[person['name']]+ALIASES.get(person['name'],[])
 text=re.sub(r'[（(][^）)]{1,25}[）)]','',doc['text'])
 hay=norm(doc['title']+'\n'+text)
 # Identity must occur before the end of the article, not solely in image alt or nav.
 ok=any(norm(n) in norm(doc['title']) for n in names)
 if not ok:
  for line in doc['headings']+doc['lines']:
   clean=re.sub(r'[（(][^）)]{1,25}[）)]','',line)
   if len(clean)>110 or re.search(r'(?:前|元)(?:市長|区長|町長|村長)|歴代|退任|逝去',clean):continue
   for n in names:
    if norm(n) in norm(clean) and (norm(clean)==norm(n) or re.search(r'氏名|名前|市長|区長|町長|村長|プロフィール|プロフィル',clean)):
     ok=True;break
 if not ok:return False
 header=doc['title']+' '+' '.join(doc['headings'][:8])
 if re.search(r'歴代|選挙結果|選挙の結果|訃報|退任|追悼',doc['title']):return False
 profile=bool(PROFILE.search(doc['title']) or any(PROFILE.search(h) for h in doc['headings']) or ('profile' in url.lower()))
 # A mayor's official room can contain the profile below its introductory message.
 room=bool(ROLE.search(doc['title']) and re.search(r'略歴|経歴|学歴|職歴|プロフィール|公職歴',doc['text']))
 return profile or room

def extract(doc,url,person):
 names=[person['name']]+ALIASES.get(person['name'],[])
 lines=doc['lines'];found=[]
 start=next((i for i,l in enumerate(lines) if any(norm(n) in norm(re.sub(r'[（(][^）)]{1,25}[）)]','',l)) for n in names)),None)
 if start is None:return []
 lines=lines[start:]
 end=next((i for i,l in enumerate(lines[1:],1) if (l in doc['headings'] and re.search(r'副市長|副町長|副村長|歴代|教育長',l)) or (re.fullmatch(r'副市長|副町長|副村長|教育長',l) and not (i>0 and DATE.search(lines[i-1])))),len(lines))
 lines=lines[:end]
 for i,line in enumerate(lines):
  if len(line)>400 or len(line)<4 or PRIVATE.search(line) or not QUAL.search(line):continue
  # Navigation entries and generic public notices are not biographical facts.
  if re.search(r'募集|募集要項|メッセージ|広報|卒業式|講演会|お知らせ|父は|母は|祖父|祖母|選挙管理委員|連絡先|お問い合わせ|関連記事|関連リンク|目次|市長への|町長への|村長への|区長への|意見|公務員募集|会議録|議員名簿|議員紹介',line):continue
  if re.fullmatch(r'.{0,12}(?:経歴|略歴|プロフィール|紹介|学歴|職歴)',line):continue
  period=DATE.findall(line)
  if not period and i>0 and len(lines[i-1])<45:
   previous=lines[i-1]
   residue=re.sub(r'[0-9０-９年月日至自（）()～~〜・\s./-]','',DATE.sub('',previous))
   if not residue and DATE.search(previous) and re.search(r'略歴|経歴|学歴|職歴|公職歴|主な役職|役員等',' '.join(lines[max(0,i-12):i])) and not (i>1 and PRIVATE.search(lines[i-2])):period=DATE.findall(previous)
  # Require temporal evidence or an explicit biography section to avoid navigation.
  context=' '.join(lines[max(0,i-12):i+1])
  if not period and not re.search(r'略歴|経歴|学歴|職歴|公職歴|主な役職|役職等|役員等',context):continue
  if not period and len(line)<7:continue
  # Trim dates; retain only the factual institution/role fragment.
  detail=re.sub(r'^(?:昭和|平成|令和)(?:元|\d+)年(?:\d+月)?(?:\d+日)?[\s　～~\-]*','',line)
  detail=re.sub(r'^(?:19|20)\d{2}年(?:\d+月)?(?:\d+日)?[\s　～~\-]*','',detail).strip(' ・:：')
  if len(detail)>95 or len(DATE.findall(line))>2:continue
  if PRIVATE.search(detail):continue
  if re.search(r'PTA|ＰＴＡ|自治会|町内会|青年会議所',detail):category='community';title='地域・教育団体の役職歴'
  elif re.search(r'理事|取締役|代表|名誉|会長',detail):category='organization';title='団体・法人での役職歴'
  else:category='career';title='学歴・職歴・議会歴'
  # Short factual fragments: avoid copying a full narrative paragraph.
  # Rephrase the factual role/institution fragment rather than reproduce a paragraph.
  fact=re.sub(r'^(?:学\s*歴|職\s*歴|略歴|経歴|主な経歴)[：:\s]*','',detail).strip('・●■ []【】')
  fact=re.sub(r'^[【\[]?(?:(?:昭和|平成|令和)\s*(?:元|\d+)年(?:\d+月)?|(?:19|20)\d{2}年(?:\d+月)?)[】\]]?\s*','',fact)
  title=fact if len(fact)<=40 else fact[:39]+'…'
  if fact.endswith('卒業'):summary=fact[:-2].rstrip()+'を卒業した経歴。'
  elif fact.endswith('修了'):summary=fact[:-2].rstrip()+'を修了した経歴。'
  elif fact.endswith('入社'):summary=fact[:-2].rstrip()+'へ入社した経歴。'
  elif fact.endswith('入省'):summary=fact[:-2].rstrip()+'へ入省した経歴。'
  elif fact.endswith('入庁'):summary=fact[:-2].rstrip()+'に入庁した経歴。'
  elif fact.endswith('勤務'):summary=fact[:-2].rstrip()+'での勤務歴を公式資料で確認。'
  else:summary=fact.rstrip('。')+'としての経歴・役職を公式資料に掲載。'
  finding={'category':category,'title':title,'summary':summary,'period':'・'.join(period) if period else '資料掲載時点（詳細年月未記載）','url':url,'sourceType':'行政・議会','asOf':doc['asOf'],'checkedAt':CHECKED,'evidence':{'matchedName':None,'sectionHeading':next((h for h in doc['headings'] if re.search(r'略歴|経歴|学歴|職歴|プロフィール|役職',h)),doc['title']),'rule':'公式紹介ページの本人氏名完全一致（異体字正規化・明示通称を除く）、経歴等の年月付き行又は経歴見出し内の役職行','sourceFragment':line[:180]}}
  if not any(norm(f['summary'])==norm(summary) for f in found):found.append(finding)
  if len(found)>=30:break
 return found[:25]

class Research:
 def __init__(self,cache):
  self.cache=cache;cache.mkdir(parents=True,exist_ok=True);self.sem=asyncio.Semaphore(cfg.PARALLEL);self.hosts={};self.memory={};self.started=time.monotonic();self.done=0;self.counts=collections.Counter();self.network=0
  # Optional private audit inputs are never bundled with this public package.
  self.seed={}
  index=os.environ.get('MAYORS_SEED_INDEX')
  seed_dir=os.environ.get('MAYORS_SEED_DIR')
  if index and seed_dir:
   for row in pathlib.Path(index).read_text(encoding='utf-8').splitlines():
    name,url=row.split('\t');f=pathlib.Path(seed_dir)/f'{name}.html'
    if f.exists():self.seed[url]=f.read_text(encoding='utf-8')
 def path(self,url):return self.cache/(hashlib.sha256(url.encode()).hexdigest()+'.json')
 async def fetch(self,session,url):
  if url in self.memory:return self.memory[url]
  path=self.path(url)
  if path.exists():
   try:r=json.loads(path.read_text());r['cached']=True;self.memory[url]=r;return r
   except Exception:pass
  if url in self.seed:r={'url':url,'status':200,'body':self.seed[url],'cached':True,'cacheSource':'user-provided reviewed profile'};self.memory[url]=r;return r
  host=urllib.parse.urlsplit(url).netloc.lower();lock=self.hosts.setdefault(host,asyncio.Semaphore(1))
  async with lock:
   async with self.sem:
    r=None
    async def read_once():
     try:
      timeout=aiohttp.ClientTimeout(total=12,connect=5,sock_read=8)
      # New Client per request; no stale cross-host connection pool is reused.
      connector=aiohttp.TCPConnector(limit=1,force_close=True,ssl=cfg.SSL_CONTEXT)
      async with aiohttp.ClientSession(timeout=timeout,connector=connector,trust_env=True,headers={'User-Agent':'Mozilla/5.0 (compatible; Localpoliticians public-source research)'}) as client:
       async with client.get(url,allow_redirects=True,ssl=cfg.SSL_CONTEXT) as response:
        if 'pdf' in response.headers.get('Content-Type','').lower():raise ValueError('PDFは今回のHTML調査対象外')
        chunks=[];size=0
        async for chunk in response.content.iter_chunked(65536):
         size+=len(chunk)
         if size>2500000:raise ValueError('HTML取得上限2.5MB超過')
         chunks.append(chunk)
        b=b''.join(chunks);enc=response.charset or 'utf-8'
        try:body=b.decode(enc)
        except (UnicodeDecodeError,LookupError):body=b.decode('cp932',errors='replace')
        if '<html' in body.lower() and '</html>' not in body.lower():raise ValueError('HTML本文が不完全（終了タグ欠落）')
        return {'url':str(response.url),'status':response.status,'body':body if response.status==200 else '', 'cached':False}
     except Exception as e:return {'url':url,'status':'error','error':str(e) or type(e).__name__,'body':'','cached':False}
    for retry in range(2):
     self.network+=1;r=await read_once()
     if r['status'] not in ('error',408,429,500,502,503,504) or retry==1:break
    self.memory[url]=r;path.write_text(json.dumps(r,ensure_ascii=False));return r

 def select(self,doc,home,seen,profile_only=False):
  target=urllib.parse.urlsplit(home).netloc.lower().removeprefix('www.')
  candidates=[]
  for label,url in doc['links']:
   host=urllib.parse.urlsplit(url).netloc.lower().removeprefix('www.')
   if host!=target or url in seen or re.search(r'\.(?:pdf|xls|xlsx|jpg|png|zip)(?:\?|$)',url,re.I):continue
   if re.search(r'(?:市|町|村|区)のプロフィ',label):continue
   if not NAV.search(label):continue
   if BADLINK.search(label):continue
   score=(12 if re.search(r'プロフィール|プロフィル',label) else 8 if re.search(r'略歴|経歴',label) else 5 if re.search(r'紹介',label) else 2)+(15 if ROLE.search(label) else 0)
   if profile_only and not PROFILE.search(label):continue
   candidates.append((score,url,label))
  if not candidates:
   for label,url in doc['links']:
    host=urllib.parse.urlsplit(url).netloc.lower().removeprefix('www.')
    if host==target and url not in seen and (re.search(r'(?:市政|町政|村政|区政)(?:情報|ポータル|について|の情報)',label) or re.fullmatch(r'.{0,12}(?:市|町|村|区)について|(?:市|町|村|区)の概要|(?:市|町|村|区)の紹介|行政情報|暮らし・行政情報',label)):candidates.append((0,url,label))
  return sorted(candidates,reverse=True)
 async def person(self,session,person):
  result={k:person[k] for k in ['municipalityCode','name','snapshotAsOf']};result['findings']=[]
  attempted=[];seen=set();queue=[];profile_found=False;ok_fetch=False;home=person['officialURL'];note=[]
  eligible=[p for p in (person.get('existingPeople') or []) if norm(p['name'])==norm(person['name']) or p['name'] in ALIASES.get(person['name'],[])]
  for old in (person.get('existingPeople') or []):
   if old not in eligible:note.append('既存自治体プロフィールは別氏名のため引継ぎ対象外: '+old['name'])
  for old in eligible:
   u=old.get('sourceURL') or old.get('profileURL') or (old.get('website') or {}).get('url')
   if u:queue.append(u)
  queue.append(home)
  for step in range(cfg.MAX_PAGES):
   if not queue:break
   url=queue.pop(0)
   if url in seen:continue
   seen.add(url);response=await self.fetch(session,url)
   attempt={'url':url,'status':str(response['status'])}
   if response.get('cached'):attempt['status']+='（保存済み資料）'
   if response.get('error'):attempt['error']=response['error'][:200]
   attempted.append(attempt)
   if response['status']!=200:continue
   ok_fetch=True;doc=document(response['body'],response['url'])
   if not doc:continue
   if identity(doc,person,response['url']):
    profile_found=True;result['profileURL']=response['url']
    # Previously curated summaries were reviewed manually, retain only same-person evidence.
    existing=[dict(f,checkedAt=CHECKED) for old in eligible for f in old.get('findings',[]) if f.get('url') in (url,response['url'])]
    new=extract(doc,response['url'],person)
    for f in new:f['evidence']['matchedName']=person['name']
    for f in existing:f['evidence']={'matchedName':person['name'],'sectionHeading':doc['title'],'rule':'前回手動確認した同一本人・同一公式URLの要約と保存本文の本人一致を再照合'}
    if existing:
     result['findings']=existing
     # Keep new distinct education rows; prior career summaries already cover many dates.
     for f in new:
      if ('卒業' in f['summary'] or '修了' in f['summary']) and not any(norm(f['summary'])==norm(e['summary']) for e in result['findings']):result['findings'].append(f)
    else:result['findings']=new
    if result['findings']:break
   choices=self.select(doc,home,seen)
   # Follow only the strongest one or two relevant links; profile links first.
   queue=[u for _,u,_ in choices[:2]]+queue
   queue=list(dict.fromkeys(queue))
  if result['findings']:status='既存内容確認' if eligible else '情報追加';note.append('本人氏名の一致する公式紹介資料を確認。掲載内容の確認であり経歴の網羅性は保証しない。')
  elif profile_found:status='追加根拠未確認';note.append('本人と一致する紹介ページは確認したが、今回追加できる経歴情報を特定できなかった。経歴がないとの意味ではない。')
  elif ok_fetch:status='追加根拠未確認';note.append('追跡した公式ページで本人一致の経歴資料を確認できなかった。首長交代や未掲載の可能性を含み、経歴がないとの意味ではない。')
  else:status='取得失敗';note.append('公式サイトの本文を取得できなかったため追加の根拠を確認できず。')
  result['enrichment']={'checkedAt':CHECKED,'status':status,'attempted':attempted,'note':' '.join(note)}
  self.done+=1;self.counts[status]+=1
  if self.done%25==0:print(json.dumps({'done':self.done,'networkRequests':self.network,'elapsedSec':round(time.monotonic()-self.started),'statuses':dict(self.counts)},ensure_ascii=False),flush=True)
  return result

async def main(args):
 people=json.loads(args.input.read_text());people=people[:args.limit] if args.limit else people
 research=Research(args.cache);log=cfg.CHECKPOINT;completed={}
 if args.resume and log.exists():
  for line in log.read_text().splitlines():
   try:r=json.loads(line);completed[(r['municipalityCode'],r['name'])]=r
   except Exception:pass
 args.output.parent.mkdir(parents=True,exist_ok=True);log.parent.mkdir(parents=True,exist_ok=True)
 timeout=aiohttp.ClientTimeout(total=25,connect=12,sock_read=15)
 connector=aiohttp.TCPConnector(limit=cfg.PARALLEL,limit_per_host=1,ssl=cfg.SSL_CONTEXT)
 async with aiohttp.ClientSession(timeout=timeout,connector=connector,trust_env=True,headers={'User-Agent':'Mozilla/5.0 (compatible; Localpoliticians public-source research)'}) as session:
  pending=asyncio.Queue()
  for person in people:
   if (person['municipalityCode'],person['name']) not in completed:pending.put_nowait(person)
  async def worker():
   while not pending.empty():
    try:person=pending.get_nowait()
    except asyncio.QueueEmpty:break
    try:r=await research.person(session,person)
    except Exception as e:r={k:person[k] for k in ['municipalityCode','name','snapshotAsOf']};r.update(findings=[],enrichment={'checkedAt':CHECKED,'status':'取得失敗','attempted':[],'note':'調査処理エラー: '+str(e)[:200]})
    completed[(r['municipalityCode'],r['name'])]=r
    with log.open('a') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    pending.task_done()
  await asyncio.gather(*(worker() for _ in range(cfg.PARALLEL)))
 result=[completed[(p['municipalityCode'],p['name'])] for p in people]
 args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'finished':len(result),'findings':sum(len(r['findings']) for r in result),'status':dict(collections.Counter(r['enrichment']['status'] for r in result))},ensure_ascii=False),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=pathlib.Path,default=cfg.INPUT);p.add_argument('--output',type=pathlib.Path,default=cfg.COLLECTED);p.add_argument('--cache',type=pathlib.Path,default=cfg.CACHE);p.add_argument('--limit',type=int);p.add_argument('--resume',action='store_true');asyncio.run(main(p.parse_args()))
