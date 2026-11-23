"""Import official, machine-readable election-result feeds. Fail closed on ambiguity."""
import csv, datetime as dt, io, json, os, re, unicodedata, urllib.request
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/'data/election-sources.json'
OUTPUT=ROOT/'data/election-results.json'
def norm(s):
    return re.sub(r'[\s　]','',unicodedata.normalize('NFKC',str(s))).translate(str.maketrans({'﨑':'崎','髙':'高','塚':'塚'}))
def date(s):
    dt.date.fromisoformat(str(s))
    return str(s)
def valid_url(url):
    p=urlparse(str(url))
    return p.scheme=='https' and bool(p.hostname) and not p.username and not p.password
def validate(record,source):
    if not isinstance(record,dict): raise ValueError('Record must be an object')
    required=('electionId','municipalityCode','electionDate','office','candidateName','result','sourceURL','publishedAt')
    if any(not record.get(k) for k in required): raise ValueError('Missing election result fields')
    if not re.fullmatch(r'\d{5}',str(record['municipalityCode'])): raise ValueError('Invalid municipality code')
    if record['office'] not in ('mayor','council'): raise ValueError('Invalid office')
    if record['result'] not in ('elected','not_elected'): raise ValueError('Invalid result')
    date(record['electionDate']);date(record['publishedAt'])
    if not valid_url(record['sourceURL']): raise ValueError('Invalid evidence URL')
    if urlparse(record['sourceURL']).hostname not in source['allowedEvidenceHosts']: raise ValueError('Evidence host not allowlisted')
    if not (record['electionId'].strip() and norm(record['candidateName'])): raise ValueError('Missing identity')
    if record.get('votes') not in (None,''):
        if not isinstance(record['votes'],int) or record['votes']<0: raise ValueError('Invalid votes')
    if record.get('termStart'): date(record['termStart'])
    if record.get('termEnd'): date(record['termEnd'])
    if record.get('termStart') and record['result']!='elected': raise ValueError('Loser cannot have new term')
    if record.get('termEnd') and not record.get('termStart'): raise ValueError('Missing term start')
    if record.get('termEnd') and record['termEnd']<record['termStart']: raise ValueError('Invalid term')
    return {k:record[k] for k in required+('votes','termStart','termEnd','district','uncontested','personId') if k in record}
def read_source(source):
    endpoint=source['url']
    if not valid_url(endpoint) or urlparse(endpoint).hostname not in source['allowedEvidenceHosts']: raise ValueError('Source host not allowlisted')
    req=urllib.request.Request(endpoint,headers={'User-Agent':'Localpoliticians/1.0 election results monitor'})
    with urllib.request.urlopen(req,timeout=25) as response:
        if urlparse(response.geturl()).hostname not in source['allowedEvidenceHosts']: raise ValueError('Redirected to untrusted host')
        raw=response.read(5_000_001)
    if len(raw)>5_000_000: raise ValueError('Feed exceeds 5MB')
    text=raw.decode('utf-8-sig')
    if source['format']=='json':
        parsed=json.loads(text)
        records=parsed['results'] if isinstance(parsed,dict) else parsed
    elif source['format']=='csv': records=list(csv.DictReader(io.StringIO(text)))
    else: raise ValueError('Unsupported format')
    if not isinstance(records,list): raise ValueError('Feed is not an array')
    out=[]
    for row in records:
        if source['format']=='csv':
            row={**row,'votes':int(row['votes']) if row.get('votes') else None}
            row={k:v for k,v in row.items() if v not in ('',None)}
        out.append(validate(row,source))
    return out
def sync():
    configs=json.loads(SOURCES.read_text(encoding='utf-8'))['sources']
    previous=json.loads(OUTPUT.read_text(encoding='utf-8')) if OUTPUT.exists() else {'results':[]}
    # Preserve previously verified results when individual providers fail.
    merged={(r['electionId'],r['municipalityCode'],r['office'],norm(r['candidateName'])):r for r in previous['results']}
    reports=[];all_hosts=set()
    for source in configs:
        try:
            if not source.get('enabled',False): continue
            hosts=source.get('allowedEvidenceHosts',[])
            if not hosts or not all(isinstance(h,str) and h for h in hosts): raise ValueError('Missing host allowlist')
            if not source.get('url'): raise ValueError('Missing URL')
            rows=read_source(source)
            keys=set()
            for r in rows:
                key=(r['electionId'],r['municipalityCode'],r['office'],norm(r['candidateName']))
                if key in keys: raise ValueError('Duplicate candidate in feed')
                keys.add(key)
            # Do not silently replace an existing verified result with a conflicting value.
            conflicts=[r for r in rows if (key:=(r['electionId'],r['municipalityCode'],r['office'],norm(r['candidateName']))) in merged and merged[key]['result']!=r['result']]
            if conflicts: raise ValueError('Conflicting election result needs manual review')
            for r in rows:
                key=(r['electionId'],r['municipalityCode'],r['office'],norm(r['candidateName']))
                if key not in merged or r['publishedAt']>=merged[key]['publishedAt']: merged[key]=r
            reports.append({'id':source['id'],'ok':True,'count':len(rows)})
        except Exception as ex:
            reports.append({'id':source.get('id','unknown'),'ok':False,'error':str(ex)[:240]})
    rows=sorted(merged.values(),key=lambda r:(r['electionDate'],r['municipalityCode'],r['electionId'],norm(r['candidateName'])))
    # A person with multiple identical normalized names in the same election needs manual adjudication.
    OUTPUT.write_text(json.dumps({'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'results':rows,'sources':reports},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Election results:',len(rows),'records;',len(reports),'feeds;',sum(not r['ok'] for r in reports),'failed')
if __name__=='__main__': sync()
