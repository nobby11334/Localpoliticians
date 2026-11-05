"""Second pass: explicit HP-labelled links inside matched official member profiles only."""
import importlib.util, json, hashlib, concurrent.futures, collections, urllib.parse
from pathlib import Path
import research_config as cfg
cfg.prepare_output()
R = Path(__file__).resolve().parent
sp = importlib.util.spec_from_file_location('research_b', R / 'research-other-b.py')
m = importlib.util.module_from_spec(sp)
sp.loader.exec_module(m)
from functools import lru_cache

@lru_cache(maxsize=2048)
def cached_soup(path):
    return m.soupof(Path(path).read_bytes())
P = cfg.RESULT_PATH
A = json.loads(P.read_text(encoding='utf-8'))
raw = {p['id']: p for p in m.PEOPLE}
jobs = []
for x in A:
    p = raw[x['id']]
    visited = {a['url'].split('#')[0] for a in x['enrichment']['attempted']}
    new = []
    for att in x['enrichment']['attempted']:
        u = att['url'].split('#')[0]
        f = cfg.CACHE_DIR / (hashlib.sha256(u.encode()).hexdigest()[:24] + '.html')
        if not f.exists():
            f = m.LOCAL.get(u)
        if not f or not f.exists() or (not f.stat().st_size):
            continue
        try:
            scope, h, sel = m.isolate(cached_soup(str(f)), p)
            if not scope:
                continue
            for nu, why in m.relevant_links(scope, p, u):
                host = urllib.parse.urlparse(nu).netloc
                if why == '本人HP掲載リンク' and nu.split('#')[0] not in visited and (not any((t in host for t in ['facebook', 'twitter', 'x.com', 'instagram', 'youtube', 'line.me', 'wikipedia.org']))):
                    new.append((nu, u))
            if scope and m.stype(u) == '本人発信' and (not any((t in urllib.parse.urlparse(u).netloc for t in ['go2senkyo', 'ameblo', 'note.com', 'facebook', 'twitter', 'x.com']))):
                raw_s = m.BeautifulSoup(f.read_bytes(), 'html.parser')
                for a in raw_s.select('a[href]'):
                    nu = urllib.parse.urljoin(u, a['href'])
                    label = a.get_text(' ', strip=True)
                    path = urllib.parse.urlparse(nu).path
                    if urllib.parse.urlparse(nu).netloc != urllib.parse.urlparse(u).netloc:
                        continue
                    if nu.split('#')[0] in visited or not nu.startswith('http'):
                        continue
                    if m.re.search('プロフィール|略歴|経歴|政策|profile|biography|keireki|/about(?:/|$)|/policy(?:/|$)', label + ' ' + path, m.re.I):
                        new.append((nu, u))
        except:
            pass
    for nu, src in list(dict.fromkeys(new))[:2]:
        jobs.append((x, p, nu, src))
print('HP JOBS', len(jobs), flush=True)
RECORD_LOCK = m.threading.Lock()

def work(j):
    x, p, u, src = j
    copy = p.copy()
    copy['website'] = {'url': u}
    copy['sourceURL'] = u
    copy['sources'] = []
    copy['_ignoreExtra'] = True
    r = m.one(copy)
    with RECORD_LOCK:
        x['findings'] += r['findings']
        x['enrichment']['attempted'] += r['enrichment']['attempted']
    if r['enrichment']['status'] in ['情報追加', '既存内容確認']:
        x['website'] = {'url': u, 'kind': '公式の本人紹介から確認した関連HP・プロフィール', 'sourceUrl': src}
    if x['findings']:
        x['enrichment']['status'] = '情報追加'
    return x['id']
with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.MAX_WORKERS) as ex:
    for i, r in enumerate(ex.map(work, jobs), 1):
        if i % 20 == 0:
            print('HP progress', i, flush=True)
P.write_text(json.dumps(A, ensure_ascii=False, indent=2), encoding='utf-8')
print('HP DONE', len(jobs), flush=True)
