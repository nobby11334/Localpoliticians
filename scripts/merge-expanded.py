"""Normalize reviewed source imports into small municipality files and a coverage index."""
import json,re,hashlib,collections,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
load=lambda p:json.loads(p.read_text())
registry={m['code']:m for m in load(ROOT/'data/national.json')['municipalities']}
regions=collections.defaultdict(dict);rejected=[]
def norm(s):return re.sub(r'[\s　]','',unicodedata.normalize('NFKC',s or '')).translate(str.maketrans({'﨑':'崎','髙':'高','塚':'塚'}))
def url(s):return isinstance(s,str) and s.startswith(('https://','http://'))
def merge(p,origin):
 code=str(p.get('municipalityCode','')).zfill(5)
 if code not in registry or not p.get('name'):rejected.append([origin,code,p.get('name')]);return
 if code=='13105' and origin!='bunkyo':return
 p=dict(p)
 if origin=='party-members.json' and '掲載日時不明' in p.get('researchNotes',''):
  p['collectedAt']=p.get('asOf','2026-11-04');p['asOf']='掲載日時不明（'+p['collectedAt']+'取得）'
  p['findings']=[{**f,'asOf':p['asOf']} for f in p.get('findings',[])]
 if p.get('candidate') and not p.get('sourceURL'):
  src=p['candidate'].get('sources',[{}])[0];p['sourceURL']=src.get('url');p['sourceTitle']=src.get('title','次回選挙の発表');p['asOf']=src.get('date') or '掲載日時不明';p['rosterKind']='予定者の発表資料'
  if '確認' in p['asOf']:p['asOf']='掲載日時不明（'+p['asOf']+'）'
 if origin=='mayor-careers.json' and not p.get('sourceUpdatedAt'):
  p['asOf']='掲載日時不明（'+p.get('retrievedAt','2026-11-04')+'確認）'
  p['findings']=[{**f,'asOf':p['asOf']} for f in p.get('findings',[])]
 if p.get('retrievedAt') and not p.get('collectedAt'):p['collectedAt']=p['retrievedAt']
 if p.get('asOfBasis') and ('取得日' in p['asOfBasis'] or p['asOfBasis']=='retrievedAt'):
  observed=p.get('asOf','2026-11-04');p['asOf']='掲載日時不明（'+str(observed)+'取得）'
  p['findings']=[{**f,'asOf':p['asOf']} if f.get('asOfBasis')=='retrievedAt' or f.get('asOf')==observed else f for f in p.get('findings',[])]
 if not p.get('rosterKind'):
  p['rosterKind']='行政・議会の名簿' if origin.startswith('council-') else '政党公式の所属議員掲載' if origin in ['party-members.json','komei-members.json'] else '行政の首長紹介' if origin=='mayor-careers.json' else '掲載資料'
 if not p.get('website') and p.get('profileURL'):p['website']={'url':p['profileURL'],'kind':'行政・議会のプロフィール' if origin.startswith('council-') else '政党公式プロフィール'}
 name=norm(p['name']);key=code+'-'+hashlib.sha256(name.encode()).hexdigest()[:12]
 old=regions[code].get(key,{'id':key,'name':p['name'],'municipalityCode':code,'findings':[],'sources':[],'sourceNames':[]})
 if p['name'] not in old['sourceNames']:old['sourceNames'].append(p['name'])
 for k in ['office','party','group','website','asOf','sourceURL','sourceTitle','candidate','currentLabel','isIncumbent','researchNotes','rosterKind','collectedAt','asOfBasis','currentStatus']:
  if p.get(k) is not None:
   if k=='website' and old.get('website') and ('本人' in str(old['website'].get('kind','')) or old['website'].get('kind')=='personal') and '本人' not in str(p[k]) and 'personal' not in str(p[k]):continue
   old[k]=p[k]
 if isinstance(old.get('website'),str):old['website']={'url':old['website'],'kind':'掲載プロフィール'}
 if old.get('website'):
  old['website']['kind']={'personal':'本人ホームページ','party':'政党公式の紹介','official':'行政・議会の紹介'}.get(old['website'].get('kind'),old['website'].get('kind','掲載プロフィール'))
 for f in p.get('findings',[]):
  if not url(f.get('url')) or not f.get('title'):continue
  if f.get('asOfBasis')=='retrievedAt' and '不明' not in str(f.get('asOf','')):f={**f,'asOf':'掲載日時不明（'+str(f.get('asOf','2026-11-04'))+'取得）'}
  f={k:v for k,v in f.items() if k in ['category','title','summary','period','url','sourceType','asOf','organization','source','additionalSources']}
  if not any(x['title']==f['title'] and x['url']==f['url'] for x in old['findings']):old['findings'].append(f)
 if url(p.get('sourceURL')):
  s={'url':p['sourceURL'],'title':p.get('sourceTitle','掲載名簿'),'asOf':p.get('asOf','掲載日時不明'),'kind':p.get('rosterKind','出典参照')}
  if s not in old['sources']:old['sources'].append(s)
 old['role']='mayor' if re.search(r'市長|区長|町長|村長|首長',old.get('office','')) and '議' not in old.get('office','') else 'council'
 if old.get('candidate') and not any('名簿' in s.get('kind','') and '予定' not in s.get('kind','') for s in old['sources']) and origin!='bunkyo':old['role']='candidate'
 if old.get('isIncumbent') is False:old['role']='candidate'
 regions[code][key]=old
for path in sorted((ROOT/'data/imports').glob('*.json')):
 d=load(path);ps=d if isinstance(d,list) else d.get('people',d.get('persons',d.get('candidates',[])))
 for p in ps:merge(p,path.name)
b=load(ROOT/'data/bunkyo.json');roster=next(s for s in b['sources'] if s['id']=='roster')
for p in b['people']:
 merge({**p,'municipalityCode':'13105','asOf':p.get('asof') or b['verified'],'sourceURL':roster['url'],'sourceTitle':'文京区・出典付き詳細調査','rosterKind':'行政・議会等の調査','collectedAt':b['verified']},'bunkyo')
coverage={};totals=collections.Counter();all_sources={}
for code,byid in sorted(regions.items()):
 people=sorted(byid.values(),key=lambda p:p['name']);counts={'people':len(people),'council':sum(p['role']=='council' for p in people),'mayorProfiles':sum(p['role']=='mayor' for p in people),'candidates':sum(bool(p.get('candidate')) for p in people),'findings':sum(len(p['findings']) for p in people),'careerProfiles':sum(any(f['category']=='career' for f in p['findings']) for p in people)}
 totals.update(counts);coverage[code]={**counts,'names':' '.join(' '.join(p.get('sourceNames',[p['name']])) for p in people),'sources':len({s['url'] for p in people for s in p['sources']})}
 (ROOT/f'data/regions/{code}.json').write_text(json.dumps({'municipalityCode':code,'people':people,'counts':counts},ensure_ascii=False,separators=(',',':'))+'\n')
 for p in people:
  for s in p['sources']:
   if url(s['url']):all_sources[s['url']]={'id':'expanded-'+hashlib.sha256(s['url'].encode()).hexdigest()[:16],'name':registry[code]['name']+' '+s['title'],'url':s['url'],'scope':s['kind'],'asof':s['asOf'],'expected':[norm(p['name'])] if p['role']=='mayor' else ['公認','推薦','候補'] if '予定者' in s['kind'] else ['議員','議会']}
meta={'collectedAt':'2026-11-04','municipalities':len(coverage),'prefectures':len({registry[c]['pref'] for c in coverage}),'totals':dict(totals),'notes':'収録は一部。政党名簿は当該政党の掲載者に限る。現職・所属は資料掲載時点、出馬は発表の根拠別に表示。'}
(ROOT/'data/coverage.json').write_text(json.dumps({'meta':meta,'municipalities':coverage},ensure_ascii=False,separators=(',',':'))+'\n')
(ROOT/'data/expanded-sources.json').write_text(json.dumps(list(all_sources.values()),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(meta,ensure_ascii=False));print('Rejected unmatched records:',len(rejected))
if rejected:(ROOT/'data/import-rejections.json').write_text(json.dumps(rejected,ensure_ascii=False,indent=2))
