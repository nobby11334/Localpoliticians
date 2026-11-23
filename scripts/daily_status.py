"""Produce an honest daily ingestion/coverage status for the public site.

This report is generated AFTER the source sync and candidate audit. It distinguishes
verified politician/filing data from unverified news and source failures.
"""
import datetime as dt
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
OUTPUT=DATA/'daily-update-status.json'

def read(name, default):
    path=DATA/name
    try:return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:return default

def source_health():
    groups={
      'candidateStructured':read('candidate-sync-status.json',{}).get('sources',[]),
      'officialRosters':read('official-rosters-status.json',{}).get('sources',[]),
      'officialHtmlResults':read('official-html-results-status.json',{}).get('sources',[]),
      'officialMunicipalVotes':[read('official-vote-status.json',{})],
      'prefectureResults':[read('prefecture-results-status.json',{})],
      'electionStructured':read('election-results.json',{}).get('sources',[]),
    }
    result={}
    for name,sources in groups.items():
        active=[s for s in sources if s and ('ok' in s or 'error' in s)]
        result[name]={'checked':len(active),'success':sum(s.get('ok') is True for s in active),
                      'failed':sum(s.get('ok') is False or bool(s.get('error')) for s in active),
                      'errors':[{'id':s.get('id',name),'error':str(s.get('error',''))[:160]}
                                for s in active if s.get('ok') is False or s.get('error')][:20]}
    return result

def make_report():
    current=read('candidate-audit.json',{})
    audit=current.get('totals',{})
    regions=current.get('municipalities',[])
    results=read('election-results.json',{}).get('results',[])
    candidate_sync=read('candidate-sync-status.json',{})
    health=source_health()
    previous=read('daily-update-status.json',{})
    previous_totals=previous.get('totals',{})
    totals={
      'municipalities':len(regions),
      'mayorCandidateRecords':audit.get('mayorCandidateRecords',0),
      'councilCandidateRecords':audit.get('councilCandidateRecords',0),
      'mayorCandidateMunicipalities':audit.get('mayorCandidateMunicipalities',0),
      'councilCandidateMunicipalities':audit.get('councilCandidateMunicipalities',0),
      'confirmedResults':len(results),
      'confirmedWinners':sum(r.get('result')=='elected' for r in results),
      'unverifiedNewsLeads':audit.get('newsLeadsForReview',0),
      'newUnverifiedLeads':audit.get('newLeads',0),
      'checkedMunicipalities':audit.get('checkedMunicipalities',0),
      'failedLastBatch':audit.get('failedLastBatch',0),
      'retriedFailedMunicipalities':audit.get('retriedFailedMunicipalities',0),
      'officialSourceChecks':sum(x['checked'] for x in health.values()),
      'officialSourceFailures':sum(x['failed'] for x in health.values()),
      'configuredStructuredCandidateSources':candidate_sync.get('configuredSources',0),
    }
    changes={k:(v-previous_totals[k] if isinstance(v,int) and isinstance(previous_totals.get(k),int) else None)
             for k,v in totals.items()}
    report={
      'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
      'asOfDateJST':dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat(),
      'status':'degraded' if totals['officialSourceFailures'] or totals['failedLastBatch'] else 'ok',
      'notice':'一次資料確認済み候補者と当落、未検証のニュース記事を明確に区別。全国完全網羅を保証しない。',
      'totals':totals,'changesSincePreviousRun':changes,'sources':health,
      'newLeads':current.get('recentNewLeads',[])[:30]
    }
    OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('DAILY STATUS',json.dumps({'status':report['status'],'totals':totals},ensure_ascii=False))
    return report

if __name__=='__main__':make_report()
