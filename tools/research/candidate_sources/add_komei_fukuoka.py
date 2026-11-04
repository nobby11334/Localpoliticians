from pathlib import Path
import os
import json,re
from lxml import html
p=os.environ['CANDIDATE_OUTPUT'];d=json.load(open(p));reg=json.load(open(os.environ['MUNICIPALITY_REGISTRY']))['municipalities'];mun={m['name']:m for m in reg if m['pref']=='福岡県'};r=html.parse(str(Path(os.environ['CANDIDATE_WORKDIR']) / 'komei2027.html'));body=r.xpath('//div[contains(@class,"article__body")]')[0];add=[];city=None;u='https://komei-fukuoka.jp/news/xz4n74n_u/'
for el in body:
 if el.tag=='h2':
  m=re.search(r'■(.+?[市町村])議会',el.text_content());city=m[1] if m else None;continue
 if not city or city not in mun:continue
 for br in el.xpath('.//br'):br.tail='\n'+(br.tail or '')
 for line in el.text_content().splitlines():
  m=re.match(r'\s*([^\d【]+?)\s+(\d+)\s+([現新元前])\s*$',line)
  if not m:continue
  name=re.sub(r'\s','',m[1]);typ='町議会議員' if city.endswith('町') else '市議会議員'
  add.append(dict(municipalityCode=mun[city]['code'],municipalityName=city,name=name,office=typ if m[3]=='現' else '新人（現在の公職未確認）',party='公明党',candidate=dict(target=city+'議会議員選挙（2027年予定）',status='公認発表',announcedAt='不明',sources=[dict(url=u,title='2027年統一地方選挙公認状況（2026年9月24日現在）',date='2026-09-24')],note='公明党福岡県本部公式の2027年公認状況で確認。個別の公認決定日そのものは未確認。正式な立候補届出前。'),findings=[],website=dict(url=u,title='公明党福岡県本部 公認状況',kind='party')))
d.extend(add);open(p,'w').write(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print('Komei added',len(add),'total',len(d))
