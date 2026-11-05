#!/usr/bin/env python3
"""Audit identity, source containment and private-data exclusions without network access."""
import os,json,pathlib,collections,hashlib,sys,importlib.util,re
ROOT=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('profile_acquisition',ROOT/'enrich_profiles.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
INPUT=M.INPUT;OUTPUT=M.OUTPUT;CACHE=M.CACHE
REPORT=pathlib.Path(os.environ.get('POLITICIAN_RESEARCH_AUDIT',str(OUTPUT.with_suffix('.audit.json'))))
raw=json.loads(INPUT.read_text());rows=json.loads(OUTPUT.read_text());byid={p['id']:p for p in raw};issues=[];checked={};content_hashes={}
if len(rows)!=len(raw):issues.append({'reason':'input/output count mismatch','input':len(raw),'output':len(rows)})
if len({p['id']for p in rows})!=len(rows):issues.append({'reason':'duplicate output IDs'})
if set(p['id']for p in rows)!=set(byid):issues.append({'reason':'input/output ID sets differ'})
for row in rows:
 p=byid.get(row['id'])
 if not p:continue
 def issue(reason,index=None):issues.append({'id':row['id'],'name':row['name'],'findingIndex':index,'reason':reason})
 if row['name']!=p['name']or row['municipalityCode']!=p['municipalityCode']:issue('identity keys changed')
 e=row.get('enrichment',{})
 if not e.get('attempted'):issue('no attempted URLs')
 if e.get('checkedAt')!=M.CHECKED:issue('record checkedAt differs')
 for i,f in enumerate(row.get('findings',[])):
  ev=f.get('evidence',{});key=ev.get('cacheKey');retrieval=ev.get('retrievalURL','')
  if ev.get('matchedName')!=row['name']or not ev.get('sectionHeading')or not ev.get('rule'):issue('missing identity/section evidence',i);continue
  if key!=hashlib.sha256(retrieval.split('#')[0].encode()).hexdigest():issue('retrieval URL/cacheKey mismatch',i);continue
  if M.PRIV.search(f.get('summary','')):issue('private/contact/birth/family pattern in summary',i)
  if f.get('checkedAt')!=M.CHECKED:issue('finding checkedAt differs',i)
  ck=(row['id'],key)
  if ck not in checked:
   try:
    data=json.loads((CACHE/(key+'.json')).read_text())['data'];t=M.tree(data);sc,individual=M.scope(t,M.names(p),data['url'])
    checked[ck]=(data,sc,individual)
   except Exception:checked[ck]=(None,None,False)
  data,sc,individual=checked[ck]
  if not individual or sc is None:issue('source is not a verified single-person page',i);continue
  if f['url']!=data['url']:issue('finding URL differs from resolved source',i)
  body=M.norm(M.txt(sc));summary=f['summary']
  if f['category']=='policy':
   match=re.search(r'掲載項目で(.+?)に言及',summary)
   if not match or any(M.norm(theme)not in body for theme in match.group(1).split('・')):issue('policy topics not found in scoped source',i)
  else:
   claim=summary.removesuffix('とプロフィールに記載。')
   if M.norm(claim)not in body:issue('biography claim not contained in scoped source',i)
  digest=hashlib.sha256(data['text'].encode('utf-8')).hexdigest()
  if ev.get('contentSha256')and ev['contentSha256']!=digest:issue('decoded HTML digest mismatch',i)
  content_hashes[(row['id'],i)]=digest
if '--stamp' in sys.argv and not issues:
 for row in rows:
  for i,f in enumerate(row.get('findings',[])):f['evidence']['contentSha256']=content_hashes[(row['id'],i)]
 temp=OUTPUT.with_suffix('.audit-stamped.tmp');temp.write_text(json.dumps(rows,ensure_ascii=False,indent=2));temp.replace(OUTPUT)
report={'checkedAt':M.CHECKED,'inputCount':len(raw),'outputCount':len(rows),'statusCounts':dict(collections.Counter(p['enrichment']['status']for p in rows)),'newFindingCount':sum(len(p['findings'])for p in rows),'categoryCounts':dict(collections.Counter(f['category']for p in rows for f in p['findings'])),'websiteCount':sum(bool(p.get('website'))for p in rows),'attemptedURLCount':len({a['url']for p in rows for a in p['enrichment']['attempted']}),'scopedSourceChecks':len(checked),'issueCount':len(issues),'issues':issues}
REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in report.items()if k!='issues'},ensure_ascii=False))
sys.exit(bool(issues))
