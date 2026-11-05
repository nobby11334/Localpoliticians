"""Recheck known transient transport failures and audit all completed records.
Run only after enrich-jcp.py has completed its full assigned roster.
"""
from pathlib import Path
import importlib.util
import sys,json,concurrent.futures,collections,re,urllib.parse
if '--help' in sys.argv:
 print('Usage: python retry_audit_jcp.py [--audit-only]\nUses the same JCP_* environment variables as enrich_jcp.py. See README.md.')
 sys.exit(0)
BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('enrich_jcp',BASE/'enrich_jcp.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
path=m.OUTPUT;output=json.loads(path.read_text());byid={r['id']:r for r in output};originals={r['id']:r for r in m.rows}
def require(condition,message):
 if not condition:raise ValueError('Audit failed: '+message)
def transient(a):
 e=a.get('error','');u=a['url']
 if a.get('status')!='取得失敗':return False
 return (not e or 'CERTIFICATE_VERIFY_FAILED' in e or ('/list/member/' in u and re.search(r'Timeout|ConnectError',e)) or ('403' in e and "url 'http://" in e))
audit_only='--audit-only' in sys.argv
if len(output)!=len(originals) or {r['id'] for r in output}!=set(originals):raise ValueError('Completed output must contain every input ID exactly once')
todo=[] if audit_only else [originals[r['id']] for r in output if any(transient(a) for a in r['enrichment']['attempted'])]
for r in ([] if audit_only else output):
 for a in r['enrichment']['attempted']:
  if not transient(a):continue
  # Recreate only transport-failure cache entries, not genuine 404/410 pages.
  u=a['url'];p=m.cachepath(u)
  if p.exists():p.unlink()
  if u.startswith('http://'):
   p=m.cachepath('https://'+u[7:])
   if p.exists():
    f=json.loads(p.read_text())
    if f['status']=='取得失敗' and (not f.get('error') or re.search(r'Timeout|CERTIFICATE_VERIFY_FAILED',f.get('error',''))):p.unlink()
print('RETRY',len(todo),flush=True)
patch=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=m.WORKERS) as pool:
 fs={pool.submit(m.enrich,p):p for p in todo}
 for f in concurrent.futures.as_completed(fs):
  p=fs[f]
  try:
   r=f.result();byid[p['id']]=r;patch.append(r)
  except Exception as e:print('PATCH_ERROR',p['name'],type(e).__name__,str(e)[:100],flush=True)
  if len(patch)%10==0:print('PATCHED',len(patch),'/',len(todo),flush=True)
m.RETRY_OUTPUT.write_text(json.dumps(patch,ensure_ascii=False,indent=2)+'\n')
output=[byid[r['id']] for r in m.rows]
dropped=m.audit_shared_sources(output)
require(len(output)==len(originals) and len({r['id'] for r in output})==len(originals),"len(output)==len(originals) and len({r['id'] for r in output})==len(originals)")
require({r['id'] for r in output}==set(originals),"{r['id'] for r in output}==set(originals)")
require(all(r['enrichment']['checkedAt']==m.DATE for r in output),"all(r['enrichment']['checkedAt']==m.DATE for r in output)")
require(all(r['enrichment']['attempted'] for r in output),"all(r['enrichment']['attempted'] for r in output)")
require(all(f.get('evidence',{}).get('matchedName')==r['name'] for r in output for f in r['findings']),"all(f.get('evidence',{}).get('matchedName')==r['name'] for r in output for f in r['findings'])")
require(all(not m.PRIVATE.search(f['summary']) for r in output for f in r['findings']),"all(not m.PRIVATE.search(f['summary']) for r in output for f in r['findings'])")
require(all(len({m.norm(f['summary']) for f in r['findings']})==len(r['findings']) for r in output),"all(len({m.norm(f['summary']) for f in r['findings']})==len(r['findings']) for r in output)")
path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
report={'total':len(output),'checkedAt':m.DATE,'statusCounts':dict(collections.Counter(r['enrichment']['status'] for r in output)),'findingCount':sum(len(r['findings']) for r in output),'categoryCounts':dict(collections.Counter(f['category'] for r in output for f in r['findings'])),'sourceTypeCounts':dict(collections.Counter(f['sourceType'] for r in output for f in r['findings'])),'websiteCount':sum('website' in r for r in output),'attemptCount':sum(len(r['enrichment']['attempted']) for r in output),'peopleWithSuccessfulFetch':sum(any(a['status']=='取得成功' for a in r['enrichment']['attempted']) for r in output),'transportRetryPeople':len(patch),'finalAuditFindingsDropped':dropped,'notes':['入力の全IDを維持。入力の漢字名・かな名の重複候補は推測統合しない。','追加事実のみ。名簿掲載の言い換えを水増ししない。','掲載日時不明の資料は取得日と区別し、現在の在職・次回出馬を推測しない。','共有トップ本文、党/議員団の共同実績・政策は個人事実に帰属させない。','追加根拠未確認は経歴や役職がないことを意味しない。']}
m.REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('FINAL',json.dumps(report,ensure_ascii=False),flush=True)
