import urllib.request,concurrent.futures,json,re,os
from bs4 import BeautifulSoup
from urllib.parse import urljoin
ROOT=os.path.dirname(__file__); os.makedirs(ROOT+'/west-cache',exist_ok=True)
SOURCES={
'hiroshima':('34100','広島市','https://www.city.hiroshima.lg.jp/gikai/giin-shoukai/1010261.html'),
'fukuyama':('34207','福山市','https://www.city.fukuyama.hiroshima.jp/soshiki/gikaisyomu/94812.html'),
'kagoshima':('46201','鹿児島市','https://www.city.kagoshima.lg.jp/gikai/gksoumu/shigikai/shokai/ichiran2.html'),
'kumamoto':('43100','熊本市','https://kumamoto-shigikai.jp/kihon/pub/default.aspx?c_id=3'),
'fukuoka':('40130','福岡市','https://gikai.city.fukuoka.lg.jp/member/alphabet'),
'kitakyushu':('40100','北九州市','https://www.city.kitakyushu.lg.jp/sigikai/g0200147.html'),
'okayama':('33100','岡山市','https://www.city.okayama.jp/gikai/0000015787.html'),
'kochi':('39201','高知市','https://www.city.kochi.kochi.jp/soshiki/97/meibo.html'),
'tokushima':('36201','徳島市','https://www.city.tokushima.tokushima.jp/shigikai/giin_meibo/member.html'),
'matsuyama':('38201','松山市','https://www.city.matsuyama.ehime.jp/shigikai/syoukai/syoukai.html'),
'takamatsu':('37201','高松市','https://www.city.takamatsu.kagawa.jp/kurashi/shigikai/about/giin/shokai.html')}
def fetch(k):
 u=SOURCES[k][2];p=ROOT+'/west-cache/'+k+'.html'
 try:
  if not os.path.exists(p):
   b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=45).read();open(p,'wb').write(b)
  s=BeautifulSoup(open(p,'rb').read(),'html.parser')
  out=[]
  for t in s.select('table')[:2]:
   out.append(t.get_text(' ',strip=True)[:1200])
  links=[(a.get_text(' ',strip=True),urljoin(u,a['href'])) for a in s.select('a[href]') if re.search('議員|[一-龠]{2}.*[一-龠]{2}',a.get_text(' ',strip=True))]
  return k, out, links[-100:],s.get_text(' ',strip=True)[-1500:]
 except Exception as e:return k,str(e)
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as x:
  for r in x.map(fetch,SOURCES): print(json.dumps(r,ensure_ascii=False))
