"""Apply additive evidence; keep historical chief snapshots separate from current rosters."""
import json,hashlib,re,gzip
from collections import Counter

def apply_enrichment(root,regions,registry,norm):
 paths=sorted((root/'data/enrichment').glob('people-*.json.gz'))
 if not paths:return {}
 records=[r for path in paths for r in json.loads(gzip.decompress(path.read_bytes()))]
 mayors=[r for path in sorted((root/'data/enrichment').glob('mayors-*.json.gz')) for r in json.loads(gzip.decompress(path.read_bytes()))]
 seen=set();counts=Counter();report={}
 def apply(p,r,snapshot=False):
  added=0
  for f in r.get('findings',[]):
   assert f.get('evidence',{}).get('matchedName'), (r['name'],'missing identity evidence')
   assert f['category'] in ['career','community','organization','party','policy','activity']
   assert f['url'].startswith(('http://','https://'))
   assert norm(f['evidence']['matchedName'])==norm(r['name']),r['name']
   if any(x.get('url')==f['url'] and norm(x.get('title',''))==norm(f.get('title','')) and norm(x.get('summary',''))==norm(f.get('summary','')) for x in p['findings']):continue
   f=dict(f)
   evidence=f.get('evidence',{});alias=evidence.get('observedMatchedName') or evidence.get('matchedAlias')
   if alias and (evidence.get('identitySources') or evidence.get('identitySourceURL')) and re.fullmatch(r'[一-龯髙﨑塚々ぁ-ゖァ-ヺーA-Za-z・ 　]{2,30}',alias):
    if norm(alias) not in {norm(n) for n in p.get('sourceNames',[p['name']])}:p.setdefault('sourceNames',[p['name']]).append(alias)
   f['id']='enriched-'+hashlib.sha256((p['id']+f['url']+f['title']+f.get('summary','')).encode()).hexdigest()[:20]
   f['method']='公開プロフィールの該当節から抽出（出典の記載）'
   if f['category']=='activity' and '本人' in f.get('sourceType',''):f['stage']='本人による活動の記述（外部資料との照合前）'
   p['findings'].append(f);added+=1
  e=dict(r['enrichment']);e['addedFindings']=added
  if added:e['status']='情報追加'
  elif e.get('status')=='情報追加':e['status']='既存内容確認'
  p['enrichment']=e
  w=r.get('website')
  if isinstance(w,dict):w={**w,'kind':{'personal':'本人ホームページ','party':'政党公式の紹介','official':'行政・議会の紹介'}.get(w.get('kind'),w.get('kind','掲載プロフィール'))}
  if isinstance(w,dict) and w.get('url','').startswith(('http://','https://')):
   # Prefer a verified personal site over a party roster, preserving curated personal links.
   if not p.get('website') or ('本人' in w.get('kind','') and '本人' not in p['website'].get('kind','')):p['website']=w
   elif p['website'].get('url')!=w['url'] and not any(x['url']==w['url'] for x in p.get('relatedWebsites',[])):p.setdefault('relatedWebsites',[]).append(w)
  counts['snapshotAddedFindings' if snapshot else 'addedFindings']+=added
  if added:counts['snapshotsWithAdditions' if snapshot else 'peopleWithAdditions']+=1
  return added
 for r in records:
  code=r['municipalityCode'];assert code in registry
  assert r['id'] not in seen;seen.add(r['id'])
  p=regions[code].get(r['id']);assert p and norm(p['name'])==norm(r['name']),(code,r['name'])
  apply(p,r);counts['peopleChecked']+=1;counts[p['enrichment']['status']]+=1
 for r in mayors:
  code=r['municipalityCode'];assert code in registry
  assert norm(registry[code]['mayor']['name'])==norm(r['name']),(code,r['name'])
  p={'id':'snapshot-'+code,'name':r['name'],'findings':[]}
  apply(p,r,snapshot=True);report[code]={'name':r['name'],'snapshotAsOf':r.get('snapshotAsOf',registry[code]['mayor']['asOf']),'findings':p['findings'],'enrichment':p['enrichment']}
  if p.get('website'):report[code]['website']=p['website']
  for existing in regions[code].values():
   if existing.get('role')=='mayor' and norm(existing['name'])==norm(r['name']):
    old=existing.get('enrichment',{});apply(existing,r)
    existing['enrichment']['attempted']=list({x['url']:x for x in old.get('attempted',[])+existing['enrichment'].get('attempted',[])}.values())
  regions[code] # Also generate a region file for municipalities with only a chief snapshot.
 # Count final added facts per displayed identity, including same-name snapshot evidence.
 counts['addedFindings']=0;counts['peopleWithAdditions']=0
 for status in ['情報追加','既存内容確認','追加根拠未確認','取得失敗']:counts[status]=0
 for ps in regions.values():
  for p in ps.values():
   n=sum(bool(f.get('method')) for f in p['findings'])
   if p.get('enrichment'):
    p['enrichment']['addedFindings']=n
    if n:p['enrichment']['status']='情報追加'
    counts[p['enrichment']['status']]+=1
   counts['addedFindings']+=n;counts['peopleWithAdditions']+=bool(n)
 counts['mayorSnapshotsChecked']=len(mayors)
 report['_summary']=dict(counts)
 return report
