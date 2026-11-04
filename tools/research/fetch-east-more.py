from importlib.machinery import SourceFileLoader
m=SourceFileLoader('east','./fetch-east.py').load_module()
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import concurrent.futures,json
s={}
for n in ['chiba','sendai']:
 soup=BeautifulSoup((m.ROOT/(n+'.raw')).read_bytes(),'html.parser')
 for a in soup.select('a'):
  h=a.get('href','');t=a.text.strip()
  if (n=='chiba' and 'list_kaiha' in h) or (n=='sendai' and '/index.html' in h and t.endswith('区')):s[n+'-'+h.split('/')[-2 if n=='sendai' else -1].split('.')[0]]=urljoin(m.sources[n],h)
s['sapporo-csv']=json.loads((m.ROOT/'sapporo.raw').read_text())['result']['resources'][0]['url']
s['saitama-names']='https://www.city.saitama.lg.jp/gikai/001/002/001/index.html'
(m.ROOT/'east-extra-sources.json').write_text(json.dumps(s,ensure_ascii=False,indent=2))
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:list(ex.map(m.fetch,s.items()))
