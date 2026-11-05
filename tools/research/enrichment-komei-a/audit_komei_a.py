#!/usr/bin/env python3
"""Cache-only final audit. Never fetches extra pages or copies page bodies."""
import asyncio,copy,hashlib,json,re
from pathlib import Path
import enrich_komei_a as E

def cached(url):
 url='https://'+url[7:] if url.startswith('http://') else url
 key=hashlib.sha256(url.encode()).hexdigest()+'.html'
 for folder in [E.CACHE,E.OLD]:
  f=folder/key
  if f.exists() and f.stat().st_size>0:return f.read_bytes()
 return None

def canonical(u):return ('https://'+u[7:] if u.startswith('http://') else u).split('#')[0].rstrip('/')

def audit(person,result):
 names=[person['name']]+person.get('sourceNames',[]);attempted=result['enrichment']['attempted'];allowed={};pages={};trusted_homes=set()
 home=person.get('website');home=home.get('url') if isinstance(home,dict) else home
 if home and '/member/detail/' not in home and not ('komei-fukuoka.jp/news/' in home):trusted_homes.add(canonical(home))
 identity_sources=[]
 for a in attempted:
  if '/member/detail/' not in a['url']:continue
  b=cached(a['url'])
  if not b:continue
  doc,matched,_=E.parse(b,a['url'],names)
  if matched:
   derived=E.official_aliases(doc,person['name'])
   names.extend(n for n in derived if n not in names)
   if derived:identity_sources.append(a['url'])

 for a in attempted:
  if '本人一致' not in a['status']:continue
  b=cached(a['url'])
  if not b:continue
  r,matched,links=E.parse(b,a['url'],names)
  if not matched:continue
  pages[canonical(a['url'])]=(b,a['url'])
  if '/member/detail/' in a['url']:
   allowed[canonical(a['url'])]=('profile','公明党公式議員プロフィール')
   for anchor in r.xpath('//a[@href]'):
    label=' '.join(anchor.text_content().split())
    if label in ['公式ホームページ','ホームページ','公式サイト','ウェブサイト']:
     trusted_homes.add(canonical(E.urljoin(a['url'],anchor.get('href'))))
 blocked_shared=[]
 for key in list(trusted_homes):
  if key not in pages:continue
  b,url=pages[key];r,matched,links=E.parse(b,url,names)
  prominent=' '.join(r.xpath('//title/text()|//h1//text()'))
  shared=re.search(r'議員団|市議団|区議団|県議団|会派|県本部|市議会公明党',prominent)
  owner=any(E.norm(n) and E.norm(n) in E.norm(prominent) for n in names)
  if shared and not owner and '/km/' not in url:
   blocked_shared.append(key);trusted_homes.discard(key)
 for key in trusted_homes:
  if key not in pages:continue
  b,url=pages[key];r,matched,links=E.parse(b,url,names)
  if not matched:continue
  for rank,dest,label in links:
   if canonical(dest) in pages:allowed[canonical(dest)]=('profile' if rank==0 else 'policy',label)
 facts=[]
 # Exact self-profile headings on an otherwise verified personal homepage are bounded sections.
 for homekey in trusted_homes:
  if homekey not in pages:continue
  b,homeurl=pages[homekey];doc,identity,_=E.parse(b,homeurl,names)
  if not identity:continue
  for heading in doc.xpath('//h2|//h3|//h4'):
   headingtext=' '.join(heading.text_content().split())
   if not re.fullmatch(r'(?:私の|議員)?(?:プロフィール|プロフィル|略歴|経歴|自己紹介)',headingtext):continue
   parent=heading.getparent()
   if parent is None or len(parent.xpath('.//h1|.//h2|.//h3|.//h4'))!=1:continue
   if len(parent.text_content())>3000:continue
   matched=next(n for n in names if E.norm(n) and E.norm(n) in E.norm(doc.text_content()))
   scope=copy.deepcopy(parent)
   fs=E.shortfacts(scope,homeurl,'本人発信','profile',person['name'],headingtext)
   for f in fs:
    f['evidence']['selector']=parent.getroottree().getpath(parent)
    f['evidence']['discoveryLinkLabel']='本人HP内の明示プロフィール見出し'
    f['evidence']['observedMatchedName']=matched
   facts.extend(fs)
 for key,(mode,linklabel) in allowed.items():
  if key not in pages:continue
  b,url=pages[key];r,identity,_=E.parse(b,url,names)
  if not identity:continue
  matched=next(n for n in names if E.norm(n) and E.norm(n) in E.norm(r.text_content()))
  pattern=E.PROFILELABEL if mode=='profile' else E.POLICYLABEL
  headings=[' '.join(h.text_content().split()) for h in r.xpath('//h1|//h2|//h3|//h4') if pattern.search(h.text_content())]
  title=' '.join(r.xpath('//title/text()'))
  if not headings and not pattern.search(title) and '/member/detail/' not in url:continue
  label=headings[0] if headings else title
  host=E.urlparse(url).hostname or ''
  admin=host.endswith('.lg.jp') or any(t in host for t in ['.city.','.town.','.vill.','.pref.'])
  source='行政・議会' if admin else '政党公式' if '/member/detail/' in url else '本人発信'
  fs=E.shortfacts(r,url,source,mode,person['name'],label)
  for f in fs:
   f['evidence']['observedMatchedName']=matched
   if identity_sources:f['evidence']['identitySources']=identity_sources
  for f in fs:f['evidence']['discoveryLinkLabel']=linklabel
  facts.extend(fs)
 oldnorm=[E.norm(f.get('title','')+' '+f.get('summary','')) for f in person.get('findings',[])];seen=set();clean=[]
 for f in facts:
  key=E.norm(f['summary'].split('と本人資料')[0].split('と党公式資料')[0])
  if key in seen or any(key in old for old in oldnorm):continue
  seen.add(key);clean.append(f)
 priority={'community':0,'organization':1,'party':2,'career':3,'policy':4};clean.sort(key=lambda f:priority[f['category']]);clean=clean[:16]
 for key in trusted_homes:
  if key in pages and '/member/' not in key:
   result['website']={'url':pages[key][1],'title':'本人ホームページ（本人名照合・政党公式リンク確認）','kind':'personal'}
   break
 if blocked_shared and not clean:
  result['website']={'url':pages[blocked_shared[0]][1],'title':'所属団体の共有サイト（本人専用ページの確認前）','kind':'party'}
 result['findings']=clean
 if clean:result['enrichment']['status']='情報追加'
 elif result['enrichment']['status']=='情報追加':result['enrichment']['status']='既存内容確認'
 result['enrichment']['note']='本人名一致と本人HPのプロフィール・政策リンクを照合し、当該本文領域の短い事実文を監査。既存内容確認は公開ページの取得・本人同定を指し、既存の全経歴の再検証を意味しない。追加未確認は経歴・活動の不存在を意味しない。現況継続・資料更新日は未確認。'
 if blocked_shared:result['enrichment']['note']+=' 団体の共有サイトは本人専用の出典として扱っていない。'
 return result

def main():
 people=json.loads(E.INPUT.read_text());results=json.loads(E.OUTPUT.read_text());byid={p['id']:p for p in people};assert len(results)==len(people)
 audited=[audit(byid[r['id']],r) for r in results]
 supplement=E.BASE/'komei-a-verified-supplement.json'
 if supplement.exists():
  overrides={r['id']:r for r in json.loads(supplement.read_text())}
  for key,r in overrides.items():assert key in byid and r['name']==byid[key]['name']
  audited=[overrides.get(r['id'],r) for r in audited]
 assert {r['id'] for r in audited}==set(byid)
 for r in audited:
  for f in r['findings']:
   assert f['evidence']['matchedName'] and f['evidence']['sectionHeading'] and f['checkedAt']<=E.CHECKED
 E.OUTPUT.write_text(json.dumps(audited,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'audited':len(audited),'peopleAdded':sum(bool(r['findings']) for r in audited),'findings':sum(len(r['findings']) for r in audited)},ensure_ascii=False))
 asyncio.run_coroutine_threadsafe(E.SESSION.close(),E.LOOP).result();E.LOOP.call_soon_threadsafe(E.LOOP.stop)
if __name__=='__main__':main()
