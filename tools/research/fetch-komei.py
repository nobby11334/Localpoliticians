import urllib.request,concurrent.futures,bs4,json,re,pathlib,hashlib,time,sys
ROOT=pathlib.Path('.');CACHE=ROOT/'komei-cache';CACHE.mkdir(exist_ok=True)
reg=json.load(open('../../data/national.json'))['municipalities']
index={}
for m in reg:index.setdefault(m['name'],[]).append(m)
def fetch(u):
 p=CACHE/(hashlib.sha256(u.encode()).hexdigest()+'.html')
 if p.exists() and p.stat().st_size:return p.read_text()
 if '--cached-only' in sys.argv:return ''
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'CivicLedger public profile research'}),timeout=18) as r:h=r.read().decode('utf-8')
  p.write_text(h);return h
 except Exception as e:return ''
def page(n):
 u='https://www.komei.or.jp/member/result/n:80/page:'+str(n);s=bs4.BeautifulSoup(fetch(u),'html.parser');out=[]
 for a in s.select('a[href*="/member/detail/"]'):
  dt=a.find('dt');dd=a.find('dd')
  if not dt or not dd:continue
  city=dt.get_text(strip=True);ident=a['href'].rstrip('/').split('/')[-1];matches=index.get(city,[]);matches=[m for m in matches if m['code'][:2]==ident[:2]] or matches
  if len(matches)!=1:continue
  name=re.split('[（(]',dd.get_text(' ',strip=True))[0].replace(' ','').replace('　','');m=matches[0]
  out.append({'municipalityCode':m['code'],'name':name,'office':('区' if city.endswith('区') else '町' if city.endswith('町') else '村' if city.endswith('村') else '市')+'議会議員','party':'公明党','asOf':'掲載日時不明（2026-11-04取得）','collectedAt':'2026-11-04','sourceURL':u,'sourceTitle':'公明党公式 所属議員検索','rosterKind':'政党公式の所属議員掲載','profileURL':'https://www.komei.or.jp'+a['href'],'findings':[],'researchNotes':'党公式の所属議員検索に掲載。掲載日時不明・2026-11-04取得。議会の全員名簿ではありません。現在の在職継続や次回出馬を推定しません。'})
 return out
def enrich(p):
 u=p['profileURL'];s=bs4.BeautifulSoup(fetch(u),'html.parser');p['website']={'url':u,'kind':'政党公式プロフィール'}
 for a in s.find_all('a',href=True):
  if a.get_text(strip=True)=='公式ホームページ' and a['href'].startswith(('http:','https:')):p['website']={'url':a['href'],'kind':'本人ホームページ（政党掲載）'};break
 for dt in s.find_all(['dt','th']):
  key=dt.get_text(' ',strip=True)
  if key not in ['期数','略歴','経歴','学歴','職歴','役職']:continue
  dd=dt.find_next_sibling(['dd','td'])
  if not dd:continue
  val=dd.get_text(' ',strip=True)
  if not val or len(val)>700:continue
  p['findings'].append({'category':'career' if key in ['略歴','経歴','学歴','職歴','期数'] else 'organization','title':key+'：'+val[:130],'summary':'公明党公式プロフィールの掲載事項。現在の継続や活動実態は未確認。','period':'掲載日時不明','url':u,'sourceType':'政党公式','asOf':'掲載日時不明（2026-11-04取得）'})
 return p
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:groups=list(ex.map(page,range(1,38)))
people=list({(p['municipalityCode'],p['name']):p for group in groups for p in group}.values());print('Komei municipality members:',len(people),flush=True)
(ROOT/'komei-members.json').write_text(json.dumps(people,ensure_ascii=False,indent=2))
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
 out=[]
 for i,p in enumerate(ex.map(enrich,people)):
  out.append(p)
  if i%200==0:
   (ROOT/'komei-members.json').write_text(json.dumps(out+people[i+1:],ensure_ascii=False,indent=2));print('Profiles',i+1,flush=True)
(ROOT/'komei-members.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print('Complete',len(out),flush=True)
