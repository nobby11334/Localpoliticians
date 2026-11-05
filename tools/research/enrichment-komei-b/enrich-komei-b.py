#!/usr/bin/env python3
"""Bounded source-based enrichment of all assigned people. Cache never treats zero bytes as success."""
import datetime
import sys,os,pathlib,json,re,hashlib,threading,time,concurrent.futures,urllib.parse,unicodedata,collections
BASE=pathlib.Path(os.environ.get('KOMEI_B_WORKDIR',os.getcwd())).expanduser().resolve()
sys.path.insert(0,os.environ.get('KOMEI_B_PYDEPS',str(BASE/'pydeps')))
import requests
from bs4 import BeautifulSoup,Tag
DATE=os.environ.get('KOMEI_B_CHECKED_AT',datetime.datetime.now(datetime.timezone.utc).date().isoformat())
INPUT=pathlib.Path(os.environ.get('KOMEI_B_INPUT',str(BASE/'komei-b.json'))).expanduser()
OUT=pathlib.Path(os.environ.get('KOMEI_B_OUTPUT',str(BASE/'enriched-komei-b.json'))).expanduser()
JOURNAL=pathlib.Path(os.environ.get('KOMEI_B_JOURNAL',str(OUT.with_suffix('.jsonl')))).expanduser()
CACHE=pathlib.Path(os.environ.get('KOMEI_B_CACHE',str(BASE/'.cache/komei-b'))).expanduser()
LEGACY=pathlib.Path(os.environ.get('KOMEI_B_LEGACY_CACHE',str(BASE/'.cache/komei-b-legacy'))).expanduser()
CACHE.mkdir(parents=True,exist_ok=True);OUT.parent.mkdir(parents=True,exist_ok=True);JOURNAL.parent.mkdir(parents=True,exist_ok=True)
LOCAL=threading.local();LOCK=threading.Lock();HOSTS={};FETCH_MEM={};PREVIOUS={}
PRIV=re.compile(r'生年月日|誕生|[0-9０-９]+年[0-9０-９]+月[0-9０-９]+日生|出生|生まれ|家族|夫婦|長男|長女|次男|次女|三男|三女|両親|病気|難病|後遺症|克服|闘病|療養|発症|疾患|入院|手術|抗がん|麻痺|まひ|配偶者|妻|夫は|夫と|父は|母は|娘|息子|父親|母親|姉|妹|兄|弟|親族|祖父|祖母|家内|趣味|血液型|住所|所在地|電話|FAX|TEL|〒|E.mail|メール|@|copyright',re.I)
BIO=re.compile(r'卒業|修了|中退|入学|入社|就職|勤務|退社|退職|秘書|取締役|理事|評議員|開業|創業|設立|会長|顧問|監事|事務局長|監査委員|初当選|PTA|ＰＴＡ|自治会|町会|町内会|消防団|民生委員|保護司|校長|教員|教授|会社員|看護師|保育士|弁護士|税理士|行政書士|社会保険労務士|社会福祉士|介護福祉士|理学療法士|作業療法士|薬剤師|医師|歯科医|支部長|幹事長|副代表|委員長|本部長',re.I)
EVENT=re.compile(r'出席|参加|訪問|懇談|対談|記念|集会|開催|挨拶|会合|お招き|お話|昨日|本日|今日|明日|一緒|皆さん|皆様|コメント|関連記事|アーカイブ|ブログ|記事一覧|ご支援|ご声援|最新ニュース')
POLICY=re.compile(r'推進|充実|支援|実現|拡充|整備|改善|強化|改革|向上|防災|子育て|教育|医療|福祉|高齢|障がい|障害|環境|産業|交通|防犯|安全|保育|給食|学校|住宅|財政|行政|デジタル|地域|市民|町民|村民|区民')
DATE_RE=re.compile(r'(?:19|20)[0-9]{2}\s*[(](?:明治|大正|昭和|平成|令和)\s*(?:元|[0-9]+)[)]年(?:度)?(?:\s*[0-9]+月)?(?:\s*[0-9]+日)?|(?:明治|大正|昭和|平成|令和)\s*(?:元|[0-9]+)年[(](?:19|20)[0-9]{2}年[)](?:\s*[0-9]+月)?(?:\s*[0-9]+日)?|同年(?:\s*[0-9]+月)?(?:\s*[0-9]+日)?|(?:明治|大正|昭和|平成|令和)\s*(?:元|[0-9]+)年(?:度)?(?:\s*[0-9]+月)?(?:\s*[0-9]+日)?|(?:19|20)[0-9]{2}年(?:度)?(?:\s*[0-9]+月)?(?:\s*[0-9]+日)?|(?:19|20)[0-9]{2}[./-][0-9]{1,2}(?:[./-][0-9]{1,2})?')
def period_of(line):
 dates=list(dict.fromkeys(DATE_RE.findall(unicodedata.normalize('NFKC',line))))
 if dates:return '、'.join(dates[:6])+'（出典表記。各経歴との対応は本文参照）'
 if re.search(r'退職|退社|退任|歴任|前職|前任|元職|[(（]元[)）]|前(?:代表|副|支部|本部|公明|会長|理事|幹事|委員|県議|市議|区議|町議|村議|議員|秘書)|元(?:理事|公設|私設|秘書|会長|副|監事|委員|代表|社長|職員|団長|幹事|支部|本部|県議|市議|区議|町議|村議|議員|PTA)',line,re.I):return '出典では元職・過去の経歴と記載（時期明記なし）'
 if re.search(r'現職|現任|現在|[(（]現[)）]|現(?:会長|副|理事|幹事|委員|団長|部長|社長|職員|支部|本部|公明|県議|市議|区議|町議|村議|議員)',line):return '出典では現職と記載（掲載時点不明。現在の継続は未確認）'
 if re.search(r'卒業|修了|入学|中退',line):return '学歴の年月は明記なし'
 return '出典に時期明記なし（在任期間・現職／元職は不明）'
def norm(t):return re.sub(r'[\s・･\u200b\u241e]+','',unicodedata.normalize('NFKC',t)).replace('髙','高').replace('﨑','崎')
def canon(u):
 u=urllib.parse.urldefrag(u.strip())[0]
 if 'komei.or.jp' in urllib.parse.urlparse(u).netloc:u=re.sub(r'^http:','https:',u)
 return u

def session():
 if not hasattr(LOCAL,'session'):
  LOCAL.session=requests.Session();LOCAL.session.headers['User-Agent']='Mozilla/5.0 (compatible; PublicPoliticalProfileResearch/1.0)'
  adapter=requests.adapters.HTTPAdapter(pool_connections=12,pool_maxsize=2,max_retries=0)
  LOCAL.session.mount('http://',adapter);LOCAL.session.mount('https://',adapter)
 return LOCAL.session

def get_page(url,attempted):
 rawurl=url;url=canon(url);parts=urllib.parse.urlparse(url)
 if parts.scheme not in ['http','https'] or not parts.hostname or '.' not in parts.hostname:return None,False
 host=parts.hostname.removeprefix('www.')
 with LOCK:
  sem=HOSTS.setdefault(host,threading.BoundedSemaphore(2));memo=FETCH_MEM.get(url)
 if memo is not None:
  attempted.append({'url':url,'status':'取得済み（同一実行内）'});return BeautifulSoup(memo,'html.parser'),True
 for cache,old in [(CACHE,False),(LEGACY,True)]:
  if os.environ.get('KOMEI_B_FORCE_FETCH')=='1' and '--offline' not in sys.argv:continue
  for candidate in dict.fromkeys([url,rawurl]):
   path=cache/(hashlib.sha256(candidate.encode()).hexdigest()+'.html')
   if path.exists() and path.stat().st_size>200:
    b=path.read_bytes()
    if b'<html' in b.lower() or b'<!doctype' in b.lower():
     attempted.append({'url':url,'status':'取得済み（保存資料）' if old else '取得済み（今回保存資料）'})
     with LOCK:FETCH_MEM[url]=b
     return BeautifulSoup(b,'html.parser'),True
 if '--offline' in sys.argv:
  attempted.append({'url':url,'status':'未取得（保存資料の再解析）'});return None,False
 for trial in range(2):
  try:
   with sem:
    r=session().get(url,timeout=(10,18),allow_redirects=True)
   if r.status_code!=200:
    attempted.append({'url':url,'status':'HTTP '+str(r.status_code),'error':'試行'+str(trial+1)})
    if r.status_code in [408,429,500,502,503,504] and trial==0:
     LOCAL.session.close();del LOCAL.session
     continue
    return None,False
   b=r.content
   if len(b)<200 or not re.search(br'<(?:!doctype|html)',b,re.I):
    attempted.append({'url':url,'status':'本文取得不可','error':'HTML本文が空または非HTML'});return None,False
   path=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.html');tmp=path.with_suffix('.tmp-'+str(threading.get_ident()));tmp.write_bytes(b);tmp.replace(path)
   attempted.append({'url':url,'status':'取得済み','httpStatus':200})
   with LOCK:FETCH_MEM[url]=b
   return BeautifulSoup(b,'html.parser'),True
  except Exception as e:
   if hasattr(LOCAL,'session'):
    LOCAL.session.close();del LOCAL.session
   attempted.append({'url':url,'status':'取得失敗','error':type(e).__name__+': '+str(e).split('url:')[0][:120]+'（試行'+str(trial+1)+'）'})
 return None,False

def aliases(person):return list(dict.fromkeys([person['name']]+person.get('sourceNames',[])+person.get('_verifiedAliases',[])))
def add_verified_aliases(s,person,source_url):
 root=s.select_one('.dList06')
 if root is None:return
 dt=next((x for x in root.select('dt') if '名前' in x.get_text()),None)
 dd=dt.find_next_sibling('dd') if dt else None
 if dd is None:return
 text=unicodedata.normalize('NFKC',dd.get_text(' ',strip=True))
 m=re.match(r'(.+?)[(](.+?)[)]',text)
 if not m:return
 kanji=re.split(r'\s+',m[1].strip());kana=re.split(r'\s+',m[2].strip())
 if norm(m[1]) not in [norm(x) for x in [person['name']]+person.get('sourceNames',[])]:return
 alt=[''.join(kana)] if len(''.join(kana))>=5 else []
 if len(kanji)==2 and len(kana)==2:alt.extend([kana[0]+kanji[1],kanji[0]+kana[1]])
 person['_verifiedAliases']=alt;person['_identitySourceURL']=source_url

def match_name(s,person,scope=None):
 text=(scope or s).get_text(' ',strip=True)
 title=(s.title.get_text(' ',strip=True) if s.title else '')
 for n in aliases(person):
  if len(norm(n))>=3 and (norm(n) in norm(text) or norm(n) in norm(title)):return n
 return None

def profile_root(s):
 for sel in ['.entry-content','.art-PostContent','.post_content','.post-content','.page-content','.pagebody','.postbody','#contents','.contents','article.area-main','main','article']:
  root=s.select_one(sel)
  if root and len(root.get_text(strip=True))>15:return root,sel
 return s.body or s,'body'

def clean_scope(root):
 # Quotes, shared footers and comment/news widgets cannot supply biography evidence.
 for t in list(root.select('script,style,nav,header,footer,aside,form,noscript,blockquote,q,.menu-item,#menu,#navigation,.comment,.comments,.commentlist,#comments,.related,.related-posts,.widget,.sidebar,#sidebar,.navigation,.post-meta,.entry-meta')):t.decompose()
 for br in root.find_all('br'):br.replace_with('\u241e')
 return root

def facts_from_text(text,kind):
 text=unicodedata.normalize('NFKC',text);text=re.sub(r'[^\S\n]+',' ',text).strip(' ・●○■◆\t')
 # Break actual sentences/field lines, so one private clause does not leak via another clause.
 chunks=re.split(r'[。\n\r]|[;；]',text)
 out=[];pending_date=''
 if kind!='policy' and PRIV.search(norm(text)):return []
 for z in chunks:
  z=z.strip(' ・●○■◆\t')
  if kind!='policy' and DATE_RE.fullmatch(z):pending_date=z;continue
  if kind!='policy' and pending_date and BIO.search(z) and not DATE_RE.search(z):z=pending_date+' '+z;pending_date=''
  if not 5<=len(z)<=180 or PRIV.search(z) or PRIV.search(norm(z)) or EVENT.search(z):continue
  if re.search(r'(?<!\d)0\d{1,3}[-ー]\d{2,4}[-ー]\d{3,4}(?!\d)',z):continue
  if kind=='policy':
   if not re.search(r'推進|整備|改善|強化|充実|拡充|導入|開設|実施|めざ|目指|を守|つく|支援|無償|削減|減免|助成|防災',z):continue
   if len(z)>110 or not re.search(r'子育て|教育|医療|福祉|高齢|障がい|障害|環境|産業|交通|防犯|安全|保育|給食|学校|住宅|財政|行政|デジタル|除雪|除排雪|災害|防災|企業|雇用|観光|経済',z) or re.search(r'実現しました|実績です|これまでの実績|\.\.\.|…|政策ページ|サイト|リンク|こちら|申し込み|ツイート|シェア|政党名|公明新聞',z):continue
  else:
   if not BIO.search(z):continue
   if re.search(r'子ども|子供|長子',z) and not re.search(r'PTA|保護司|民生委員',z,re.I):continue
   if re.search(r'私は|そして|その後は|できました|ことが|一生懸命|日々を|400倍|奇跡|不景気|「|」|『|』|と話|によると|報じ|さん|君|氏が|氏は|氏の経歴|友人|知人|先輩|同僚|同級生|先生|ゲスト|講演会|入社当時|大学院卒業時|学校卒業まで|全員|児童生徒|[!！?？]|見て|ご覧|からだ|と述べ|と語り|を紹介|とのこと|を支える|をめざ|を目指',z):continue
   if re.search(r'大学|短期大学|大学院|専門学校|[高大]等学校|高校|中学校|小学校',z) and re.search(r'卒業|修了|中退|入学',z) and re.search(r'無償化|まで|医療費|助成|奨学金の|卒業生',z):continue
  if kind!='policy':z=re.sub(r'(初当選)(?:した時.*|し、.*|を果たし.*)$',r'\1',z)
  if z not in out:out.append(z)
 return out

def category(line,kind):
 if kind=='policy':return 'policy'
 if re.search(r'PTA|自治会|町内会|町会|消防団|保護司|民生委員|交通指導|地域防災|青少年|育成会',line,re.I):return 'community'
 if re.search(r'議会.*(?:委員|理事|会長|幹事|団長|議長|議員会)|監査委員|(?:常任|特別|予算|決算|議会運営|総務|文教|厚生|建設)委員会.*委員',line):return 'activity'
 if re.search(r'党.*(?:会長|幹事長|支部長|本部長|委員長|副代表|局長|部長)|(?:支部長|本部長|幹事長).*党',line):return 'party'
 if re.search(r'理事|評議員|顧問|会長',line) and not re.search(r'取締役|入社|会社',line):return 'organization'
 return 'career'

def make_finding(line,url,kind,matched,heading,selector,source='本人発信'):
 cat=category(line,kind)
 label={'career':'職歴・学歴','community':'PTA・地域活動','organization':'団体役職','party':'政党役職','policy':'掲げる政策','activity':'議会内役職'}[cat]
 # Factual lists/names, summarized without claims of independent verification or achievement.
 summary=('本人の政策ページで「'+line+'」を紹介。実現状況や本人の寄与は未検証。' if cat=='policy' else 'プロフィール記載：'+line+'。')
 return {'category':cat,'title':label+'：'+line[:58],'summary':summary,'period':period_of(line),'url':url,'sourceType':source,'asOf':f'掲載時点不明（保存資料を{DATE}確認）','asOfBasis':'retrievedAt','checkedAt':DATE,'evidence':{'matchedName':matched,'sectionHeading':heading[:100],'selector':selector,'rule':'本人一致＋専用プロフィール/政策欄の短い事実項目。引用・共有フッター・行事記事・私的事項を除外。'}}

def extract_page(s,person,url,kind):
 if '/member/detail/' in url:
  root=s.select_one('.dList06');matched=match_name(s,person,root)
  if not root or not matched:return [],None
  findings=[]
  for dt in root.select('dt'):
   key=dt.get_text(' ',strip=True);dd=dt.find_next_sibling('dd')
   if not dd or key not in ['略歴','経歴','学歴','職歴','役職','主な経歴']:continue
   for br in dd.find_all('br'):br.replace_with('\u241e')
   for line in facts_from_text(dd.get_text(' ',strip=True).replace('\u241e','\n'),'profile')[:8]:findings.append(make_finding(line,url,'profile',matched,key,'.dList06 dl > dd','政党公式'))
  return findings,matched
 root,sel=profile_root(s);root=clean_scope(root)
 if re.search(r'404|not found|お探しのページ|見つかりません',root.get_text(' ',strip=True)[:400],re.I):return [],None
 matched=match_name(s,person,root)
 if not matched:return [],None
 # Only dedicated profile/policy pages; a blog homepage containing daily events is not a source block.
 if kind not in ['profile','policy']:return [],matched
 findings=[];seen=set();totalchars=0
 # Headings and table/dl/list rows preserve local biography field context.
 elements=root.find_all(['h1','h2','h3','h4','h5','p','li','dd','tr'])
 for el in elements:
  if el.find_parent(['blockquote','aside','nav','footer','header']):continue
  family_dd=el.find_parent('dd')
  if family_dd:
   k=family_dd.find_previous_sibling('dt')
   if k and PRIV.search(norm(k.get_text(' ',strip=True))):continue
  family_row=el.find_parent('tr')
  if family_row and PRIV.search(norm(family_row.get_text(' ',strip=True))):continue
  if el.name in ['p','li'] and el.find(['p','li','tr','dd']):continue
  if el.name=='p' and el.find_parent(['tr','dd']):continue
  txt=el.get_text(' ',strip=True).replace('\u241e','\n')
  if kind=='profile' and not DATE_RE.search(unicodedata.normalize('NFKC',txt)):
   prev=el.find_previous_sibling()
   if prev:
    prior=unicodedata.normalize('NFKC',prev.get_text(' ',strip=True)).strip()
    prevprev=prev.find_previous_sibling()
    if DATE_RE.fullmatch(prior) and not (prevprev and PRIV.search(norm(prevprev.get_text(' ',strip=True)))):txt=prior+' '+txt
    elif prior in ['元','現','現職','元職','前職']:txt='('+prior+') '+txt
  if el.name=='dd':
   prev=el.find_previous_sibling('dt')
   if prev and PRIV.search(norm(prev.get_text(' ',strip=True))):continue
   if prev:txt=prev.get_text(' ',strip=True)+' '+txt
  if PRIV.search(txt) and len(txt)>250:continue
  if len(txt)>500:continue
  # Nearest preceding heading must belong to the current profile content, not a sidebar.
  h=el if el.name.startswith('h') else el.find_previous(['h1','h2','h3','h4','h5'])
  heading=h.get_text(' ',strip=True) if h else ''
  if not heading:heading='[ページタイトル] '+(s.title.get_text(' ',strip=True) if s.title else ('政策専用ページ（文字見出しなし）' if kind=='policy' else 'プロフィール専用ページ（文字見出しなし）'))
  if kind=='profile' and (PRIV.search(norm(heading)) or re.search(r'家族|夫の|父の|母の|子供の|子どもの|連絡先',heading)):continue
  if re.search(r'コメント|最近の|新着|ブログ|活動報告|実績ニュース|公明党とは|党代表|サイトマップ',heading):continue
  for line in facts_from_text(txt,kind):
   key=norm(re.sub(r'^政策[ :：]*','',line))
   if key in seen:continue
   seen.add(key);totalchars+=len(line)
   findings.append(make_finding(line,url,kind,matched,heading,sel+' '+el.name))
   # Retain role/community facts before school history if a long CV exceeds the limit.
 if kind=='profile':
  def rank(f):
   c=f['category'];t=f['summary']
   if c=='community':return 0
   if c=='organization':return 1
   if c=='party':return 2
   if c=='career' and re.search(r'入社|退社|勤務|就職|開業|創業|秘書|取締役|資格',t):return 3
   if c=='career' and re.search(r'大学|大学院|専門学校',t):return 4
   if c=='activity':return 5
   return 6
  findings.sort(key=rank)
 selected=[];budget=0
 for f in findings:
  if budget+len(f['summary'])>650:continue
  selected.append(f);budget+=len(f['summary'])
  if len(selected)>=(10 if kind=='profile' else 6):break
 return selected,matched

def discover(s,url):
 links={'profile':[],'policy':[]};base=urllib.parse.urlparse(url)
 for a in s.select('a[href]'):
  label=a.get_text(' ',strip=True);href=a['href'];u=canon(urllib.parse.urljoin(url,href));pr=urllib.parse.urlparse(u)
  if pr.scheme not in ['http','https']:continue
  same=pr.netloc.removeprefix('www.')==base.netloc.removeprefix('www.')
  if not same:continue
  # On shared komei host, same-host is insufficient: preserve the person's /km/<slug>/ prefix.
  m=re.match(r'(/km/[^/]+)(?:/|$)',base.path)
  if m and not pr.path.startswith(m[1]+'/'):continue
  if u==canon(url):continue
  if re.search(r'プロフィール|経歴|略歴|自己紹介|[Pp]rofile|[Bb]iography',label) or re.search(r'/(?:profile|biography)(?:[./_-]|$)',pr.path):links['profile'].append(u)
  elif re.search(r'政策|公約|お約束|ビジョン|[Pp]olicy|[Mm]anifest',label) or re.search(r'/(?:policy|manifest)(?:[./_-]|$)',pr.path):links['policy'].append(u)
 return {k:list(dict.fromkeys(v))[:1] for k,v in links.items()}

def existing_match(s,person):
 root=s.select_one('.dList06') or profile_root(s)[0]
 text=norm(root.get_text(' ',strip=True))
 for f in person.get('findings',[]):
  title=unicodedata.normalize('NFKC',f.get('title',''))
  value=re.split(r'[:：]',title,maxsplit=1)[-1].strip()
  if '期数' in title:
   dt=next((d for d in s.select('.dList06 dt')if d.get_text(strip=True)=='期数'),None)
   dd=dt.find_next_sibling('dd') if dt else None
   if dd and norm(value)==norm(dd.get_text(strip=True)):return True
  elif len(norm(value))>=6 and norm(value) in text:return True
 return False

def process(person):
 attempted=list(PREVIOUS.get(person['id'],{}).get('enrichment',{}).get('attempted',[])) if '--offline' in sys.argv else [];new=[];matched=False;confirmed_existing=False;website=person.get('website',{});website=website if isinstance(website,dict) else {'url':website}
 u=website.get('url','');out={'id':person['id'],'municipalityCode':person['municipalityCode'],'name':person['name'],'findings':[]}
 existing=person.get('findings',[])
 if '--offline' in sys.argv and '/member/detail/' not in u:
  proof=next((f.get('url') for f in existing if '/member/detail/' in f.get('url','')),None)
  if proof:
   doc,success=get_page(proof,attempted)
   if doc is not None and match_name(doc,person,doc.select_one('.dList06')):
    add_verified_aliases(doc,person,proof);confirmed_existing=existing_match(doc,person)
 # Existing entries are comparison values only; never re-export them as new findings.
 if not u:
  u=next((f['url'] for f in existing if '/member/detail/' in f.get('url','')),'')
 if not u:
  out['enrichment']={'checkedAt':DATE,'status':'追加根拠未確認','attempted':[],'note':'入力に本人プロフィールURLがなく、本人ページを同定できず。経歴不存在を意味しない。'};return out
 s,ok=get_page(u,attempted)
 if s is not None:
  if '/member/detail/' in u:add_verified_aliases(s,person,canon(u))
  fs,m=extract_page(s,person,canon(u),'profile' if re.search(r'/profile(?:[./_-]|$)',u) else 'home');new+=fs;matched=bool(m);confirmed_existing=confirmed_existing or (bool(m) and existing_match(s,person))
  if '/member/detail/' in u and matched:
   own=next((a.get('href') for a in s.select('.dList06 a[href]') if '公式ホームページ' in a.get_text()),None)
   if own and own.startswith(('http://','https://')):
    website={'url':canon(own),'kind':'本人ホームページ（政党公式プロフィールから確認）'};u=website['url']
    direct_match=False
    if re.match(r'https://(?:www\.)?komei\.or\.jp/km/[^/]+/?$',u):
     attempted.append({'url':u,'status':'公式URL確認（党公式プロフィールのリンク）'})
     for direct_kind in ['profile','policy']:
      v=u.rstrip('/')+'/'+direct_kind+'/'
      sub,success=get_page(v,attempted)
      if sub is not None:
       fs,m=extract_page(sub,person,v,direct_kind);new+=fs;direct_match=direct_match or bool(m);confirmed_existing=confirmed_existing or (bool(m) and existing_match(sub,person))
     if direct_match:s=None;matched=True
     else:s,ok=get_page(u,attempted)
    else:s,ok=get_page(u,attempted)
    if s is not None:matched=bool(match_name(s,person))
  if s is not None and '/member/detail/' not in u:
   d=discover(s,canon(u))
   # Homepage's owner name must match, but a known dedicated profile may supply the name if home is image-only.
   for kind in ['profile','policy']:
    for v in d[kind]:
     sub,success=get_page(v,attempted)
     if sub is not None:
      fs,m=extract_page(sub,person,v,kind);new+=fs;matched=matched or bool(m);confirmed_existing=confirmed_existing or (bool(m) and existing_match(sub,person))
   # Some sites use /profile as the entry URL and have no profile link.
   if re.search(r'/profile(?:[./_-]|$)',u):
    fs,m=extract_page(s,person,canon(u),'profile');new+=fs;matched=matched or bool(m)
 # Remove duplicates at claim/URL level. Never add a roster-only or term-count finding.
 signatures={(norm(f.get('summary','')),canon(f.get('url',''))) for f in existing}
 added=[]
 for f in new:
  if person.get('_identitySourceURL'):
   f['evidence']['identitySourceURL']=person['_identitySourceURL']
   f['evidence']['identityBasis']='政党公式の氏名・フリガナ欄に基づく表記ゆれを含め照合'
  sig=(norm(f['summary']),canon(f['url']))
  if sig in signatures:continue
  signatures.add(sig);added.append(f)
 out['findings']=added
 if website.get('url'):out['website']=website
 attempted=list({(a.get('url'),a.get('status'),a.get('error')):a for a in attempted}.values())
 anyok=any(a['status'].startswith('取得済み') for a in attempted)
 if added:status='情報追加'
 elif anyok and confirmed_existing:status='既存内容確認'
 elif anyok:status='追加根拠未確認'
 else:status='取得失敗'
 out['enrichment']={'checkedAt':DATE,'status':status,'attempted':attempted,'note':('本人の一致を確認し、専用欄の事実を追加。本人発信の内容は第三者裏付け未実施。' if added else '既存の一部記載を出典本文と照合。既存全項目の再検証や役職の現任確認を意味しない。' if status=='既存内容確認' else '追加できる本人一致の専用欄の記載を確認できず。取得失敗・画像のみ・氏名不一致・経歴記載未確認などを含み、経歴や活動が存在しないという判定ではない。')}
 return out

def safe_process(p):
 try:return process(p)
 except Exception as e:return {'id':p['id'],'municipalityCode':p['municipalityCode'],'name':p['name'],'findings':[],'enrichment':{'checkedAt':DATE,'status':'取得失敗','attempted':[],'note':'処理例外：'+type(e).__name__+' '+str(e)[:100]+'。経歴不存在を意味しない。'}}

def write_text_atomic(path,text):
 tmp=path.with_name(path.name+'.tmp-'+str(os.getpid()))
 tmp.write_text(text);tmp.replace(path)

def main():
 global PREVIOUS
 people=json.loads(INPUT.read_text());done={}
 if JOURNAL.exists():
  for line in JOURNAL.read_text().splitlines():
   try:
    x=json.loads(line)
    if x.get('enrichment',{}).get('checkedAt')==DATE:done[x['id']]=x
   except:pass
 if OUT.exists():
  for x in json.loads(OUT.read_text()):
   if x.get('enrichment',{}).get('checkedAt')==DATE:done[x['id']]=x
 PREVIOUS=dict(done)
 if '--reparse' in sys.argv:done={}
 pending=[p for p in people if p['id'] not in done]
 if '--limit' in sys.argv:pending=pending[:int(sys.argv[sys.argv.index('--limit')+1])]
 print('START',len(people),'resume',len(done),'pending',len(pending),flush=True)
 with JOURNAL.open('a') as log,concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  futures={pool.submit(safe_process,p):p['id'] for p in pending}
  for fut in concurrent.futures.as_completed(futures):
   x=fut.result();done[x['id']]=x;log.write(json.dumps(x,ensure_ascii=False)+'\n');log.flush()
   if len(done)%25==0:
    write_text_atomic(OUT,json.dumps([done[p['id']] for p in people if p['id'] in done],ensure_ascii=False,indent=2))
    print('PROGRESS',len(done),dict(collections.Counter(v['enrichment']['status'] for v in done.values())),flush=True)
 write_text_atomic(OUT,json.dumps([done[p['id']] for p in people if p['id'] in done],ensure_ascii=False,indent=2))
 print('COMPLETE' if len(done)==len(people) else 'PARTIAL',len(done),dict(collections.Counter(v['enrichment']['status'] for v in done.values())),flush=True)
if __name__=='__main__':main()
