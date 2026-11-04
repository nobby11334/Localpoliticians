import pathlib,json,re,collections
P=pathlib.Path(__file__).parent
S=json.loads((P/'east-reviewed-biographies.json').read_text())
# Manual review: retain only factual biography entries; remove news, policy proposals,
# another person's roles, family/private context, duplicates and incomplete captions.
keep={0:[1,2,3],1:[1],2:[0],3:[2],4:[],5:[1,2,3,4,5,6,7],6:[0,2],7:[2],8:[1,4,5,8],9:[],10:[0,1,2,3],11:[0,1,2,4,5,6],12:[],13:[2],14:[2,7,8],15:[2],16:[0,2],17:[0,1],18:[0],19:[0,3],20:[0],21:[1,5],22:[0,1],23:[0,1,2,3,4,5],24:[1,2],25:[],26:[0,1,2],27:[3],28:[],29:[0],30:[3],31:[0],32:[0]}
manual={
3:['株式会社アサツーディ・ケイに勤務した経歴。','2014年7月にNPO法人マタニティハラスメント対策ネットワーク（マタハラNet）を設立し、元代表理事と記載。','2016年11月に株式会社natural rightsを設立し、代表に就任したと記載。'],
4:['神奈川大学法学部法律学科を卒業。','アシスト株式会社へ就職し、2002年12月に退社。','2009年9月に明治大学専門職大学院を修了。'],
9:['1988年に同志社大学商学部を卒業。','1988年にセコム株式会社へ入社。','1994年にソニー生命へ転職し、2006年に退社。','2021年12月から自民党横浜市支部連合会幹事長と記載。'],
12:['エイベックス株式会社で約8年間勤務した経歴。'],
15:['大学卒業後に鉄道会社へ入社し、車掌として勤務した経歴。'],
21:['社会福祉法人柏木福祉会評議員と記載。','若林区保護司会の保護司と記載。','南材小学校PTA監事と記載。','交通指導隊荒町地区分隊長、仙台市地域防災リーダー（南材地区）と記載。'],
25:['仙台市高砂小学校PTA会長と記載。','宮城野消防団高砂分団福田町部の団員と記載。','第49回仙台七夕花火祭特別委員会副委員長と記載。'],
26:['國學院大学文学部文学科を卒業。'],
30:['仙台市立郡山小学校PTA会長と記載。','郡山学区民体育振興会副会長と記載。','交通指導隊郡山分隊隊員、東郡山新々田町内会防災部長と記載。','立憲民主党宮城県連幹事長と記載。']}
def norm(s):return re.sub(r'\s+','',s).replace('﨑','崎').replace('髙','高')
D=json.loads((P/'council-east.json').read_text());idx={(x['municipalityCode'],norm(x['name'])):x for x in D['people']}
for p in D['people']:
 p['asOfBasis']='retrievedAt' if '不明' in p['asOf'] else 'sourceDate'
 for f in p['findings']:f.setdefault('asOfBasis','sourceDate')
linked=0
for c,n,u,src in json.loads((P/'east-personal-links.json').read_text()):
 p=idx.get((c,norm(n)))
 if p:
  p['website']=u;p['websiteSourceURL']=src;p['websiteAsOf']='2026-11-04';p['websiteAsOfBasis']='retrievedAt';linked+=1
base=json.loads((P/'east-enriched-base.json').read_text())
for p in base['people']:
 if p.get('officialProfileURL'):idx[(p['municipalityCode'],norm(p['name']))]['officialProfileURL']=p['officialProfileURL']
added=0;touched=set()
for i,page in enumerate(S):
 p=idx.get((page['code'],norm(page['name'])))
 if not p:continue
 lines=page['reviewedLines']
 for line in lines:
  category='career'
  if re.search(r'PTA|ＰＴＡ|町内会|町会|自治会|消防団|保護司|交通指導|地域防災|体育振興|七夕|民生',line,re.I):category='community'
  elif re.search(r'党.*幹事|党.*支部',line):category='party'
  elif re.search(r'理事|評議員',line):category='organization'
  title={'career':'職歴・学歴','community':'PTA・地域活動','organization':'外部団体の役職','party':'政党役職'}[category]+'：'+line[:55]
  f={'category':category,'title':title,'summary':line,'period':'プロフィール掲載（時期・現職／元職は本文の記載どおり。記載がない場合は不明）','url':page['url'],'sourceType':'本人発信','sourceTitle':'本人公式サイトのプロフィール・自己紹介','asOf':'2026-11-04','asOfBasis':'retrievedAt','officialLinkSourceURL':page['officialSource']}
  if any(x.get('summary')==line and x.get('url')==page['url'] for x in p['findings']):continue
  p['findings'].append(f);added+=1;touched.add(p['name'])
 p['profileResearch']={'checkedAt':'2026-11-04','asOfBasis':'retrievedAt','scope':'公式名簿からリンクされた本人サイトのプロフィールを確認。自己申告の経歴であり第三者による裏付け調査は未実施。記載されていない活動や就任期間は補完しない。'}
D['meta']['asOfBasisDefinitions']={'sourceDate':'出典の基準日または掲載更新日。閲覧時点の現職を保証しない。','retrievedAt':'資料日が不明のため取得日を示す。役職の現任確認日ではない。'}
D['meta']['biographyEnrichment']={'checkedAt':'2026-11-04','officiallyLinkedWebsites':linked,'peopleWithAddedBiographies':len(S),'addedFindings':sum(len(x['reviewedLines']) for x in S),'method':'行政公式名簿117ページから本人HPリンクを確認。本文取得済みプロフィールを人手確認し、ニュース・政策提案・別人の経歴・私的事項を除外。本人発信として記録。','limits':'本人HPの全ページ調査・経歴の第三者裏付け・現職役職の全件再確認は未実施。URLは公式名簿の掲載リンク。リンク先本文の未取得分もある。'}
(P/'council-east.json').write_text(json.dumps(D,ensure_ascii=False,indent=2));print(D['meta']['biographyEnrichment'])
assert not re.search(r'〒|mailto:|電話番号|[\w.+-]+@[\w.-]+\.[a-z]{2,}',json.dumps(D,ensure_ascii=False))
print('validated',len(D['people']),'people;',sum(len(p['findings'])for p in D['people']),'total findings')
