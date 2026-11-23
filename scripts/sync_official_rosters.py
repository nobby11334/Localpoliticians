"""Verify and ingest municipal election-office PDF candidate rosters.

This adapter is deliberately narrow: only explicitly configured official rosters.
It refuses to publish partial/ambiguous extractions or silently discard candidates.
"""
import datetime as dt
import json
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'data/official-rosters.json'
OUTPUT=ROOT/'data/imports/official-roster-candidates.json'
STATUS=ROOT/'data/official-rosters-status.json'

def extract(text):
    """Read rows of Japanese election commission candidacy PDFs with ordinal + spaced name."""
    rows=[]
    for line in text.splitlines():
        match=re.match(r'^\s*(\d{1,3})\s+([^\s\d()（）]+)\s+([^\s\d()（）]+)\s+',line)
        if match:
            number=int(match.group(1))
            name=match.group(2)+match.group(3)
            if 1<=number<=300 and 2<=len(name)<=30:
                rows.append((number,name))
    return rows

def parse_document(text,conf):
    if conf['documentTitle'] not in text or conf['finalMarker'] not in text:
        raise ValueError('Official election title or final-filing marker missing')
    rows=extract(text)
    unique={n for n,_ in rows}
    if not rows or len(unique)!=len(rows) or set(unique)!=set(range(1,len(rows)+1)):
        raise ValueError('Noncontiguous/ambiguous candidate enumeration')
    if not conf['minCandidates']<=len(rows)<=conf['maxCandidates']:
        raise ValueError('Candidate-count verification failed')
    return [name for _,name in sorted(rows)]

def load_pdf(conf):
    url=conf['url']
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!=conf['host'] or parsed.username or parsed.password:
        raise ValueError('Untrusted source host')
    req=urllib.request.Request(url,headers={'User-Agent':'Localpoliticians/1.0 official document reader'})
    with urllib.request.urlopen(req,timeout=22) as resp:
        if urlparse(resp.geturl()).hostname!=conf['host']:
            raise ValueError('Untrusted redirect')
        blob=resp.read(2500001)
    if len(blob)>2500000 or not blob.startswith(b'%PDF-'):
        raise ValueError('Not a bounded PDF file')
    with tempfile.TemporaryDirectory() as d:
        file=Path(d)/'roster.pdf'
        file.write_bytes(blob)
        result=subprocess.run(['pdftotext','-layout',str(file),'-'],capture_output=True,text=True,timeout=15,check=True)
        return result.stdout

def person(conf,name):
    return {
        'municipalityCode':conf['municipalityCode'],'name':name,
        'office':'首長選立候補予定者' if conf['electionType']=='mayor' else '議員選立候補予定者',
        'asOf':conf['publishedAt'],'collectedAt':dt.datetime.now(dt.timezone.utc).date().isoformat(),
        'rosterKind':'選管確定届出名簿','sourceURL':conf['url'],'sourceTitle':conf['documentTitle'],
        'party':'党派未確認（出典参照）','findings':[],
        'candidate':{'target':conf['electionName'],'electionType':conf['electionType'],
            'status':'正式届出','announcedAt':conf['publishedAt'],
            'note':'選挙管理委員会の確定届出名簿に掲載。党派・詳細は原資料を参照。',
            'sources':[{'url':conf['url'],'title':conf['documentTitle'],'date':conf['publishedAt']}]}
    }

def sync():
    previous=json.loads(OUTPUT.read_text()) if OUTPUT.exists() else []
    # Preserve records from providers that temporarily fail.
    existing={(p['municipalityCode'],p['candidate']['target']):[] for p in previous}
    for p in previous:existing[(p['municipalityCode'],p['candidate']['target'])].append(p)
    reports=[]
    for conf in json.loads(CONFIG.read_text())['sources']:
        if not conf.get('enabled',False):continue
        key=(conf['municipalityCode'],conf['electionName'])
        try:
            text=load_pdf(conf)
            names=parse_document(text,conf)
            verified=[person(conf,n) for n in names]
            existing[key]=verified
            reports.append({'id':conf['id'],'ok':True,'count':len(verified)})
        except Exception as error:
            reports.append({'id':conf['id'],'ok':False,'error':str(error)[:200]})
    output=[p for group in existing.values() for p in group]
    output.sort(key=lambda x:(x['municipalityCode'],x['candidate']['target'],x['name']))
    OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    STATUS.write_text(json.dumps({'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'records':len(output),'sources':reports},ensure_ascii=False,indent=2)+'\n')
    print('Official filed candidates',len(output),'sources',len(reports),'errors',sum(not x['ok'] for x in reports))
if __name__=='__main__':sync()
