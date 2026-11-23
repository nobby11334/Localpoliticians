"""Refresh a nationwide election-calendar reference CSV (not official candidacy evidence)."""
import csv,datetime as dt,io,json,re,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'data/election-calendar.json'
SOURCE='https://senkyo-data.jp/data/senkyo-data.csv'
def valid_date(s):
 if not s:return None
 try:return dt.date.fromisoformat(s).isoformat()
 except (ValueError,TypeError):return None
def normalize_code(value):
 value=str(value or '').strip()
 return value[:5] if re.fullmatch(r'\d{6}',value) else value if re.fullmatch(r'\d{5}',value) else None
def to_entry(row,valid_codes):
 code=normalize_code(row.get('団体コード'))
 if code not in valid_codes:return None
 item={'pref':row.get('都道府県',''),'name':row.get('市区町村',''),
       'nextMayorElection':valid_date(row.get('次の首長選挙の投票日')),
       'nextCouncilElection':valid_date(row.get('次の議員選挙の投票日')),
       'mayorTermEnd':valid_date(row.get('首長の任期満了日')),
       'councilTermEnd':valid_date(row.get('議員の任期満了日')),
       'checkedAt':valid_date(row.get('最終確認日')),
       'referenceURL':row.get('出典つきのページ','')}
 if item['referenceURL'] and not item['referenceURL'].startswith('https://senkyo-data.jp/'):
  item['referenceURL']=''
 return code,item
def sync():
 old=json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {'municipalities':{}}
 codes={str(x['code']) for x in json.loads((ROOT/'data/national.json').read_text())['municipalities']}
 try:
  req=urllib.request.Request(SOURCE,headers={'User-Agent':'Localpoliticians/1.0 public civic monitor'})
  with urllib.request.urlopen(req,timeout=30) as response:
   if response.geturl()!=SOURCE:raise ValueError('Unexpected calendar source redirect')
   data=response.read(5000001)
  if len(data)>5000000:raise ValueError('Calendar CSV exceeds limit')
  reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
  required={'団体コード','次の首長選挙の投票日','次の議員選挙の投票日','首長の任期満了日','議員の任期満了日'}
  if not required.issubset(reader.fieldnames or []):raise ValueError('Calendar CSV schema changed')
  entries={}
  for row in reader:
   entry=to_entry(row,codes)
   if entry:entries[entry[0]]=entry[1]
  # Reject provider failures or unexpectedly incomplete exports, retaining previous valid snapshot.
  if len(entries)<1400:raise ValueError('Unexpectedly low municipality coverage')
  output={'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
   'source':SOURCE,'notice':'参考データ。候補者氏名は含まれず、公式日程は各選挙管理委員会で要確認。',
   'municipalities':entries,'count':len(entries)}
  OUTPUT.write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n')
  print('Calendar loaded',len(entries),'municipalities')
 except Exception as error:
  print('Calendar update failed; previous snapshot retained:',str(error)[:220])
  if not OUTPUT.exists():
   OUTPUT.write_text(json.dumps({**old,'updatedAt':None,'source':SOURCE,'notice':'参考資料取得に失敗。登録日程なし。','count':0},ensure_ascii=False)+'\n')
if __name__=='__main__':sync()
