#!/usr/bin/env python3
import collections,hashlib,json,re
import enrich_komei_a as E
from pathlib import Path

def main():
 original=json.loads(E.INPUT.read_text());results=json.loads(E.OUTPUT.read_text());byid={r['id']:r for r in original};assert len(results)==1321==len(original);assert len({r['id'] for r in results})==1321
 assert {r['id'] for r in results}==set(byid)
 failures=[];facts=[]
 for r in results:
  o=byid[r['id']];assert r['name']==o['name'] and r['municipalityCode']==o['municipalityCode'];assert r['enrichment']['checkedAt']=='2026-11-05';assert r['enrichment']['status'] in ['情報追加','既存内容確認','追加根拠未確認','取得失敗']
  assert r['enrichment']['attempted']
  for f in r['findings']:
   assert f['checkedAt']=='2026-11-05';assert f['sourceType'] in ['本人発信','政党公式','行政・議会'];assert f['url'].startswith(('https://','http://'));assert f['evidence']['matchedName']==o['name'];assert f['evidence']['sectionHeading'];assert f['evidence']['rule']
   privacy=E.POLICY_PRIVATE if f['category']=='policy' else E.PRIVATE
   if privacy.search(f['summary']):failures.append({'id':r['id'],'title':f['title']})
   facts.append(f)
 assert not failures,failures
 attempts=[a for r in results for a in r['enrichment']['attempted']]
 report=dict(checkedAt='2026-11-05',inputCount=len(original),resultCount=len(results),peopleWithAddedFacts=sum(bool(r['findings']) for r in results),additionalFindings=len(facts),categoryCounts=dict(collections.Counter(f['category'] for f in facts)),sourceTypeCounts=dict(collections.Counter(f['sourceType'] for f in facts)),statusCounts=dict(collections.Counter(r['enrichment']['status'] for r in results)),attemptRecords=len(attempts),uniqueAttemptURLs=len({a['url'] for a in attempts}),peopleWithPersonalWebsite=sum(r.get('website',{}).get('kind')=='personal' for r in results),remainingFailedAttempts=sum('取得失敗' in a['status'] for a in attempts),privateInformationPatternHits=0,missingEvidence=0,inputSHA256=hashlib.sha256(E.INPUT.read_bytes()).hexdigest(),outputSHA256=hashlib.sha256(E.OUTPUT.read_bytes()).hexdigest(),note='全1321人を含む。findingsは今回追加した事実のみ。追加がないことを経歴・活動の不存在と判断しない。本人発信・政党公式を区別し、個人と共有団体の出典帰属を監査。既存内容確認は公開ページ取得・本人同定を指し、元の全経歴の再検証ではない。画像・PDFのみの情報はこのHTML本文抽出では追加していない。')
 (E.BASE/'komei-a-enrichment-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False),flush=True)
 import asyncio
 asyncio.run_coroutine_threadsafe(E.SESSION.close(),E.LOOP).result();E.LOOP.call_soon_threadsafe(E.LOOP.stop)
if __name__=='__main__':main()
