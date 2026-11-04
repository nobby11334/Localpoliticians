from pathlib import Path
import os
import json,re
from lxml import html
p=os.environ['CANDIDATE_OUTPUT'];data=json.load(open(p));registry=json.load(open(os.environ['MUNICIPALITY_REGISTRY']))['municipalities']
r=html.parse(str(Path(os.environ['CANDIDATE_WORKDIR']) / 'ishin2027.html'));added=[];skipped=[];target=''
for el in r.xpath('//section[@id="left"]/*'):
 if el.tag=='h4':
  full=' '.join(el.text_content().split());m=re.search(r'([^\s】]+[市区町村県府])議会議員(補欠)?選挙',full);target=m.group(0) if m else ''; locality=m.group(1) if m else '';continue
 if el.tag!='section': continue
 for dt in el.xpath('.//dt[span]'):
  name=''.join(dt.xpath('text()')).strip().replace('　','')
  div=dt.getparent().getparent();profile=div.xpath('./a/@href');district=''.join(div.xpath('.//li/text()')).strip()
  if not target or locality.endswith(('県','府')):skipped.append((name,target));continue
  matches=[m for m in registry if m['name']==locality]
  if len(matches)>1:matches=[m for m in matches if m['pref']=='東京都']
  if len(matches)!=1:skipped.append((name,locality));continue
  code=matches[0]['code'];cls=div.get('class','');current='activedutyicon' in cls;new='newicon' in cls
  office=target.split('選挙')[0].replace('補欠','') if current else '新人（現在の公職未確認）' if new else '元職等（現在の公職未確認）'
  # office title should exclude municipality name
  if current:office='区議会議員' if locality.endswith('区') else '町議会議員' if locality.endswith('町') else '市議会議員'
  u='https://o-ishin.jp/election/candidate/2027kounin/'
  rec={'municipalityCode':code,'municipalityName':locality,'name':name,'office':office,'party':'日本維新の会','candidate':{'target':target+'（2027年予定）','status':'公認発表','announcedAt':'不明','sources':[{'url':u,'title':'2027年実施予定 地方議会議員選挙 公認候補予定者','date':(os.environ['CANDIDATE_AS_OF']+'確認')}],'note':'党公式2027年名簿で確認。公認決定日そのものは未確認。正式な立候補届出前。選挙区表示：'+district+'。日付の具体的記載は選管による再確認前。'},'findings':[],'website':{'url':profile[0] if profile else u,'title':'日本維新の会公式プロフィール' if profile else '日本維新の会公認候補予定者','kind':'party'}}
  added.append(rec)
data.extend(added);open(p,'w').write(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print('added',len(added),'total',len(data),'skipped',len(skipped),'municipalities',len(set(x['municipalityCode'] for x in data)))
print('pref',sorted(set(m['pref'] for m in registry if m['code'] in {x['municipalityCode'] for x in data})))
