#!/usr/bin/env python3
"""Bounded public-profile enrichment; explicit person match; no private data."""
import asyncio,aiohttp,concurrent.futures,datetime,hashlib,json,os,re,threading,time,unicodedata,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urlparse,urljoin,urlunparse
from lxml import html
BASE=Path(__file__).resolve().parent
INPUT=Path(os.environ.get('KOMEI_A_INPUT',str(BASE/'komei-a.json')));OUTPUT=Path(os.environ.get('KOMEI_A_OUTPUT',str(BASE/'enriched-komei-a.json')))
CACHE=Path(os.environ.get('KOMEI_A_CACHE',str(BASE/'komei-a-cache')));CACHE.mkdir(parents=True,exist_ok=True)
OLD=Path(os.environ.get('KOMEI_A_SOURCE_CACHE',str(BASE.parent/'expanded/komei-cache')))
CHECKED=os.environ.get('KOMEI_A_CHECKED_AT','2026-11-05')
locks={};guard=threading.Lock();stat= {'network':0,'cache':0}

# One persistent async HTTP session; per-host semaphores below enforce the shared budget.
LOOP=asyncio.new_event_loop()
def _run_loop():
 asyncio.set_event_loop(LOOP);LOOP.run_forever()
threading.Thread(target=_run_loop,daemon=True).start()
async def _make_session():
 return aiohttp.ClientSession(trust_env=True,timeout=aiohttp.ClientTimeout(total=18,sock_read=9),connector=aiohttp.TCPConnector(limit=8,limit_per_host=2),headers={'User-Agent':'PublicMunicipalProfileResearch/1.0','Accept':'text/html'})
SESSION=asyncio.run_coroutine_threadsafe(_make_session(),LOOP).result()
async def _download(url):
 async with SESSION.get(url) as response:
  response.raise_for_status()
  data=await response.read()
  if len(data)>2500000:raise ValueError('response exceeds page limit')
  return data,str(response.url)

def norm(s):
 canonical=unicodedata.normalize('NFKC',s or '').translate(str.maketrans({'國':'国','澤':'沢','濱':'浜','髙':'高','﨑':'崎','邊':'辺','邉':'辺'}))
 return re.sub(r'[\s　・･\-\u200b]','',canonical)
def fetch(url):
 if url.startswith('http://'):url='https://'+url[7:]
 key=hashlib.sha256(url.encode()).hexdigest()+'.html'
 for folder in [CACHE,OLD]:
  f=folder/key
  if f.exists() and f.stat().st_size>0:
   with guard:stat['cache']+=1
   return f.read_bytes(),url,'取得済み資料再読',None
 host=urlparse(url).hostname or ''
 with guard:sem=locks.setdefault(host,threading.Semaphore(2))
 error=None
 for attempt in range(2):
  try:
   with sem:
    data,final=asyncio.run_coroutine_threadsafe(_download(url),LOOP).result(timeout=22)
    with guard:stat['network']+=1
   if len(data)<100:raise ValueError('empty or too short response')
   (CACHE/key).write_bytes(data)
   return data,final,'取得',None
  except Exception as e:
   error=type(e).__name__+': '+str(e)[:150]
   if (isinstance(e,urllib.error.HTTPError) and e.code in [401,403,404,410]) or (isinstance(e,aiohttp.ClientResponseError) and e.status in [401,403,404,410]):break
 return None,url,'取得失敗',error

PRIVATE=re.compile(r'生年月|誕生|生まれ|出身地|住所|電話|FAX|ＴＥＬ|TEL|メール|家族|配偶者|夫|妻|一男|一女|二男|二女|子供[はがの]|兄|姉|弟|妹|長男|長女|次男|次女|息子|娘|妻|夫人|趣味|血液|座右|ペット|結婚|歳|才|〒|@|[0-9０-９]{2,4}[-－][0-9０-９]{2,4}[-－][0-9０-９]{3,4}')
POLICY_PRIVATE=re.compile(r'生年月日|誕生日|家族構成|私の(?:妻|夫|家族|父|母|息子|娘)|趣味|血液型|座右の銘|〒|@|[0-9０-９]{2,4}[-－][0-9０-９]{2,4}[-－][0-9０-９]{3,4}|[0-9０-９一二三四五六七八九十]+丁目[0-9０-９]')
CAREER=re.compile(r'卒業|大学卒|高校卒|高等学校卒|専門学校卒|修了|中退|入社|退社|勤務|勤め|就職|秘書|独立|開業|看護師|保育士|教諭|教員|講師|教授|助教|研究員|防災士|宅地建物取引士|電気工事士|弁護士|税理士|行政書士|社会福祉士|介護福祉士|歯科医|薬剤師|公認会計士|初当選|再選|議会議員|議長|委員長|当選')
COMM=re.compile(r'PTA|ＰＴＡ|保護者会|子ども会|自治会|町内会|消防団|民生委員|児童委員|防犯協会|交通安全|スポーツ少年団')
ORG=re.compile(r'理事|顧問|会長|副会長|事務局長|代表|幹事長|支部長|委員長|部長|局長')
POLICY=re.compile(r'政策|ビジョン|マニフェスト|取り組み|めざす|目指す|推進|充実|実現|支援|防災|子育て|教育|福祉|交通')
PROFILELABEL=re.compile(r'プロフィール|プロフィル|略歴|経歴|自己紹介|自己紹介|議員紹介')
POLICYLABEL=re.compile(r'政策|ビジョン|マニフェスト|めざす|目指す')

def parse(data,url,names):
 try:r=html.fromstring(data)
 except:return None,False,[]
 for e in r.xpath('//script|//style|//noscript|//template|//svg'):e.getparent().remove(e)
 text=norm(r.text_content())
 matched=any(norm(n) and norm(n) in text for n in names)
 links=[]
 if matched:
  for a in r.xpath('//a[@href]'):
   label=' '.join(a.text_content().split());u=urljoin(url,a.get('href'))
   if not label or len(label)>45:continue
   if PROFILELABEL.search(label) and not re.search(r'家族|妻|夫|長男|長女|父|母',label):links.append((0,u,label))
   elif POLICYLABEL.search(label):links.append((1,u,label))
 return r,matched,links

def shortfacts(r,url,source_type,mode,matched_name,section_heading):
 original_paths={node:node.getroottree().getpath(node) for node in r.iter()}
 # Remove page chrome, shared article lists, comment forms and social feeds.
 for e in r.xpath('//nav|//header|//footer|//aside|//form|//*[contains(concat(" ",normalize-space(@class)," ")," sidebar ") or contains(@class,"widget") or contains(@class,"comment") or contains(@class,"related")]'):
  if e.getparent() is not None:e.getparent().remove(e)
 roots=r.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," entry-content ") or contains(concat(" ",normalize-space(@class)," ")," post-content ") or contains(@class,"profile-body")]')
 if not roots:roots=r.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," content ")]')
 if len(roots)>1:
  leaves=[n for n in roots if not any(m is not n and n in m.iterancestors() for m in roots)]
  if len(leaves)!=1:return []
  roots=leaves
 roots=roots or [r]
 # Remove explicitly private family/hobby sections, including subsequent unlabelled lines.
 for root in roots:
  for heading in list(root.xpath('.//h2|.//h3|.//h4')):
   label=' '.join(heading.text_content().split()).strip('：: ')
   if not re.fullmatch(r'家族(?:構成|紹介)?|趣味|生年月日|誕生日|好きな(?:本|食べ物|言葉)|妻|夫|長男|長女|次男|次女|息子|娘',label):continue
   for sibling in list(heading.itersiblings()):
    if sibling.tag in ['h1','h2','h3','h4'] or sibling.xpath('.//h1|.//h2|.//h3|.//h4'):break
    if sibling.getparent() is not None:sibling.getparent().remove(sibling)
   if heading.getparent() is not None:heading.getparent().remove(heading)
 # Work with leaf-ish blocks to preserve short factual entries instead of entire-page prose.
 blocks=[]
 for root in roots:
  for el in root.xpath('.//tr|.//li[not(.//li)]|.//p[not(.//p)]|.//dd|.//h2|.//h3|.//h4'):
   if el.tag=='tr':s=' '.join(el.text_content().split())
   elif el.tag=='dd' and el.getprevious() is not None and el.getprevious().tag=='dt':s=' '.join((el.getprevious().text_content()+' '+el.text_content()).split())
   else:
    # br separates chronology lines.
    eltext=html.tostring(el,encoding='unicode',method='html');eltext=re.sub(r'<br\s*/?>','\n',eltext,flags=re.I)
    try:s=html.fromstring(eltext).text_content()
    except:s=el.text_content()
   if mode=='profile' and re.search(r'(?:妻|夫|父|母|長男|長女|次男|次女|息子|娘)[はがの]|恩師|友人|知人|先輩|後輩',s):continue
   for line in re.split(r"[。\n]+",s):
    line=' '.join(line.split()).strip('・●■◆◇○◎▶▷：: ')
    line=re.sub(r'^.*?(?:人柄が評価され|信頼を得て)[、,]','',line)
    line=re.sub(r'^そして[、,]','',line)
    if line and line not in blocks:blocks.append(line)
 findings=[];seen=set()
 for line in blocks:
  if len(line)<5 or len(line)>120 or re.search(r'同校|同大学|同社|同会|これら|上記|以下',line) or (POLICY_PRIVATE.search(line) if mode=='policy' else PRIVATE.search(line)) or (mode=='profile' and re.search(r'父|母|引用|転載|寄稿|とのこと|と語|と述べ|さん[はがの]|氏[はが]|先生|恩師|師匠|友人|知人|先輩|後輩',line)):continue
  # Ignore global menu entries, bare topics, navigational labels and election advertisement.
  if (re.fullmatch(r'[\w\s・／/ー]{0,8}',line) and not (CAREER.search(line) or COMM.search(line) or ORG.search(line))) or 'クリック' in line or 'こちら' in line or line in ['プロフィール','政策','略歴','経歴']:continue
  cat=None
  if COMM.search(line) and (ORG.search(line) or re.search(r'委員|団員|活動|所属',line)):cat='community'
  elif mode=='profile' and CAREER.search(line):cat='career'
  elif mode=='profile' and ORG.search(line) and len(line)<95:cat='party' if '公明党' in line or re.search(r'党|総支部',line) else 'organization'
  elif mode=='policy' and POLICY.search(line) and len(line)>=12 and re.search(r'支援|推進|強化|充実|実現|改善|対策|施策|制度|整備|見直|拡充|廃止|助成|負担|給付|無償|守る|確保|解消|減税|増税|賛成|反対|挑戦|導入|連携',line):cat='policy'
  if not cat:continue
  if cat!='policy' and re.search(r'(?:看護師|保育士|教諭|教員|弁護士|税理士|行政書士)(?:さん|の方|に相談|に支え|に助け|からの支|から励|から助)|温か|やさし|優し|励ま|感謝|感動|尊敬',line):continue
  if cat!='policy' and re.search(r'目指|めざ|予定|なりたい|当選を|当選に向け|当選のため|尽くして|努めて',line):continue
  if cat=='career' and '選挙' in line and not re.search(r'当選|再選|落選|立候補した|出馬した|公選',line):continue
  if cat!='policy' and re.search(r'(?:を|の).{0,10}(?:支援|解消|改善|充実|推進|促進|強化|拡充|実現)|に取り組|を応援',line) and not re.search(r'卒業|修了|中退|入社|退社|勤務|初当選|再選|秘書|委員長|議長|支部長|幹事長|歴任',line):continue
  if cat=='career' and re.fullmatch(r'(?:公明党)?[^。]{1,25}議会議員(?:[ 　]+[^。]+)?',line) and not re.search(r'[0-9０-９].*(?:年|期|回)',line):continue
  if cat=='career' and not re.search(r'入社|勤務|就職|退社|開業',line):
   degree=re.search(r'^(.+?(?:卒業|修了|中退))',line)
   if degree:line=degree.group(1)
  # Restrict paragraphs to concise fact-like fragments; discard multiple-sentence narratives.
  if line.count('。')>1 or line.count('！')>0 or 'ありがとうございます' in line:continue
  suffix='と本人資料に記載。' if source_type=='本人発信' else 'と行政・議会資料に記載。' if source_type=='行政・議会' else 'と党公式資料に記載。'
  summary=line.rstrip('。')+suffix
  title=('政策：' if cat=='policy' else '地域活動：' if cat=='community' else '経歴：' if cat=='career' else '役職：')+line[:55]
  year=r'(?:(?:19|20)\d{2}年(?:\d{1,2}月)?|(?:令和|平成|昭和)\s*[元\d]+年(?:\s*\d{1,2}月)?)'
  date=re.search('('+year+r'(?:\s*[～〜~－−—-]\s*'+year+r')?)',unicodedata.normalize('NFKC',line))
  f=dict(category=cat,title=title,summary=summary,period=date.group(0) if date else '資料記載／期間不明',url=url,sourceType=source_type,asOf=f'資料更新日不明（{CHECKED}確認）',checkedAt=CHECKED,evidence=dict(matchedName=matched_name,sectionHeading=section_heading,selector=original_paths.get(roots[0],roots[0].getroottree().getpath(roots[0])),rule='本人名一致＋本人HPリンクのプロフィール/政策範囲。短い事実文のみ。私的情報・引用他人・称賛表現・長文を除外。'))
  if norm(line) in seen:continue
  seen.add(norm(line));findings.append(f)
 priority={'community':0,'organization':1,'party':2,'career':3,'policy':4}
 findings.sort(key=lambda f:priority[f['category']])
 return findings[:4] if mode=="policy" else findings[:10]

def official_aliases(doc,person_name):
 aliases=[]
 for heading in doc.xpath('//h1[contains(@class,"hdg1_01")]'):
  label=' '.join(heading.text_content().split())
  value=unicodedata.normalize('NFKC',label)
  match=re.match(r'(.+?)\(([^)]+)\)',value)
  if not match or norm(match.group(1))!=norm(person_name):continue
  if not re.fullmatch(r'[ぁ-ゖァ-ヶー・\s]+',match.group(2)):continue
  kanji=match.group(1).split();reading=match.group(2).split()
  aliases.append(''.join(reading))
  if len(kanji)==2 and len(reading)==2:
   aliases.extend([reading[0]+kanji[1],kanji[0]+reading[1]])
 return list(dict.fromkeys(aliases))

def process(person):
 attempted=[];new=[];matched_any=False;fetched=False;names=[person['name']]+person.get('sourceNames',[]);urls=[]
 web=person.get('website');web=web.get('url') if isinstance(web,dict) else web
 if web:urls.append((web,'home'))
 details=[f.get('url') for f in person.get('findings',[]) if '/member/detail/' in f.get('url','')]
 queue=urls[:];visited=set();links=[];note=[]
 # Homepage then explicitly linked profile and policy. Official detail is the fallback.
 if not queue and details:queue=[(details[0],'profile')]
 while queue and len(visited)<4:
  u,mode=queue.pop(0)
  if u.startswith('http://'):u='https://'+u[7:]
  u=u.split('#')[0]
  if u in visited:continue
  visited.add(u);data,actual,status,error=fetch(u);a=dict(url=u,status=status)
  if error:a['error']=error
  attempted.append(a)
  if data is None:
   if not queue and not matched_any and details and details[0] not in visited:queue.append((details[0],'profile'))
   continue
  fetched=True;r,identity,ls=parse(data,actual,names)
  if not identity:
   a['status']='取得・本人一致未確認'
   if not queue and not matched_any and details and details[0] not in visited:queue.append((details[0],'profile'))
   continue
  matched_any=True;a['status']=status+'・本人一致'
  matched_name=next(n for n in names if norm(n) and norm(n) in norm(r.text_content()))
  source='政党公式' if '/member/detail/' in actual else '本人発信'
  if '/member/detail/' in actual:
   names.extend(n for n in official_aliases(r,person['name']) if n not in names)
   # Follow only the official individual profile's explicit personal homepage link.
   targetlinks=[]
   for anchor in r.xpath('//a[@href]'):
    label=' '.join(anchor.text_content().split())
    if label in ['公式ホームページ','ホームページ','公式サイト','ウェブサイト']:
     dest=urljoin(actual,anchor.get('href'))
     if '/member/' not in dest and urlparse(dest).scheme in ['http','https']:targetlinks.append(dest)
   if targetlinks:queue=[(targetlinks[0],'home')]+queue
   else:new.extend(shortfacts(r,actual,'政党公式','profile',matched_name,'公明党公式議員プロフィール'))
   continue
  if mode=='home':
   # Profile sections on home are accepted only when the block explicitly identifies the section.
   # Homepages are discovery only; no article or shared-page fact extraction.
   current=urlparse(actual);personpath=current.path.rstrip('/')
   chosen={}
   for rank,v,label in ls:
    parsed=urlparse(v)
    if parsed.scheme not in ['https','http']:continue
    # A shared komei host is trusted only within this person's /km/ subtree.
    same=parsed.hostname==current.hostname and (not '/km/' in current.path or parsed.path.startswith(personpath+'/'))
    if not same:continue
    if rank not in chosen and v.split('#')[0] not in visited:chosen[rank]=v
   queue.extend((chosen[k],'profile' if k==0 else 'policy') for k in sorted(chosen))
   if not queue and details:queue.append((details[0],'profile'))
  else:
   # Individual subpage must have one article body; multiple-article listings are rejected.
   title=' '.join(r.xpath('//h1//text()|//title/text()'))
   headings=' '.join(r.xpath('//h1//text()|//h2//text()|//h3//text()'))
   pattern=POLICYLABEL if mode=='policy' else PROFILELABEL
   hs=[' '.join(h.text_content().split()) for h in r.xpath('//h1|//h2|//h3|//h4') if pattern.search(h.text_content())]
   label=hs[0] if hs else title
   if mode=='policy' and not POLICYLABEL.search(title+' '+headings):continue
   if mode=='profile' and '/member/detail/' not in actual and not PROFILELABEL.search(title+' '+headings):continue
   new.extend(shortfacts(r,actual,source,mode,matched_name,label))
 # Suppress duplicate facts already present in the input.
 oldnorm=[norm(f.get('title','')+' '+f.get('summary','')) for f in person.get('findings',[])];seen=set();clean=[]
 for f in new:
  k=norm(f['summary'].split('と本人資料')[0].split('と党公式資料')[0])
  if k in seen or any(k in old for old in oldnorm):continue
  seen.add(k);clean.append(f)
 priority={'community':0,'organization':1,'party':2,'career':3,'policy':4}
 clean.sort(key=lambda f:priority[f['category']])
 clean=clean[:16]
 state='情報追加' if clean else '既存内容確認' if matched_any else '追加根拠未確認' if fetched else '取得失敗'
 return dict(id=person['id'],municipalityCode=person['municipalityCode'],name=person['name'],findings=clean,enrichment=dict(checkedAt=CHECKED,status=state,attempted=attempted,note='本人名一致の公開ページを確認。党の個人プロフィールに本人HPリンクがある場合は追跡。既存内容確認はページ取得と本人同定を指し、既存の全経歴の再検証を意味しない。追加未確認は経歴・活動の不存在を意味しない。現況継続・更新日は未確認。'))

def main():
 people=json.loads(INPUT.read_text());partial=OUTPUT.with_suffix('.partial-v3.json');done={}
 if partial.exists():done={x['id']:x for x in json.loads(partial.read_text())}
 start=time.time();todo=[p for p in people if p['id'] not in done]
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
  futures={ex.submit(process,p):p for p in todo}
  for fut in concurrent.futures.as_completed(futures):
   p=futures[fut]
   try:r=fut.result()
   except Exception as e:r=dict(id=p['id'],municipalityCode=p['municipalityCode'],name=p['name'],findings=[],enrichment=dict(checkedAt=CHECKED,status='取得失敗',attempted=[],note='処理例外：'+type(e).__name__+': '+str(e)[:100]+'。経歴なしとは判断しない。'))
   done[r['id']]=r
   if len(done)%20==0 or len(done)==len(people):
    ordered=[done[p['id']] for p in people if p['id'] in done];partial.write_text(json.dumps(ordered,ensure_ascii=False,indent=2)+'\n')
    counts={s:sum(x['enrichment']['status']==s for x in ordered) for s in ['情報追加','既存内容確認','追加根拠未確認','取得失敗']}
    print(json.dumps(dict(processed=len(done),total=len(people),findings=sum(len(x['findings']) for x in ordered),statuses=counts,seconds=round(time.time()-start),fetch=stat),ensure_ascii=False),flush=True)
 results=[done[p['id']] for p in people];assert len(results)==len(people);OUTPUT.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
 print('COMPLETE '+str(OUTPUT),flush=True)
 asyncio.run_coroutine_threadsafe(SESSION.close(),LOOP).result()
 LOOP.call_soon_threadsafe(LOOP.stop)
if __name__=='__main__':main()
