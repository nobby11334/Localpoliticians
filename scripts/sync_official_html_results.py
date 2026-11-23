"""Read official municipality HTML vote tables for vetted election IDs and candidates."""
import datetime as dt
import hashlib
import json
import re
import unicodedata
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from sync_prefecture_results import Tables

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'data/official-html-result-sources.json'
OUT=ROOT/'data/election-results.json'
STATUS=ROOT/'data/official-html-results-status.json'

def norm(name):
    return re.sub(r'[\s　]','',unicodedata.normalize('NFKC',str(name))).translate(str.maketrans({'﨑':'崎','髙':'高','塚':'塚'}))

def parse(text,conf):
    # Reject provisional result summaries.
    if not ('確定' in text or '当選人' in text) or not ('開票' in text or '選挙' in text):
        raise ValueError('Official final results marker absent')
    parser=Tables()
    parser.feed(text)
    valid=[]
    expected=set(conf['expected'])
    if len(expected)!=len(conf['expected']):raise ValueError('Repeated expected names')
    for table in parser.tables:
        found={}
        for row in table:
            if conf['layout']=='last':
                if len(row)<3:continue
                name=norm(row[1]);vote_string=row[-1]
            else:
                if len(row)<4:continue
                name=norm(row[0]);vote_string=row[2]
            if name not in expected:continue
            number=vote_string.replace(',','').strip()
            if not number.isdecimal():raise ValueError('Vote count not numeric')
            found[name]=(int(number),row)
        if set(found)==expected and len(found)==len(expected):valid.append(found)
    if len(valid)!=1:raise ValueError('Did not identify exactly one complete official result table')
    results=[]
    counts=valid[0]
    if any(v<=0 for v,_ in counts.values()):raise ValueError('Invalid vote count')
    if conf['layout']=='named':
        winners=[name for name,(_,row) in counts.items() if any('当選人' in cell for cell in row[3:])]
        if len(winners)!=1:raise ValueError('Winner not explicitly certified')
    else:
        highest=max(v for v,_ in counts.values())
        winners=[name for name,(votes,_) in counts.items() if votes==highest]
        if len(winners)!=1:raise ValueError('No unique leading candidate')
    for name,(votes,_) in counts.items():
        alias=conf['identity'][name]
        person_id=conf['municipalityCode']+'-'+hashlib.sha256(norm(alias).encode()).hexdigest()[:12]
        results.append({'electionId':conf['electionId'],'municipalityCode':conf['municipalityCode'],
           'electionDate':conf['electionDate'],'office':conf['office'],
           'candidateName':name,'result':'elected' if name in winners else 'not_elected',
           'votes':votes,'sourceURL':conf['url'],'publishedAt':conf['publishedAt'],
           'uncontested':False,'personId':person_id})
    return results

def fetch(url,host):
    p=urlparse(url)
    if p.scheme!='https' or p.hostname!=host:raise ValueError('Untrusted source')
    req=urllib.request.Request(url,headers={'User-Agent':'Localpoliticians/1.0 civic public records'})
    with urllib.request.urlopen(req,timeout=22) as response:
        if urlparse(response.geturl()).hostname!=host:raise ValueError('Untrusted redirect')
        body=response.read(1500001)
        encoding=response.headers.get_content_charset() or 'utf-8'
    if len(body)>1500000:raise ValueError('Excessive source size')
    return body.decode(encoding,errors='replace')

def sync():
    old=json.loads(OUT.read_text()) if OUT.exists() else {'results':[]}
    combined=list(old['results'])
    status=[]
    sources=json.loads(CONFIG.read_text())['sources']
    fetched={}
    for conf in sources:
        try:
            if conf['url'] not in fetched:
                fetched[conf['url']]=fetch(conf['url'],conf['host'])
            newer=parse(fetched[conf['url']],conf)
            # Update only fully verified election, never overwrite unrelated histories.
            combined=[r for r in combined if r['electionId']!=conf['electionId']]+newer
            status.append({'id':conf['id'],'ok':True,'count':len(newer)})
            print('Verified official HTML result',conf['id'],len(newer))
        except Exception as error:
            status.append({'id':conf['id'],'ok':False,'error':str(error)[:220]})
            print('Official HTML result retained from previous verified snapshot:',conf['id'],str(error)[:200])
    old['results']=sorted(combined,key=lambda x:(x['electionDate'],x['municipalityCode'],x['office'],norm(x['candidateName'])))
    old['updatedAt']=dt.datetime.now(dt.timezone.utc).isoformat()
    OUT.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
    STATUS.write_text(json.dumps({'updatedAt':old['updatedAt'],'sources':status},ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':sync()
