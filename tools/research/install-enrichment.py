"""Install completed, identity-scoped research batches. Never install partial batches."""
import argparse,json,collections,re,unicodedata,gzip
from pathlib import Path
args=argparse.ArgumentParser();args.add_argument('directory',type=Path);opt=args.parse_args()
ROOT=Path(__file__).resolve().parents[2]
files={'enriched-komei-a.json':1321,'enriched-komei-b.json':1320,'enriched-jcp.json':2042,'enriched-other-a.json':1598,'enriched-other-b.json':1597}
originals={r['id']:r for filename in ['komei-a.json','komei-b.json','jcp.json','other-a.json','other-b.json'] for r in json.loads((opt.directory/filename).read_text())}
def normalized_name(s):return re.sub(r'[\s　]','',unicodedata.normalize('NFKC',s)).translate(str.maketrans({'﨑':'崎','髙':'高','塚':'塚'}))
def normalized_url(s):return (s or '').replace('http://','https://',1).rstrip('/')
people=[]
for name,count in files.items():
 d=json.loads((opt.directory/name).read_text())
 if isinstance(d,dict):d=d.get('people',d.get('results',[]))
 assert len(d)==count,(name,len(d),count)
 people+=d
assert len({p['id'] for p in people})==7878
mayors=json.loads((opt.directory/'enriched-mayors.json').read_text())
if isinstance(mayors,dict):mayors=mayors.get('people',mayors.get('results',[]))
assert len(mayors)==1741
for p in people+mayors:
 for key in list(p):
  if key not in ['id','municipalityCode','name','findings','website','enrichment','snapshotAsOf','profileURL']:del p[key]
 p['findings']=[{k:v for k,v in f.items() if k in ['category','title','summary','period','url','sourceType','asOf','checkedAt','evidence','organization','asOfBasis','stage']} for f in p.get('findings',[])]
 for attempt in p.get('enrichment',{}).get('attempted',[]):
  if attempt.get('error'):
   error=str(attempt['error']);http=re.search(r'\b(4\d\d|5\d\d)\b',error)
   attempt['error']='HTTP '+http.group(1) if http else '応答待ち時間超過' if re.search(r'time.?out|timed out',error,re.I) else '本文または接続を確認できず'
 for f in p.get('findings',[]):
  # Preserve the extraction scope, without retaining copies of source paragraphs.
  f['evidence']={k:v for k,v in f.get('evidence',{}).items() if k in ['matchedName','sectionHeading','selector','rule','identitySourceURL','matchedAlias','sourceName','matchedSourceName','observedMatchedName','identitySources','discoveryLinkLabel','cacheSHA256','cacheKey','sourceCacheSHA256','contentSHA256','fetchedURL','originalMatchedName','contentSha256','retrievalURL']}
  assert f['evidence'].get('matchedName') and f['evidence'].get('sectionHeading'),p['name']
  if normalized_name(f['evidence']['matchedName'])!=normalized_name(p['name']):
   original=originals[p['id']];w=original.get('website');w=w.get('url') if isinstance(w,dict) else w
   known_urls=[w,original.get('sourceURL'),original.get('profileURL')]+[x.get('url') for x in original.get('sources',[])]+[x.get('url') for x in original.get('findings',[])]
   proof=f['evidence'].get('identitySourceURL')
   assert proof and normalized_url(proof) in {normalized_url(u) for u in known_urls if u},(p['name'],'alias without matching original identity source')
   f['evidence']['observedMatchedName']=f['evidence']['matchedName'];f['evidence']['matchedName']=p['name']
  assert f['url'].startswith(('http://','https://'))
  if not re.search(r'(?:19|20)\d{2}|(?:明治|大正|昭和|平成|令和)(?:元|\d+)年',f.get('period','')):
   dates=re.findall(r'(?:(?:19|20)\d{2}|(?:明治|大正|昭和|平成|令和)(?:元|\d+))年(?:\d{1,2}月)?(?:\d{1,2}日)?',f.get('summary',''))
   if dates:f['period']='・'.join(dict.fromkeys(dates))
   elif re.search(r'出典記載の時期|本文で確認できる範囲',f.get('period','')):f['period']='時期未確認'
 assert p.get('enrichment',{}).get('checkedAt')=='2026-11-05',p['name']
 path=ROOT/'data/enrichment';path.mkdir(exist_ok=True)
for name,d in [('people',sorted(people,key=lambda p:p['id'])),('mayors',sorted(mayors,key=lambda p:p['municipalityCode']))]:
 for i in range(0,len(d),500):
  payload=(json.dumps(d[i:i+500],ensure_ascii=False,separators=(',',':'))+'\n').encode()
  (path/(name+'-'+str(i//500).zfill(2)+'.json.gz')).write_bytes(gzip.compress(payload,mtime=0))
for old in path.glob('*.json'):old.unlink()
print(json.dumps({'people':len(people),'mayorSnapshots':len(mayors),'newSourceFacts':sum(len(p.get('findings',[])) for p in people+mayors),'statuses':dict(collections.Counter(p['enrichment']['status'] for p in people))},ensure_ascii=False))
