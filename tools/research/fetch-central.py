import urllib.request,concurrent.futures,lxml.html,json,pathlib,re
BASE=pathlib.Path(__file__).parent
SOURCES={
'osaka':('27100','大阪市','https://www.city.osaka.lg.jp/shikai/page/0000002245.html'),
'kyoto':('26100','京都市','https://www2.city.kyoto.lg.jp/shikai/meibo/gojuon.html'),
'kobe':('28100','神戸市','https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/50onmeibo.html'),
'nagoya':('23100','名古屋市','https://www.city.nagoya.jp/shikai/about/1030778/1030799.html'),
'sakai':('27140','堺市','https://www.city.sakai.lg.jp/shigikai/meibo/50on.html'),
'hamamatsu':('22130','浜松市','https://www.city.hamamatsu.shizuoka.jp/gikai/iinkai/meibo50.html'),
'shizuoka':('22100','静岡市','https://www.city.shizuoka.lg.jp/gikai/s900078.html'),
'niigata':('15100','新潟市','https://www.city.niigata.lg.jp/shigikai/index_meibo/meibo_02kaihabetsu.html'),
'nagano':('20201','長野市','https://www.city.nagano.nagano.jp/n440500/shigikai/p005267.html'),
'matsumoto':('20202','松本市','https://www.city.matsumoto.nagano.jp/site/gikai/6162.html'),
'kanazawa':('17201','金沢市','https://www4.city.kanazawa.lg.jp/soshikikarasagasu/gikaijimukyokugijichosaka/gyomuannai/1/5/3800.html'),
'himeji':('28201','姫路市','https://www.city.himeji.lg.jp/shisei/0000007766.html'),
'nishinomiya':('28204','西宮市','https://www.city.nishinomiya.lg.jp/nishinomiyashigikai/namelist/namelist02/meibo-list.html'),
'fukui':('18201','福井市','https://www.city.fukui.lg.jp/sisei/gikai/giin/p020856.html'),
'toyama':('16201','富山市','https://www.city.toyama.lg.jp/gikai/giinmeibo/1007104.html'),
'otsu':('25201','大津市','https://www.city.otsu.lg.jp/gikai/giin/1430447099023.html'),
'nara':('29201','奈良市','https://www.city.nara.lg.jp/site/narasigikai/115225.html'),
'suita':('27205','吹田市','https://www.city.suita.osaka.jp/shigikai/1017062/1012849.html'),
'okazaki':('23202','岡崎市','https://www.city.okazaki.lg.jp/shigikai/meibo/1009848.html'),
'kusatsu':('25206','草津市','https://www.city.kusatsu.shiga.jp/shigikai/shoukai/giin.html'),
 'toyonaka':('27203','豊中市','https://www.city.toyonaka.osaka.jp/shigikai/giinsyokai/giin/index.html'),
 'toyohashi':('23201','豊橋市','https://www.city.toyohashi.lg.jp/item/9866.htm'),
 'toyota':('23211','豊田市','https://www.toyota-shigikai.jp/lawmaker.html'),
 'takatsuki-a':('27207','高槻市','https://www.city.takatsuki.osaka.jp/site/takatsukishigikai/1016.html'),
 'takatsuki-n':('27207','高槻市','https://www.city.takatsuki.osaka.jp/site/takatsukishigikai/1017.html'),
 'kasugai':('23206','春日井市','https://www.city.kasugai.lg.jp/shisei/shigikai/giinmeibo.html'),
 'hirakata':('27210','枚方市','https://www.city.hirakata.osaka.jp/0000000172.html'),
}
def fetch(item):
 k,(_,name,u)=item;p=BASE/(k+'.html')
 try:
  if not p.exists():p.write_bytes(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=35).read())
  t=lxml.html.fromstring(p.read_bytes());t.make_links_absolute(u)
  out=[k,name,'TITLE '+''.join(t.xpath('//title/text()'))]
  for i,x in enumerate(t.xpath('//table')):
   rows=x.xpath('.//tr');out.append(str(i)+' rows '+str(len(rows))+' '+repr([[ ' '.join(c.text_content().split())[:80] for c in r.xpath('./td|./th')]for r in rows[:3]]))
  out.append('HEADINGS '+repr([x.text_content().strip() for x in t.xpath('//h2|//h3')][:10]))
  out.append('LINKS '+repr([(a.text_content().strip(),a.get('href'))for a in t.xpath('//a[@href]') if re.search('議員|meibo|kaiha|giin|氏名',a.text_content()+a.get('href',''))][-15:]))
  return '\n'.join(out)
 except Exception as e:return k+' ERROR '+str(e)
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=10)as ex:
  for s in ex.map(fetch,SOURCES.items()):print(s,flush=True)
