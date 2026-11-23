"""Nationwide candidate-coverage audit and rotating discovery of public news leads.
News headlines are NEVER promoted into candidacy facts: they are review leads only.
"""
import concurrent.futures, datetime as dt, hashlib, json, re, sys, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
TODAY=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
BATCH_COUNT=28
BATCH_NUMBER=TODAY.toordinal()%BATCH_COUNT
MAX_LEADS=2500
def read(path, default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:return default
def coverage():
    national=read(DATA/'national.json',{})['municipalities']
    rows=[]
    for m in national:
        code=str(m['code']);region=read(DATA/'regions'/f'{code}.json',{'people':[]})
        people=region.get('people',[])
        mayors=[p for p in people if p.get('candidate',{}).get('electionType')=='mayor']
        councils=[p for p in people if p.get('candidate',{}).get('electionType')=='council']
        rows.append({'code':code,'pref':m['pref'],'municipality':m['name'],'mayorCandidates':len(mayors),
          'councilCandidates':len(councils),'mayorCandidateNames':[p['name'] for p in mayors]})
    return rows
def fetch_news(m):
    # Search engine results are only tips for a human to validate against original sources.
    term=m['municipality']+' '+m['pref']+' (市長選 OR 区長選 OR 町長選 OR 村長選 OR 市議選 OR 区議選 OR 町議選 OR 村議選) (出馬 OR 立候補 OR 公認 OR 推薦)'
    q=urllib.parse.urlencode({'q':term,'hl':'ja','gl':'JP','ceid':'JP:ja'})
    url='https://news.google.com/rss/search?'+q
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Localpoliticians/1.0 (public election monitoring)'})
        with urllib.request.urlopen(req,timeout=12) as response:
            raw=response.read(400_001)
        if len(raw)>400_000:raise ValueError('Feed exceeds limit')
        root=ET.fromstring(raw)
        items=[]
        for item in root.findall('./channel/item')[:8]:
            title=(item.findtext('title') or '').strip()
            link=(item.findtext('link') or '').strip()
            if not title or not link.startswith('https://'):continue
            # Keep titles for review, not as confirmed candidacy.
            key=hashlib.sha256((m['code']+'|'+link).encode()).hexdigest()[:20]
            items.append({'id':key,'municipalityCode':m['code'],'pref':m['pref'],'municipality':m['municipality'],
             'title':title[:220],'url':link,'published':(item.findtext('pubDate') or '')[:80],'status':'要一次資料照合'})
        return m['code'],items,None
    except Exception as ex:return m['code'],[],str(ex)[:180]
def main():
    rows=coverage();report=read(DATA/'candidate-audit.json',{'leads':[],'checks':{}})
    old={r['id']:r for r in report.get('leads',[]) if 'id' in r}
    checks=report.get('checks',{})
    # All municipalities in 28 days; upcoming elections receive extra checks.
    calendar=read(DATA/'election-calendar.json',{}).get('municipalities',{})
    def days_to_election(m):
        item=calendar.get(m['code'],{})
        dates=[]
        for name in ('nextMayorElection','nextCouncilElection','mayorTermEnd','councilTermEnd'):
            d=item.get(name)
            if d:
                try:
                    days=(dt.date.fromisoformat(d)-TODAY).days
                    if 0<=days<=120:dates.append(days)
                except ValueError:pass
        return min(dates) if dates else None
    default=[m for m in rows if int(m['code'])%BATCH_COUNT==BATCH_NUMBER]
    urgent=[m for m in rows if days_to_election(m) is not None and days_to_election(m)<=14]
    soon=[m for m in rows if days_to_election(m) is not None and 14<days_to_election(m)<=120 and int(m['code'])%4==TODAY.toordinal()%4]
    batch=list({m['code']:m for m in default+urgent+soon}.values())
    priority_count=len({m['code'] for m in urgent+soon})
    if '--offline' in sys.argv:
        results=[]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results=list(executor.map(fetch_news,batch))
    checked_at=dt.datetime.now(dt.timezone.utc).isoformat()
    for code,leads,error in results:
        checks[code]={'checkedAt':checked_at,'error':error,'headlineCount':len(leads)}
        for lead in leads:
            if lead['id'] in old:
                lead['firstSeenAt']=old[lead['id']].get('firstSeenAt',checked_at)
            else:lead['firstSeenAt']=checked_at
            old[lead['id']]=lead
    all_leads=sorted(old.values(),key=lambda r:r['firstSeenAt'],reverse=True)[:MAX_LEADS]
    totals={'municipalities':len(rows),'mayorCandidateMunicipalities':sum(r['mayorCandidates']>0 for r in rows),
      'councilCandidateMunicipalities':sum(r['councilCandidates']>0 for r in rows),
      'withoutMayorCandidateRecords':sum(r['mayorCandidates']==0 for r in rows),
      'mayorCandidateRecords':sum(r['mayorCandidates'] for r in rows),
      'councilCandidateRecords':sum(r['councilCandidates'] for r in rows),
      'newsLeadsForReview':len(all_leads),'checkedMunicipalities':len(checks),
      'lastBatchMunicipalities':len(batch),'priorityMunicipalities':priority_count,'failedLastBatch':sum(bool(e) for _,_,e in results)}
    output={'updatedAt':checked_at,'method':'資料収録率の監査と検索ニュース見出しの要確認リード。候補者登録・一次資料確定ではない。',
      'totals':totals,'municipalities':rows,'leads':all_leads,'checks':checks}
    (DATA/'candidate-audit.json').write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps(totals,ensure_ascii=False))
if __name__=='__main__':main()
