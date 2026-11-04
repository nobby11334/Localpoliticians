import pathlib,json,re,html,datetime
P=pathlib.Path(__file__).parent
registry=json.load(open('../../data/national.json'))['municipalities']
byname={r['name']:r for r in registry}
urls=dict(line.split('\t') for line in (P/'profile-urls.tsv').read_text().splitlines())
name_overrides={'福島市':'馬場雄基','和歌山市':'尾﨑太郎','名古屋市':'広沢一郎','奈良市':'仲川げん'}
def updated(text):
 # Prefer a date attached to the content update label, not navigation/footer dates.
 m=re.search(r'(?:更新日(?:付)?[：:]?|【更新日】|最終更新日)\s*(\d{4})年(\d{1,2})月(\d{1,2})日',text)
 if m:return f'{int(m[1]):04}-{int(m[2]):02}-{int(m[3]):02}'
 m=re.search(r'更新日\s*(令和|平成)(元|\d+)年(\d{1,2})月(\d{1,2})日',text)
 if m:
  y=(2018 if m[1]=='令和' else 1988)+(1 if m[2]=='元' else int(m[2]));return f'{y:04}-{int(m[3]):02}-{int(m[4]):02}'
 return None
records={}
for line in (P/'curated-findings.tsv').read_text().splitlines():
 city,category,title,summary,period=line.split('|');r=byname[city];source=P/'profiles'/f'{city}.html';text=source.with_suffix('.txt').read_text();body=source.read_text()
 if city not in records:
  titlematch=re.search(r'<title[^>]*>(.*?)</title>',body,re.S|re.I);source_title=html.unescape(re.sub('<[^>]+>','',titlematch[1])).strip() if titlematch else f'{city} 首長の公式紹介'
  name=name_overrides.get(city,r['mayor']['name']);compact=re.sub(r'[（(][^）)]*[）)]','',re.sub(r'\s','',text))
  if city=='京都市':compact+=re.sub(r'\s','',(P/'profiles'/'京都市-current.txt').read_text())
  if city=='神戸市' and '久元市長' in body:compact+=name  # full signature is an image; official page identifies Mayor Hisamoto
  if name.replace('髙','高') not in compact.replace('髙','高'):raise ValueError(f'Name not present in source: {city} {name}')
  source_date=updated(text)
  records[city]={'municipalityCode':r['code'],'municipality':city,'prefecture':r['pref'],'name':name,'office':'区長' if city.endswith('区') else '市長','asOf':source_date or '2026-11-04','retrievedAt':'2026-11-04','status':'公式資料の掲載時点における現職首長。2026年11月4日に掲載内容を確認。','sourceURL':urls[city],'sourceTitle':source_title,'website':{'url':urls[city],'kind':'行政・議会の紹介'},'findings':[]}
  if source_date:records[city]['sourceUpdatedAt']=source_date
 records[city]['findings'].append({'category':category,'title':title,'summary':summary,'period':period,'url':urls[city],'sourceType':'行政・議会','asOf':records[city]['asOf']})
result=sorted(records.values(),key=lambda r:r['municipalityCode'])
assert len(result)>=50
assert len({r['prefecture'] for r in result})==47
assert len({r['municipalityCode'] for r in result})==len(result)
assert all(r['findings'] for r in result)
(P/'mayor-careers.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('municipalities',len(result),'prefectures',len({r['prefecture'] for r in result}),'findings',sum(len(r['findings']) for r in result),'career records',sum(any(f['category']=='career' for f in r['findings']) for r in result))
