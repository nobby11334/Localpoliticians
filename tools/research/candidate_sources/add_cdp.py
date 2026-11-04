import os
import urllib.request,json,re,concurrent.futures,time
from lxml import html
from pathlib import Path
p=Path(os.environ['CANDIDATE_OUTPUT']);reg=json.load(open(os.environ['MUNICIPALITY_REGISTRY']))['municipalities'];r=html.parse(str(Path(os.environ['CANDIDATE_WORKDIR']) / 'cdp2027.html'));jobs=[]
for a in r.xpath('//a[contains(@href,"/election/")]'):
 u=a.get('href');name=a.text_content().strip()
 if not re.search(r'/election/\d+$',u):continue
 matches=[m for m in reg if m['name']==name]
 if len(matches)>1:
  tr=a.xpath('ancestor::tr');t=tr[0].text_content() if tr else ''
  matches=[m for m in matches if m['pref'] in t]
 if len(matches)==1:jobs.append((u,matches[0]))
jobs=list({u:(u,m) for u,m in jobs}.values());print('jobs',len(jobs),flush=True)
cache=Path(str(Path(os.environ['CANDIDATE_WORKDIR']) / 'cdp2027pages'));cache.mkdir(exist_ok=True)
def run(job):
 u,m=job
 try:
  f=cache/u.rsplit('/',1)[-1];b=f.read_bytes() if f.exists() else urllib.request.urlopen(u,timeout=18).read();f.write_bytes(b);doc=html.fromstring(b)
  # This link is sourced from the official 2027 list; exclude any resolved pages with incompatible year.
  title=' '.join(doc.xpath('//title/text()'));cards=doc.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," member ")]');ans=[]
  for c in cards:
   nn=c.xpath('.//h1[contains(@class,"member-name")]')
   if not nn:continue
   name=''.join(nn[0].xpath('text()')).strip();tag=c.xpath('.//span[@class="candidate-type"]/text()');tag=tag[0].strip() if tag else ''
   if tag not in ['公認','推薦']:continue
   kinds=c.xpath('.//p[contains(@class,"house-type")]/span/text()');state=kinds[1].strip() if len(kinds)>1 else '不明'
   typ='区議会議員' if m['name'].endswith('区') else '町議会議員' if m['name'].endswith('町') else '村議会議員' if m['name'].endswith('村') else '市議会議員'
   fs=[]
   for tr in c.xpath('.//table[contains(@class,"member-info")]//tr'):
    th=''.join(tr.xpath('./th//text()'));v=' '.join(' '.join(tr.xpath('./td//text()')).split())
    if th in ['経歴等','学歴'] and v:fs.append(dict(category='career',title=th,summary=v,period='資料記載／期間不明',url=u,sourceType='政党公式',asOf=(os.environ['CANDIDATE_AS_OF']+'確認')))
   ans.append(dict(municipalityCode=m['code'],municipalityName=m['name'],name=name,office=typ if state=='現職' else state+'（現在の公職未確認）',party='立憲民主党' if tag=='公認' else '党籍未確認（立憲民主党推薦）',candidate=dict(target=m['name']+'議会議員選挙（2027年予定）',status=tag+'発表',announcedAt='不明',sources=[dict(url=u,title=title,date=(os.environ['CANDIDATE_AS_OF']+'確認')),dict(url='https://cdp-japan.jp/election/unified_local_elections/2027/',title='2027年第21回統一自治体選挙情報（公認・推薦）',date=(os.environ['CANDIDATE_AS_OF']+'確認'))],note='党公式の2027年統一自治体選挙一覧からリンクされた選挙ページで公認・推薦を確認。決定日そのものは未確認。正式な立候補届出前。'),findings=fs,website=dict(url=u,title='立憲民主党公式 選挙情報',kind='party')))
  return ans,None
 except Exception as e:return [],str(e)+' '+u
added=[];errors=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
 for k,(ans,err) in enumerate(ex.map(run,jobs)):
  added.extend(ans)
  if err:errors.append(err)
  if k%20==0:print('progress',k,'people',len(added),flush=True)
if errors: raise RuntimeError('Official election pages could not be fetched: '+repr(errors))
data=json.loads(p.read_text());data.extend(added);p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print('DONE',len(added),'total',len(data),'errors',errors,flush=True)
