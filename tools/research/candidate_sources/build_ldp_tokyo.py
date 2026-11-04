import os
import json,re,collections,pdfplumber,unicodedata
from pathlib import Path
out=Path(os.environ['CANDIDATE_OUTPUT'])
registry=json.load(open(os.environ['MUNICIPALITY_REGISTRY']))['municipalities']
mun={x['name']:x for x in registry if x['pref']=='東京都'}
u='https://election-special.tokyo-jimin.jp/wp-content/uploads/2026/10/%E8%B3%87%E6%96%99%EF%BC%9AR9%E7%B5%B1%E4%B8%80%E5%9C%B0%E6%96%B9%E9%81%B8_%E7%AC%AC1%E6%AC%A1%E5%85%AC%E8%AA%8D%E6%8E%A8%E8%96%A6%E6%B1%BA%E5%AE%9A%E8%80%85%E4%B8%80%E8%A6%A720261013.pdf'
res=[];unknown=[];current=None
with pdfplumber.open(str(Path(os.environ['CANDIDATE_WORKDIR']) / 'ldp2027.pdf')) as pdf:
 for pi,page in enumerate(pdf.pages):
  words=page.extract_words(x_tolerance=2,y_tolerance=3)
  headers=[w for w in words if w['text'] in mun and w['x0']<100]
  for w in words:
   if w['text'] not in ['公認','推薦'] or w['x0']>80: continue
   hs=[h for h in headers if h['top']<w['top']]
   if hs: current=sorted(hs,key=lambda x:x['top'])[-1]['text']
   if not current: unknown.append((pi,w));continue
   row=[z for z in words if abs(z['top']-w['top'])<2]
   name=''.join(z['text'] for z in row if 80<z['x0']<185)
   kana=''.join(z['text'] for z in row if 185<=z['x0']<300)
   name=name or kana
   state=''.join(z['text'] for z in row if 300<=z['x0']<330)
   terms=''.join(z['text'] for z in row if 330<=z['x0']<350)
   job=''.join(z['text'] for z in row if 380<=z['x0']<485)
   if state not in ['現','前','元','新']: unknown.append((pi,name,state));continue
   note='令和9年（2027年）統一地方選挙・近接選挙の候補予定者。正式な立候補届出前。'
   if not ''.join(z['text'] for z in row if 80<z['x0']<185): note+=' PDF氏名欄の文字が抽出できないため、同資料の読み仮名で表示。'
   typ='区議会議員' if current.endswith('区') else '町議会議員' if current.endswith('町') else '市議会議員'
   office=typ if state=='現' else '前職（現在の公職未確認）' if state=='前' else '元職（現在の公職未確認）' if state=='元' else '新人（現在の公職未確認）'
   source={'url':u,'title':'令和9年統一地方選挙 第1次公認・推薦候補予定者名簿（'+str(pi+1)+'ページ）','date':'2026-10-13'}
   findings=[]
   if job: findings.append({'category':'career','title':'公認・推薦名簿の職業欄','summary':job+'と記載。職歴の始期・終期および現在継続の確認は未了。','period':'2026年10月13日資料現在','url':u,'sourceType':'政党公式','asOf':'2026-10-13'})
   if state=='現' and terms: findings.append({'category':'career','title':typ+' '+terms+'期','summary':'党公式候補予定者名簿の現職・期別欄による。','period':'2026年10月13日資料現在','url':u,'sourceType':'政党公式','asOf':'2026-10-13'})
   res.append({'municipalityCode':mun[current]['code'],'municipalityName':current,'name':name,'office':office,'party':'自由民主党' if w['text']=='公認' else '党籍未確認（自民党推薦）','candidate':{'target':typ+'選挙（2027年予定）','status':'公認発表' if w['text']=='公認' else '推薦発表','announcedAt':'2026-10-13','sources':[source],'note':note},'findings':findings,'website':{'url':'https://election-special.tokyo-jimin.jp/20261013release/','title':'自民党東京都連 公認・推薦発表','kind':'party'}})
print('count',len(res),'unknown',unknown,'municipalities',len(set(x['municipalityCode'] for x in res)))
assert len(res)==276
out.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
