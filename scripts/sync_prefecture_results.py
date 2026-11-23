"""Ingest certified municipal mayoral winners from a prefectural election-commission table.
Only the municipality mayor section with an explicit winner is eligible; missing winners remain unknown.
"""
import datetime as dt
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'data/election-results.json'
STATUS=ROOT/'data/prefecture-results-status.json'
URL='https://www.pref.niigata.lg.jp/site/senkyo/r8-senkyoichiran.html'

class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables=[];self.table=None;self.row=None;self.cell=None;self.depth=0
    def handle_starttag(self,tag,attrs):
        if tag=='table':
            self.depth+=1
            if self.depth==1:self.table=[]
        if self.depth==1:
            if tag=='tr':self.row=[]
            if tag in ('td','th') and self.row is not None:self.cell=[]
    def handle_data(self,value):
        if self.cell is not None:self.cell.append(value)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None and self.row is not None:
            self.row.append(' '.join(''.join(self.cell).split()));self.cell=None
        if tag=='tr' and self.row is not None and self.table is not None:
            self.table.append(self.row);self.row=None
        if tag=='table':
            if self.depth==1 and self.table is not None:self.tables.append(self.table);self.table=None
            self.depth=max(0,self.depth-1)

def extract(html,municipalities):
    parser=Tables();parser.feed(html)
    matching=[table for table in parser.tables if any('当選者' in ''.join(row) and '市町村名' in ''.join(row) for row in table[:3])]
    if len(matching)!=1:raise ValueError('Municipal mayor result table not identified uniquely')
    table=matching[0]
    output=[]
    for row in table[1:]:
        if len(row)<7:continue
        name=row[0].replace(' ','');winner=row[5].replace(' ','')
        if name not in municipalities or not winner:continue
        m=re.match(r'(\d{1,2})月(\d{1,2})日',row[3])
        if not m:continue
        day=dt.date(2026,int(m.group(1)),int(m.group(2))).isoformat()
        output.append({'electionId':f'{municipalities[name]}-mayor-{day}',
          'municipalityCode':municipalities[name],'electionDate':day,
          'office':'mayor','candidateName':winner,'result':'elected',
          'sourceURL':URL,'publishedAt':'2026-10-16',
          'uncontested':'無投票' in row[4],'electionType':'mayor'})
    if not 3<=len(output)<=50:raise ValueError('Unexpected number of confirmed winner rows')
    if len({r['electionId'] for r in output})!=len(output):raise ValueError('Duplicated election')
    return output

def main():
    municipalities={m['name']:m['code'] for m in json.loads((ROOT/'data/national.json').read_text())['municipalities'] if m['pref']=='新潟県'}
    previous=json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {'results':[]}
    try:
        req=urllib.request.Request(URL,headers={'User-Agent':'Localpoliticians/1.0 election commission monitor'})
        with urllib.request.urlopen(req,timeout=25) as resp:
            if urlparse(resp.geturl()).hostname!='www.pref.niigata.lg.jp':raise ValueError('Untrusted redirect')
            data=resp.read(1500001)
            charset=resp.headers.get_content_charset() or 'utf-8'
        if len(data)>1500000:raise ValueError('Oversized official HTML')
        incoming=extract(data.decode(charset,errors='replace'),municipalities)
        old={(r['electionId'],r['candidateName']):r for r in previous.get('results',[])}
        for r in incoming:
            key=(r['electionId'],r['candidateName'])
            if key not in old:old[key]=r
        combined=sorted(old.values(),key=lambda x:(x['electionDate'],x['municipalityCode'],x['candidateName']))
        previous['results']=combined
        previous['updatedAt']=dt.datetime.now(dt.timezone.utc).isoformat()
        OUTPUT.write_text(json.dumps(previous,ensure_ascii=False,indent=2)+'\n')
        report={'updatedAt':previous['updatedAt'],'ok':True,'importedFromSource':len(incoming),'totalResults':len(combined)}
        print('Official Niigata municipality winners:',len(incoming),'total',len(combined))
    except Exception as ex:
        report={'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'ok':False,'error':str(ex)[:200]}
        print('Niigata result import failed, preserved previous verified records:',report['error'])
    STATUS.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
