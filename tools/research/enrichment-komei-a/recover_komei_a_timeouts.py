#!/usr/bin/env python3
"""Recheck timeout URLs once in a fresh HTTP client, retaining cache and person IDs."""
import asyncio,concurrent.futures,hashlib,json,threading
import enrich_komei_a as E
from audit_komei_a import cached,canonical

def main():
 results=json.loads(E.OUTPUT.read_text());people={p['id']:p for p in json.loads(E.INPUT.read_text())}
 urls=sorted({a['url'] for r in results for a in r['enrichment']['attempted'] if 'Timeout' in a.get('error','')})
 sems={};guard=threading.Lock()
 def get(url):
  host=E.urlparse(url).hostname or ''
  with guard:sem=sems.setdefault(host,threading.Semaphore(2))
  with sem:
   try:
    b,actual=asyncio.run_coroutine_threadsafe(E._download(url),E.LOOP).result(timeout=22)
    if len(b)<100:raise ValueError('empty response')
    (E.CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.html')).write_bytes(b)
    return url,(b,actual,None)
   except Exception as exc:return url,(None,url,type(exc).__name__+': '+str(exc)[:100])
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:responses=dict(pool.map(get,urls))
 redone=[];count=0
 for index,r in enumerate(results):
  person=people[r['id']];names=[person['name']]+person.get('sourceNames',[]);needs_follow=False
  homes=set();web=person.get('website');web=web.get('url') if isinstance(web,dict) else web
  if web and '/member/detail/' not in web:homes.add(canonical(web))
  for a in r['enrichment']['attempted']:
   if '/member/detail/' in a['url']:
    b=cached(a['url'])
    if b:
     doc,identity,_=E.parse(b,a['url'],names)
     if identity:
      for anchor in doc.xpath('//a[@href]'):
       if ' '.join(anchor.text_content().split()) in ['公式ホームページ','ホームページ','公式サイト','ウェブサイト']:homes.add(canonical(E.urljoin(a['url'],anchor.get('href'))))
  for a in r['enrichment']['attempted']:
   if a['url'] not in responses:continue
   b,actual,error=responses[a['url']]
   if b:
    _,identity,_=E.parse(b,actual,names)
    a['status']='新規HTTP接続で再取得・本人一致' if identity else '新規HTTP接続で再取得・本人一致未確認';a.pop('error',None);count+=1
    if identity and canonical(a['url']) in homes:needs_follow=True
    if identity and r['enrichment']['status'] in ['取得失敗','追加根拠未確認']:r['enrichment']['status']='既存内容確認'
   else:a['error']='新規HTTP接続で再確認：'+error
  if needs_follow:
   refreshed=E.process(person);r=refreshed;redone.append(r['id'])
  results[index]=r
 E.OUTPUT.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
 report={'checkedAt':E.CHECKED,'timeoutURLs':len(urls),'successURLs':sum(bool(v[0]) for v in responses.values()),'remainingFailureURLs':sum(not v[0] for v in responses.values()),'followedHomepageIDs':redone,'note':'TimeoutのURLのみ、新規クライアントで1回再取得。成功した本人HPはプロフィール・政策の追跡を再開。'}
 (E.BASE/'komei-a-timeout-recovery-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False),flush=True)
 asyncio.run_coroutine_threadsafe(E.SESSION.close(),E.LOOP).result();E.LOOP.call_soon_threadsafe(E.LOOP.stop)
if __name__=='__main__':main()
