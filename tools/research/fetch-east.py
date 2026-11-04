import urllib.request,json,concurrent.futures,pathlib
from bs4 import BeautifulSoup
ROOT=pathlib.Path(__file__).parent
sources={
'yokohama':'https://www.city.yokohama.lg.jp/shikai/giin/kaihabetsu.html',
'kawasaki':'https://www.city.kawasaki.jp/shisei/category/40-3-4-0-0-0-0-0-0-0.html',
'chiba':'https://www.city.chiba.jp/shigikai/kaiha.html',
'sendai':'https://www.gikai.city.sendai.jp/list/district/index.html',
'saitama':'https://www.city.saitama.lg.jp/gikai/001/meibo/index.html',
'nerima':'https://www.city.nerima.tokyo.jp/gikai/giin/20ichiran.html',
'ota':'https://www.city.ota.tokyo.jp/gikai/shoukai/giinsyokai.html',
'itabashi':'https://www.city.itabashi.tokyo.jp/kugikai/giin/1010916.html',
'suginami':'https://www.city.suginami.tokyo.jp/kugikai/s117/4101.html',
'edogawa':'https://www.gikai.city.edogawa.tokyo.jp/g07_giinlist.asp?Hmode=20',
'minato':'https://www.gikai.city.minato.tokyo.jp/0000002539.html',
'sapporo':'https://ckan.pf-sapporo.jp/api/3/action/package_show?id=sapporo_city_counsilors_directory',
}
def fetch(kv):
 k,u=kv
 try:
  data=urllib.request.urlopen(u,timeout=40).read();(ROOT/(k+'.raw')).write_bytes(data)
  try:t=data.decode('utf-8')
  except:t=data.decode('cp932',errors='replace')
  soup=BeautifulSoup(t,'html.parser');(ROOT/(k+'.txt')).write_text(soup.get_text(' ',strip=True));print(k,len(data),len(soup.select('table')))
 except Exception as e: print(k,str(e))
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:list(ex.map(fetch,sources.items()))
