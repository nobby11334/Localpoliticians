import pathlib,json,hashlib,urllib.request,concurrent.futures
P=pathlib.Path(__file__).parent
home={(c,n,u) for c,n,u,src in json.load(open(P/'east-personal-links.json'))}
seen=set();urls=[]
for c,n,u,src in json.load(open(P/'east-biography-jobs.json')):
 if (c,n,u) in home or (c,n) in seen:continue
 seen.add((c,n));f=P/'east-profile-cache'/(hashlib.sha256(u.encode()).hexdigest()+'.html')
 if not f.exists():urls.append(u)
urls=urls[:42]
def f(u):
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  b=urllib.request.urlopen(req,timeout=12).read(2000000)
  (P/'east-profile-cache'/(hashlib.sha256(u.encode()).hexdigest()+'.html')).write_bytes(b);return 1
 except:return 0
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:print('new profiles',sum(ex.map(f,urls)),len(urls))
