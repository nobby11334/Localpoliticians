from importlib.machinery import SourceFileLoader
m=SourceFileLoader('east',str(__import__('pathlib').Path(__file__).parent/'fetch-east.py')).load_module()
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re,json,csv,io,collections
P=m.ROOT
extra=json.loads((P/'east-extra-sources.json').read_text());sources={**m.sources,**extra}
C={'yokohama':('14100','横浜市'),'kawasaki':('14130','川崎市'),'chiba':('12100','千葉市'),'sendai':('04100','仙台市'),'nerima':('13120','練馬区'),'ota':('13111','大田区'),'suginami':('13115','杉並区'),'minato':('13103','港区'),'edogawa':('13123','江戸川区'),'saitama':('11100','さいたま市'),'sapporo':('01100','札幌市')}
D={'yokohama':'2026-09-04','kawasaki':'2026-01-20','nerima':'2026-07-24','ota':'2026-09-01','suginami':'2026-10-19','minato':'2026-10-13','edogawa':'不明（2026-11-04取得）','sendai':'2026-09-01','saitama':'不明（2026-11-04取得）','sapporo':'2026-04-17'}
people=[]
def soup(k):return BeautifulSoup((P/(k+'.raw')).read_bytes(),'html.parser')
def clean(s):return re.sub(r'\s+',' ',s).strip()
def add(k,name,group=None,url=None,findings=None,website=None,date=None):
 base=k.split('-')[0];code,city=C[base];name=clean(name);date=date or D.get(base,'不明（2026-11-04取得）');u=url or sources[k]
 x={'municipalityCode':code,'municipality':city,'name':name,'office':('区議会議員' if city.endswith('区') else '市議会議員'),'asOf':date,'sourceURL':u,'sourceTitle':city+'議会 議員名簿','findings':findings or []}
 if group:x['group']=clean(group)
 if website:x['website']=website
 people.append(x);return x
# 横浜: all member links within article only; preserve headings as caucus, not party
s=soup('yokohama')
for a in s.select('a[href*="/shikai/giin/kubetsu/meibo"]'):
 if '#' not in a['href']:continue
 h=a.find_previous('h2');g=re.sub(r'（.*','',h.get_text(' ',strip=True)) if h else None
 add('yokohama',a.text,g)
# 川崎 official member profile links in paragraphs under party headings
s=soup('kawasaki')
for a in s.select('a[href*="/980/page/"]'):
 name=clean(a.text)
 if not name or len(name)>15:continue
 h=a.find_previous('h2');g=h.get_text(' ',strip=True) if h else ''
 if not any(t in g for t in ['議員団','会','無所属']):continue
 add('kawasaki',name,re.sub(r'（.*','',g))
# 千葉 six caucus pages, leaf's actual update date
for k in extra:
 if not k.startswith('chiba-'):continue
 s=soup(k);main=s.select_one('#tmp_contents');g=main.h1.text;dt=re.search(r'更新日：(\d+)年(\d+)月(\d+)日',s.text);date='-'.join([dt[1],dt[2].zfill(2),dt[3].zfill(2)]) if dt else None
 for a in main.select('a[href*="list_senkyoku"]'):add(k,a.text,g,date=date)
# 仙台 district listing supplied by parent dated roster
for k in extra:
 if not k.startswith('sendai-'):continue
 for a in soup(k).select('article .page_list a'):add(k,a.text,date=D['sendai'])
# 練馬 table: name and caucus only, skip addresses
for tr in soup('nerima').select('table tr'):
 cells=tr.find_all('td',recursive=False)
 if len(cells)>=9:add('nerima',cells[0].text,cells[2].text)
# 大田 blocks have personal HP and committee roles
for b in soup('ota').select('.gi-txt'):
 n=b.select_one('.gi-name')
 if not n:continue
 g=re.search(r'（(.+?)）',b.h2.text);g=g[1] if g else None
 web=next((a['href'] for a in b.select('a.externalLink') if a['href'].startswith('http')),None)
 f=[]
 lines=b.get_text('\n',strip=True).splitlines()
 for line in lines:
  if re.search(r'委員(?:長)?$',line):f.append({'category':'activity','title':line,'summary':'大田区議会公式名簿に記載された議会内役職。','period':'資料日現在','url':sources['ota'],'sourceType':'行政・議会','asOf':D['ota']})
 add('ota',n.text,g,findings=f,website=web)
# 杉並 caucus table; row lines explicitly separated by br
for tr in soup('suginami').select('table tr'):
 th=tr.find('th');td=tr.find('td')
 if not th or not td or '人数' not in th.text:continue
 g=re.split('（略称|人数',th.get_text(' ',strip=True))[0].strip()
 for line in td.get_text('\n',strip=True).splitlines():
  n=re.sub(r'（.*?）','',line).strip()
  if n:add('suginami',n,g)
# 港 table captions caucus
for t in soup('minato').select('table'):
 cap=t.find('caption')
 if not cap:continue
 g=re.sub(r'（.*','',cap.text)
 for a in t.select('td a'):
  for span in a.select('span'):span.decompose()
  add('minato',a.text,g)
# 江戸川 name only
for tr in soup('edogawa').select('table tr'):
 td=tr.find_all('td',recursive=False)
 if len(td)==4 and td[1].a:add('edogawa',td[1].a.text)
# さいたま name/caucus rows
for b in soup('saitama-names').select('.member_list li'):
 n=b.select_one('.name')
 if n:
  g=next((c.select_one('.text_cont').text for c in b.select('.cf') if c.select_one('.text_ttl') and '所属会派' in c.select_one('.text_ttl').text),None)
  add('saitama-names',n.text,g)
# Sapporo CC-BY 4.0 opendata: committee activities and counts
for row in list(csv.reader(io.StringIO((P/'sapporo-csv.raw').read_text(encoding='utf-8-sig'))))[1:]:
 if not row or not row[0]:continue
 fs=[]
 for idx in [6,10]:
  if row[idx]:fs.append({'category':'activity','title':row[idx]+' 委員','summary':'札幌市議会議員名簿の委員会所属欄に記載。委員長等の役職は別欄。','period':'2026-04-17現在','url':sources['sapporo-csv'],'sourceType':'行政・議会','asOf':D['sapporo']})
 if row[3]:fs.append({'category':'activity','title':'会派内役職：'+row[3],'summary':'会派「'+row[2]+'」における役職。政党役職とは区別。','period':'2026-04-17現在','url':sources['sapporo-csv'],'sourceType':'行政・議会','asOf':D['sapporo']})
 add('sapporo-csv',row[0],row[2],findings=fs)
# fail on duplicates rather than silently merging contradictory rows
out={};dups=[]
for p in people:
 key=(p['municipalityCode'],p['name'].replace(' ',''))
 if key in out:dups.append(key)
 else:out[key]=p
people=list(out.values())
result={'meta':{'retrievedAt':'2026-11-04','count':len(people),'scope':'北海道・東北・関東の11自治体の公式議員名簿。資料日現在の在職掲載であり、閲覧時点の現職保証ではない。会派は政党と区別。政策成果・職歴・地域活動の網羅調査ではない。資料日不明は明記。','licenseNotes':'札幌市データは札幌市議会事務局政策調査課作成、CC BY 4.0。その他は各自治体の公式名簿から氏名・公職・会派等の事実を抽出。私的連絡先は出力しない。','counts':dict(collections.Counter(p['municipality'] for p in people)),'duplicateKeys':dups},'people':people}
(P/'council-east.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result['meta'],ensure_ascii=False,indent=2))
