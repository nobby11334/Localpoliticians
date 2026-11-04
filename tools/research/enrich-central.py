#!/usr/bin/env python3
"""Optional second step: enrich official rosters using their own linked official profile pages.
Run after collect-council-central.py. Pass --cached-only to use downloaded profile snapshots.
No personal contact, exact birth dates or street addresses are exported.
"""
import sys,json,concurrent.futures,re,hashlib
from pathlib import Path
from importlib.machinery import SourceFileLoader
M=SourceFileLoader('collectcentral',str(Path(__file__).parent/'collect-council-central.py')).load_module()
B=Path(__file__).parent;D=json.loads((B/'council-central.json').read_text());M.people=D['people']
urls=sorted(set(p['officialProfileURL'].split('#')[0]for p in D['people']if p.get('officialProfileURL')))
def get(u):
 try:
  key='profile-'+hashlib.sha256(u.encode()).hexdigest()[:12]
  if '--cached-only'in sys.argv and not (B/(key+'.html')).exists():return u,None
  t=M.load(key,u);return u,t
 except Exception:return u,None
with concurrent.futures.ThreadPoolExecutor(max_workers=10)as ex:data=dict(ex.map(get,urls))
byname={(p['municipalityCode'],p['name']):p for p in D['people']}
def add(p,title,summary,u,category='activity'):
 if not summary:return
 if any(f['title']==title and f['summary']==summary for f in p['findings']):return
 p['findings'].append({'category':category,'title':title,'summary':summary,'period':'資料掲載時点（就任・退任時期不明）','url':u,'sourceType':'行政・議会','asOf':p['asOf']})
for u,t in data.items():
 if t is None:continue
 for tb in t.xpath('//table'):
  fields={M.text(M.cells(r)[0]):M.cells(r)[1]for r in tb.xpath('.//tr')if len(M.cells(r))==2}
  nk=next((k for k in fields if k.startswith('氏名')),None)
  if not nk:continue
  n=M.name(M.text(fields[nk]));ps=[p for p in D['people']if p.get('officialProfileURL','').split('#')[0]==u and p['name']==n]
  if len(ps)!=1:continue
  p=ps[0]
  for k,e in fields.items():
   if k=='所属委員会':add(p,k,M.text(e),u)
   if k in ['略歴','経歴','職歴','主な経歴']:add(p,k,M.text(e),u,'career')
   if k in ['ホームページ','個人ホームページ','ホームページURL']:
    aa=e.xpath('.//a[starts-with(@href,"http")]')
    if aa:p['website']=aa[0].get('href')
 if 'city.kobe.lg.jp'in u:
  for ul in t.xpath('//ul[contains(@class,"noicon")]'):
   lis=ul.xpath('./li')
   if not lis or not M.text(lis[0]).startswith('(1)'):continue
   n=M.name(re.sub(r'^\(1\)','',M.text(lis[0])));p=byname.get(('28100',n))
   if not p:continue
   for li in lis:
    s=M.text(li)
    if s.startswith('(2)'):p['group']=s[3:].strip()
    if s.startswith('(3)'):add(p,'議員期数',s[3:].strip(),u)
    if s.startswith('(4)'):add(p,'所属委員会',s[3:].strip(),u)
    if s.startswith('(8)'):
     aa=li.xpath('.//a[starts-with(@href,"http")]')
     if aa:p['website']=aa[0].get('href')
 # Any exact official member heading can safely delimit its following sibling blocks.
 for h in t.xpath('//h2|//h3|//h4'):
  n=M.name(M.text(h));ps=[p for p in D['people']if p.get('officialProfileURL','').split('#')[0]==u and p['name']==n]
  if len(ps)!=1:continue
  p=ps[0]
  for e in h.itersiblings():
   if e.tag in ['h2','h3','h4']:break
   s=M.text(e)
   if any(k in s for k in ['ホームページ','ウェブサイト']):
    aa=e.xpath('.//a[starts-with(@href,"http")]');aa=[a for a in aa if not any(z in a.get('href')for z in ['city.','twitter.com/intent','facebook.com/sharer'])]
    if aa:p['website']=aa[0].get('href')
   if e.tag=='dl':
    for dt in e.xpath('./dt'):
     if M.text(dt) in ['略歴','経歴','職歴','主な経歴']:
      dd=dt.getnext()
      if dd is not None:add(p,M.text(dt),M.text(dd),u,'career')
D['meta']['officialProfilePagesFetched']=sum(t is not None for t in data.values());D['meta']['websiteCount']=sum(bool(p.get('website'))for p in D['people']);D['meta']['findingCount']=sum(len(p['findings'])for p in D['people'])
(B/'council-central.json').write_text(json.dumps(D,ensure_ascii=False,indent=2));print(json.dumps(D['meta'],ensure_ascii=False))
