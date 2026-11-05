#!/usr/bin/env python3
"""Resolve public display-name variants only from verified official furigana."""
import asyncio,concurrent.futures,copy,json
import enrich_komei_a as E
from audit_komei_a import cached

def main():
 results=json.loads(E.OUTPUT.read_text());people={p['id']:p for p in json.loads(E.INPUT.read_text())};jobs=[];proof=[]
 for record in results:
  mismatches=[a for a in record['enrichment']['attempted'] if '本人一致未確認' in a['status']]
  if not mismatches:continue
  person=people[record['id']];names=[person['name']]+person.get('sourceNames',[])
  official=[a['url'] for a in record['enrichment']['attempted'] if '/member/detail/' in a['url']]
  for url in official:
   b=cached(url)
   if not b:continue
   doc,identity,_=E.parse(b,url,names)
   if not identity:continue
   aliases=E.official_aliases(doc,person['name'])
   if not aliases:continue
   can_verify=False
   for attempt in mismatches:
    payload=cached(attempt['url'])
    if payload and E.parse(payload,attempt['url'],names+aliases)[1]:can_verify=True
   if not can_verify:continue
   updated=copy.deepcopy(person);updated['sourceNames']=list(dict.fromkeys(names+aliases));updated['website']={'url':url,'kind':'party'}
   jobs.append(updated);proof.append({'id':person['id'],'name':person['name'],'aliases':aliases,'sourceURL':url,'basis':'同一人物の党公式h1に記載された姓名とふりがなのみから表記対応。読み方の推定・外部辞書は使用しない。'});break
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:refreshed={p['id']:p for p in pool.map(E.process,jobs)}
 results=[refreshed.get(r['id'],r) for r in results];E.OUTPUT.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
 (E.BASE/'komei-a-name-aliases.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'reprocessedPeople':len(refreshed),'findingsOnReprocessed':sum(len(r['findings']) for r in refreshed.values())},ensure_ascii=False))
 asyncio.run_coroutine_threadsafe(E.SESSION.close(),E.LOOP).result();E.LOOP.call_soon_threadsafe(E.LOOP.stop)
if __name__=='__main__':main()
