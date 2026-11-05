"""Report possible shared-page contamination for manual review before publication."""
import json,collections,unicodedata,re,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
byurl=collections.defaultdict(list);exact=collections.defaultdict(set)
for path in (ROOT/'data/enrichment').glob('people-*.json.gz'):
 for p in json.loads(gzip.decompress(path.read_bytes())):
  for f in p['findings']:
   byurl[f['url']].append((p['name'],f['title'],f['summary']))
   exact[(f['url'],f['summary'])].add(p['name'])
issues=[]
for (url,text),names in exact.items():
 if len(names)>1:issues.append({'url':url,'names':sorted(names),'summary':text})
print(json.dumps({'sharedExactFacts':issues,'sharedURLs':{u:len(set(x[0] for x in rows)) for u,rows in byurl.items() if len(set(x[0] for x in rows))>1}},ensure_ascii=False,indent=2))
