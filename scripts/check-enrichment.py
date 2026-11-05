"""Validate complete identity coverage and provenance of additional facts."""
import json,collections,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
paths=sorted((ROOT/'data/enrichment').glob('people-*.json.gz'))
if not paths:raise SystemExit('No enrichment dataset installed')
raw=[r for path in paths for r in json.loads(gzip.decompress(path.read_bytes()))];mayors=[r for path in sorted((ROOT/'data/enrichment').glob('mayors-*.json.gz')) for r in json.loads(gzip.decompress(path.read_bytes()))]
assert len(raw)==7878 and len({p['id'] for p in raw})==7878
assert len(mayors)==1741 and len({p['municipalityCode'] for p in mayors})==1741
regions={p.stem:json.loads(p.read_text()) for p in (ROOT/'data/regions').glob('*.json')}
for r in raw:
 p=next(p for p in regions[r['municipalityCode']]['people'] if p['id']==r['id'])
 assert p['enrichment']['checkedAt']=='2026-11-05'
 assert p['enrichment']['status'] in ['情報追加','既存内容確認','追加根拠未確認','取得失敗']
 for f in r['findings']:
  assert f['evidence']['matchedName'] and f['evidence']['sectionHeading']
  assert f.get('asOf') and f.get('period') and f.get('checkedAt')
  assert len(f['summary'])<650, (r['name'],f['summary'])
  assert not any(x in f['summary'] for x in ['@','〒','TEL:','電話番号','FAX:']),r['name']
  assert not ('cdp-japan.jp/election/' in f['url'] and not any(x in f['evidence'].get('selector','') for x in ['member-detail','本人','card'])),r['name']
for r in mayors:
 out=regions[r['municipalityCode']]['mayorResearch'];assert out['name']==r['name']
 assert out['snapshotAsOf']=='2025-04-30'
print('PASS: all 7,878 person records and 1,741 historical chief snapshots covered; identity, source scope, dates, no contact-field contamination')
