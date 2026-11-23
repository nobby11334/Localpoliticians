"""Synchronize an officially certified municipal mayoral vote count PDF.

Only a configured election and an exact, complete vote table are accepted.
On HTTP denial, retain already verified results and expose the error.
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
OUT=ROOT/'data/election-results.json'
STATUS=ROOT/'data/official-vote-status.json'
URL='https://www.city.yachimata.lg.jp/uploaded/attachment/28757.pdf'
ELECTION='12230-mayor-2026-11-22'
CODE='12230'

def parse(text):
    if not all(token in text.replace(' ','') for token in ('八街市長選挙','開票結果','確定')):
        raise ValueError('Not a certified election result document')
    rows=[]
    for line in text.splitlines():
        match=re.search(r'^\s*([12])\s+無所属\s+([\u3040-\u30ff\u3400-\u9fff\s]+?)\s+(\d{1,3}(?:,\d{3})+)\s*$',line)
        if match:rows.append((int(match.group(1)),''.join(match.group(2).split()),int(match.group(3).replace(',',''))))
    if len(rows)!=2 or {r[0] for r in rows}!={1,2} or sum(r[2] for r in rows)!=19189:
        raise ValueError('Certified count not fully extracted')
    maximum=max(r[2] for r in rows)
    if sum(r[2]==maximum for r in rows)!=1:raise ValueError('Tied winner cannot be inferred')
    return [{'electionId':ELECTION,'municipalityCode':CODE,'electionDate':'2026-11-22',
            'office':'mayor','candidateName':name,
            'result':'elected' if votes==maximum else 'not_elected',
            'votes':votes,'sourceURL':URL,'publishedAt':'2026-11-22','uncontested':False}
            for _,name,votes in sorted(rows)]

def fetch():
    request=urllib.request.Request(URL,headers={'User-Agent':'Localpoliticians/1.0 official election monitor'})
    with urllib.request.urlopen(request,timeout=22) as response:
        if urlparse(response.geturl()).hostname!='www.city.yachimata.lg.jp':raise ValueError('Untrusted redirect')
        blob=response.read(2000001)
    if not blob.startswith(b'%PDF-') or len(blob)>2000000:raise ValueError('Invalid PDF')
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'result.pdf';path.write_bytes(blob)
        return subprocess.run(['pdftotext','-layout',str(path),'-'],capture_output=True,text=True,check=True,timeout=15).stdout

def sync():
    try:
        verified=parse(fetch())
        contents=json.loads(OUT.read_text())
        retained=[x for x in contents['results'] if x['electionId']!=ELECTION]
        contents['results']=retained+verified
        contents['updatedAt']=dt.datetime.now(dt.timezone.utc).isoformat()
        OUT.write_text(json.dumps(contents,ensure_ascii=False,indent=2)+'\n')
        report={'ok':True,'count':len(verified),'updatedAt':contents['updatedAt']}
        print('Yachimata official certified vote records:',len(verified))
    except Exception as error:
        report={'ok':False,'error':str(error)[:200],
            'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat()}
        print('Official vote PDF cannot be refreshed; preserved verified results:',report['error'])
    STATUS.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':sync()
