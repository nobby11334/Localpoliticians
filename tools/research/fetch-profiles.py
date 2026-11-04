import pathlib,urllib.request,concurrent.futures,re,json
from html.parser import HTMLParser
P=pathlib.Path(__file__).parent
class Text(HTMLParser):
 def __init__(self):super().__init__();self.out=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ['script','style']:self.skip+=1
  if tag in ['p','li','tr','h1','h2','h3','h4','br','div']:self.out.append('\n')
 def handle_endtag(self,tag):
  if tag in ['script','style']:self.skip=max(0,self.skip-1)
  if tag in ['p','li','tr','h1','h2','h3','h4','div']:self.out.append('\n')
 def handle_data(self,data):
  if not self.skip:self.out.append(data)
def fetch(row):
 name,url=row.split('\t');f=P/'profiles'/f'{name}.html';f.parent.mkdir(exist_ok=True)
 try:
  if not f.exists():
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=22) as response:b=response.read();enc=response.headers.get_content_charset()
   if not enc:enc='utf-8'
   try:s=b.decode(enc)
   except UnicodeDecodeError:s=b.decode('cp932',errors='replace')
   f.write_text(s)
  s=f.read_text();t=Text();t.feed(s);text='\n'.join(l.strip() for l in ''.join(t.out).splitlines() if l.strip());f.with_suffix('.txt').write_text(text)
  return {'municipality':name,'url':url,'chars':len(text)}
 except Exception as e:return {'municipality':name,'url':url,'error':str(e)}
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as e:r=list(e.map(fetch,(P/'profile-urls.tsv').read_text().splitlines()))
 (P/'fetch-results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
 print(json.dumps(r,ensure_ascii=False))
