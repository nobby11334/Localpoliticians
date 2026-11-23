"""Safely import official structured candidate announcements; never interpret news headlines as facts."""
import csv,datetime as dt,io,json,re,unicodedata,urllib.request
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
C=ROOT/'data/candidate-sources.json'
OUT=ROOT/'data/imports/verified-candidates.json'
REPORT=ROOT/'data/candidate-sync-status.json'
STATES={'本人表明':1,'公認発表':1,'推薦発表':1,'正式届出':2}
def norm(s):
 return re.sub(r'[\s　]','',unicodedata.normalize('NFKC',str(s))).translate(str.maketrans({'﨑':'崎','髙':'高','塚':'塚'}))
def check_date(s):return dt.date.fromisoformat(str(s))
def host(url):
 p=urlparse(str(url))
 if p.scheme!='https' or not p.hostname or p.username or p.password:raise ValueError('HTTPS required')
 return p.hostname.lower()
def validate(row,conf,codes):
 for k in ('candidateName','municipalityCode','electionType','electionName','status','sourceURL','publishedAt'):
  if not str(row.get(k) or '').strip():raise ValueError('Missing '+k)
 code=str(row['municipalityCode']).zfill(5)
 if code not in codes:raise ValueError('Unknown municipality')
 if row['electionType'] not in ('mayor','council'):raise ValueError('Invalid election type')
 if row['status'] not in STATES:raise ValueError('Invalid candidacy status')
 if row['status']=='正式届出' and conf['authority']!='election_commission':raise ValueError('Official filing requires election commission')
 check_date(row['publishedAt'])
 if row.get('electionDate'):check_date(row['electionDate'])
 if host(row['sourceURL']) not in conf['allowedEvidenceHosts']:raise ValueError('Untrusted evidence')
 name=str(row['candidateName']).strip()
 if not 2<=len(norm(name))<=80:raise ValueError('Invalid name')
 target=str(row['electionName']).strip()
 if len(target)>150:raise ValueError('Election title too long')
 if row['electionType']=='mayor' and not re.search(r'知事|市長|区長|町長|村長|首長',target):raise ValueError('Target does not match mayor')
 if row['electionType']=='council' and not re.search(r'議|議会',target):raise ValueError('Target does not match council')
 return dict(code=code,name=name,kind=row['electionType'],target=target,status=row['status'],
  url=row['sourceURL'],published=row['publishedAt'],electionDate=row.get('electionDate') or None,
  party=row.get('party') or '党派未確認',title=row.get('sourceTitle') or '候補者公表資料',authority=conf['authority'])
def fetch(conf):
 if host(conf['url']) not in conf['allowedEvidenceHosts']:raise ValueError('Untrusted feed')
 req=urllib.request.Request(conf['url'],headers={'User-Agent':'Localpoliticians/1.0'})
 with urllib.request.urlopen(req,timeout=20) as response:
  if host(response.geturl()) not in conf['allowedEvidenceHosts']:raise ValueError('Redirect outside allowlist')
  raw=response.read(4000001)
 if len(raw)>4000000:raise ValueError('Feed too large')
 text=raw.decode('utf-8-sig')
 if conf['format']=='json':
  d=json.loads(text);return d['candidates'] if isinstance(d,dict) else d
 if conf['format']=='csv':return list(csv.DictReader(io.StringIO(text)))
 raise ValueError('Unsupported format')
def key(r):return (r['code'],r['kind'],norm(r['name']),norm(r['target']))
def person(r):
 return {'municipalityCode':r['code'],'name':r['name'],
 'office':'首長選立候補予定者' if r['kind']=='mayor' else '議会議員選立候補予定者',
 'party':r['party'],'asOf':r['published'],'collectedAt':dt.datetime.now(dt.timezone.utc).date().isoformat(),
 'sourceURL':r['url'],'sourceTitle':r['title'],'rosterKind':'出典付き候補者発表資料','findings':[],
 'candidate':{'target':r['target'],'electionType':r['kind'],'status':r['status'],'announcedAt':r['published'],
 'electionDate':r['electionDate'],'authority':r['authority'],
 'note':'届出確認前の情報を正式候補者とは扱いません。',
 'sources':[{'url':r['url'],'title':r['title'],'date':r['published']}]}}
def from_person(p):
 c=p['candidate'];src=c['sources'][0]
 return dict(code=p['municipalityCode'],name=p['name'],kind=c['electionType'],target=c['target'],
 status=c['status'],url=src['url'],published=c['announcedAt'],electionDate=c.get('electionDate'),
 party=p.get('party') or '党派未確認',title=src.get('title') or '発表資料',authority=c.get('authority','election_commission'))
def main():
 codes={str(m['code']) for m in json.loads((ROOT/'data/national.json').read_text())['municipalities']}
 confs=json.loads(C.read_text())['sources']
 stored=json.loads(OUT.read_text()) if OUT.exists() else []
 merged={}
 for p in stored:
  if p.get('candidate'):
   r=from_person(p);merged[key(r)]=r
 reports=[]
 for conf in confs:
  if not conf.get('enabled',False):continue
  try:
   if conf.get('authority') not in ('election_commission','party','candidate'):raise ValueError('Invalid authority')
   if not conf.get('allowedEvidenceHosts'):raise ValueError('Host allowlist is required')
   rows=fetch(conf)
   if not isinstance(rows,list) or len(rows)>3000:raise ValueError('Invalid feed length')
   incoming=[validate(row,conf,codes) for row in rows]
   for r in incoming:
    old=merged.get(key(r))
    if old and (STATES[r['status']]<STATES[old['status']] or
      (STATES[r['status']]==STATES[old['status']] and r['published']<old['published'])):continue
    merged[key(r)]=r
   reports.append({'id':conf['id'],'ok':True,'count':len(incoming)})
  except Exception as ex:reports.append({'id':conf.get('id','unknown'),'ok':False,'error':str(ex)[:200]})
 OUT.write_text(json.dumps([person(r) for _,r in sorted(merged.items())],ensure_ascii=False,indent=2)+'\n')
 REPORT.write_text(json.dumps({'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
  'verifiedCandidateRecords':len(merged),'configuredSources':len(confs),'sources':reports},
  ensure_ascii=False,indent=2)+'\n')
 print('Candidates',len(merged),'configured sources',len(confs),'failed',sum(not x['ok'] for x in reports))
if __name__=='__main__':main()
