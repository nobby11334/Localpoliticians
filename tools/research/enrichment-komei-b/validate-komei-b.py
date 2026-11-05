import os,pathlib,json,re,collections,sys,unicodedata,urllib.parse
B=pathlib.Path(os.environ.get('KOMEI_B_WORKDIR',os.getcwd())).expanduser().resolve()
INPUT=pathlib.Path(os.environ.get('KOMEI_B_INPUT',str(B/'komei-b.json'))).expanduser()
OUTPUT=pathlib.Path(os.environ.get('KOMEI_B_OUTPUT',str(B/'enriched-komei-b.json'))).expanduser()
STATS=pathlib.Path(os.environ.get('KOMEI_B_STATS',str(OUTPUT.with_name(OUTPUT.stem+'-stats.json')))).expanduser()
source=json.loads(INPUT.read_text());data=json.loads(OUTPUT.read_text());idx={x['id']:x for x in source}
DATE=os.environ.get('KOMEI_B_CHECKED_AT',data[0]['enrichment']['checkedAt'] if data else '')
if '--partial' not in sys.argv:assert len(data)==len(source)
assert len({x['id']for x in data})==len(data)
def norm(t):return re.sub(r'[\s・･\u200b\u241e]+','',unicodedata.normalize('NFKC',str(t))).replace('髙','高').replace('﨑','崎')
def canon(u):
 q=urllib.parse.urlsplit(str(u));host=q.netloc.lower().removeprefix('www.');scheme='https' if host=='komei.or.jp' else q.scheme.lower()
 return urllib.parse.urlunsplit((scheme,host,q.path.rstrip('/'),q.query,''))
new=0;year_kept=0;alias_proofs=0;types=collections.Counter();categories=collections.Counter();errors=[]
for p in data:
 original=idx[p['id']];assert p['name']==original['name'] and p['municipalityCode']==original['municipalityCode']
 assert p['enrichment']['checkedAt']==DATE
 assert p['enrichment']['status']in ['情報追加','既存内容確認','追加根拠未確認','取得失敗']
 for f in p['findings']:
  if not f.get('evidence'):
   errors.append((p['id'],'既存findingが残っている'));continue
  assert f['checkedAt']==DATE
  assert all(f.get(k) for k in ['category','title','summary','period','url','sourceType','asOf'])
  assert all(f['evidence'].get(k) for k in ['matchedName','sectionHeading','rule'])
  if norm(f['evidence']['matchedName'])!=norm(original['name']):
   w=original.get('website',{});urls=[w.get('url','') if isinstance(w,dict) else w,original.get('profileURL',''),original.get('sourceURL','')]+[r.get('url','')for r in original.get('findings',[])]+[r.get('url','')for r in original.get('sources',[])]
   approved={canon(u)for u in urls if '/member/detail/'in u}
   assert canon(f['evidence'].get('identitySourceURL',''))in approved,(p['id'],'別表記の党公式プロフィールURLが元入力と対応しない')
   alias_proofs+=1
  assert f['url'].startswith(('http://','https://'))
  assert f['sourceType']in ['本人発信','政党公式','行政・議会','団体公式']
  assert not re.search(r'〒|mailto:|[\w.+-]+@[\w.-]+\.[a-z]{2,}|生年月日|家族構成|電話番号|誕生日',f['summary'],re.I)
  assert '名簿に掲載' not in f['summary']
  if re.search(r'(?:昭和|平成|令和|19[0-9]{2}|20[0-9]{2})',f['period']):year_kept+=1
  new+=1;types[f['sourceType']]+=1;categories[f['category']]+=1
if '--partial' not in sys.argv:assert not errors,errors[:5]
stats={'people':len(data),'expected':len(source),'statuses':dict(collections.Counter(p['enrichment']['status']for p in data)),'newFindings':new,'withExplicitPeriod':year_kept,'sourceTypes':dict(types),'categories':dict(categories),'peopleWithNewFindings':sum(bool(p['findings'])for p in data),'existingRecordsToRemove':len(errors),'alternateNameFactsWithInputLinkedProof':alias_proofs}
STATS.parent.mkdir(parents=True,exist_ok=True);STATS.write_text(json.dumps(stats,ensure_ascii=False,indent=2));print(json.dumps(stats,ensure_ascii=False,indent=2))
