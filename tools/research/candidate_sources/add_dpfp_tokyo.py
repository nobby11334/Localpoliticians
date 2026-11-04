from pathlib import Path
import os
import json,re
from lxml import html
p=os.environ['CANDIDATE_OUTPUT'];d=json.load(open(p));reg=json.load(open(os.environ['MUNICIPALITY_REGISTRY']))['municipalities'];mun={m['name']:m for m in reg if m['pref']=='東京都'}
r=html.parse(str(Path(os.environ['CANDIDATE_WORKDIR']) / 'dpfp2027.html'));add=[];u='https://r9-toitsu.new-kokumin.tokyo/candidates.html'
for li in r.xpath('//li[@class="electoral__memberList__item"]'):
 name=''.join(li.xpath('.//h3[contains(@class,"name")]/text()')).strip().replace(' ','');target=''.join(li.xpath('.//p[contains(@class,"district")]/text()')).strip();m=re.match(r'(.+?[区市町村])議会',target)
 if not m or m[1] not in mun:continue
 state=''.join(li.xpath('.//p[@class="en"]/text()')).strip();typ='区議会議員' if m[1].endswith('区') else '町議会議員' if m[1].endswith('町') else '市議会議員';kind='推薦' if state.startswith('推薦') else '公認';web=li.xpath('.//a[contains(.,"公式HP")]/@href')
 add.append(dict(municipalityCode=mun[m[1]]['code'],municipalityName=m[1],name=name,office=typ if '現職' in state else '新人（現在の公職未確認）' if '新人' in state else '元職（現在の公職未確認）',party='国民民主党' if kind=='公認' else '党籍未確認（国民民主党推薦）',candidate=dict(target=target+'（2027年予定）',status=kind+'発表',announcedAt='不明',sources=[dict(url=u,title='2027年統一地方選挙 公認候補予定者一覧｜国民民主党東京都連',date=(os.environ['CANDIDATE_AS_OF']+'確認'))],note='2027年党公式名簿の表示：'+state+'。公認・推薦決定日そのものは未確認。正式届出前。'),findings=[],website=dict(url=web[0] if web else u,title='本人公式HP（政党公式からリンク）' if web else '国民民主党東京都連候補予定者一覧',kind='personal' if web else 'party')))
d.extend(add);open(p,'w').write(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print('DPFP added',len(add),'total',len(d))
