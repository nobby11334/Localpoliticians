"""Bounded first-party biography research. 6 workers, at most 2 fetches/host, one retry.
Output contains only newly supported facts. All records receive an audit trail.
Run from any directory; no repository files are modified.
"""
import os, json, re, urllib.request, urllib.parse, threading, concurrent.futures, hashlib, time, unicodedata
from pathlib import Path
from bs4 import BeautifulSoup, Tag
import research_config as cfg
ROOT = Path(__file__).resolve().parent
EXP = cfg.LEGACY_DIR
CACHE = cfg.CACHE_DIR
CACHE.mkdir(parents=True, exist_ok=True)
cfg.prepare_output()
DAY = cfg.CHECKED_AT
PEOPLE = cfg.load_people()
LOCK = threading.Lock()
HOSTS = {}
FETCH = {}
EVENTS = {}
REPORT = []

def norm(t):
    return re.sub('[\\s\\u200b\\ufeff・･]', '', unicodedata.normalize('NFKC', str(t)))

def text(t):
    return re.sub('\\s+', ' ', str(t)).strip()

def aliases(p):
    return list(dict.fromkeys([p['name']] + p.get('sourceNames', [])))

def matching(t, p):
    n = norm(t)
    for a in aliases(p):
        key = norm(a)
        if len(key) < 2 or (len(key) == 2 and norm(p['name']) != key):
            continue
        for hit in re.finditer(re.escape(key), n):
            before = n[:hit.start()]
            after = n[hit.end():]
            if before and re.match('[一-龥々﨑]', before[-1]) and (not re.search('(?:議員|市長|区長|町長|村長|県議|代表|現職|新人|候補者|氏名欄|氏名|名前|公式)$', before)):
                continue
            if after and re.match('[一-龥々﨑]', after[0]) and (not re.match('(?:議員|市長|区長|町長|村長|県議|候補|公式|経歴|学歴|政策|事務所|後援会|委員|代表|氏)', after)):
                continue
            return a
    return None

def urlstr(w):
    return w.get('url') if isinstance(w, dict) else w
LOCAL = {}
EXTRA = {}
try:
    for k, v in json.loads((EXP / 'west-sources.json').read_text(encoding='utf-8')).items():
        f = EXP / 'west-cache' / f'{k}.html'
        if f.exists() and f.stat().st_size:
            LOCAL[v[2]] = f
except Exception:
    pass
for fn in ['council-west.json', 'council-central.json', 'council-east.json']:
    try:
        data = json.loads((EXP / fn).read_text(encoding='utf-8'))
        rs = data.get('people', []) if isinstance(data, dict) else data
        for r in rs:
            for key in ['profileURL', 'officialProfileURL', 'website']:
                u = urlstr(r.get(key))
                if not u:
                    continue
                EXTRA.setdefault((r['municipalityCode'], norm(r['name'])), []).append(u)
                u = u.split('#')[0]
                dig = hashlib.sha256(u.encode()).hexdigest()
                for f in [EXP / 'west-profile-cache' / f'{dig[:20]}.html', EXP / 'east-profile-cache' / f'{dig[:20]}.html', EXP / 'east-profile-cache' / f'{dig}.html', EXP / f'profile-{dig[:12]}.html']:
                    if f.exists() and f.stat().st_size:
                        LOCAL[u] = f
    except Exception:
        pass

def get(u):
    u = u.split('#')[0]
    with LOCK:
        if u in FETCH:
            return FETCH[u]
        if u in EVENTS:
            evt = EVENTS[u]
            owner = False
        else:
            evt = threading.Event()
            EVENTS[u] = evt
            owner = True
    if not owner:
        evt.wait()
        return FETCH[u]
    result = None
    fn = CACHE / (hashlib.sha256(u.encode()).hexdigest()[:24] + '.html')
    meta = fn.with_suffix('.json')
    try:
        if u in LOCAL:
            result = (LOCAL[u].read_bytes(), u, '既取得キャッシュ確認', None)
        elif fn.exists() and fn.stat().st_size and meta.exists():
            m = json.loads(meta.read_text(encoding='utf-8'))
            result = (fn.read_bytes(), m['finalURL'], '取得済', None)
        elif any((x in urllib.parse.urlparse(u).netloc for x in ['facebook.com', 'x.com', 'twitter.com', 'instagram.com'])):
            result = (None, u, '取得対象外', 'SNSはプロフィール本文取得対象外')
        elif re.search('\\.(csv|xlsx?|pdf|zip)(\\?|$)', u, re.I):
            result = (None, u, '本文未取得', '名簿データは既存資料。個人プロフィールリンクを別途探索')
        else:
            host = urllib.parse.urlparse(u).netloc
            with LOCK:
                sem = HOSTS.setdefault(host, threading.Semaphore(cfg.HOST_CONCURRENCY))
            err = ''
            with sem:
                for retry in range(2):
                    try:
                        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (public biography verification)', 'Accept': 'text/html'})
                        with urllib.request.urlopen(req, timeout=cfg.HTTP_TIMEOUT) as r:
                            if 'pdf' in r.headers.get('Content-Type', ''):
                                raise ValueError('PDF本文は今回のHTML略歴抽出対象外')
                            b = r.read(3500000)
                            final = r.url
                        fn.write_bytes(b)
                        meta.write_text(json.dumps({'url': u, 'finalURL': final, 'checkedAt': DAY}, ensure_ascii=False), encoding='utf-8')
                        result = (b, final, '取得成功', None)
                        break
                    except Exception as e:
                        err = type(e).__name__ + ': ' + str(e)[:180]
            if result is None:
                result = (None, u, '取得失敗', err)
    except Exception as e:
        result = (None, u, '取得失敗', str(e)[:180])
    with LOCK:
        FETCH[u] = result
        evt.set()
    return result

def soupof(b):
    s = BeautifulSoup(b, 'html.parser')
    for x in s.select('script,style,nav,footer,header,noscript,aside'):
        x.decompose()
    return s

def isolate(s, p):
    for art in s.select('article.member-detail'):
        h = art.find(['h1', 'h2', 'h3'])
        if h and matching(h.get_text(' ', strip=True), p):
            return (art, h.get_text(' ', strip=True), 'article.member-detail')
    hs = [h for h in s.select('h1,h2,h3,h4') if len(h.get_text(' ', strip=True)) < 100 and matching(h.get_text(' ', strip=True), p)]
    if hs:
        h = hs[0]
        level = int(h.name[1])
        blocks = [str(h)]
        for sib in h.next_siblings:
            if isinstance(sib, Tag) and re.fullmatch('h[1-6]', sib.name) and (int(sib.name[1]) <= level):
                break
            blocks.append(str(sib))
        frag = BeautifulSoup(''.join(blocks), 'html.parser')
        if len(frag.get_text()) > 40:
            return (frag, h.get_text(' ', strip=True), h.name + ' ~ next heading')
        for par in list(h.parents)[:4]:
            if par.find('table') and len(par.get_text()) < 18000:
                return (par, h.get_text(' ', strip=True), 'matched heading ancestor with table')
    for t in s.select('table'):
        for tr in t.select('tr'):
            cs = tr.find_all(['td', 'th'], recursive=False)
            if len(cs) >= 2 and norm(cs[0].text) in ['氏名', '名前'] and matching(cs[1].text, p):
                return (t, '氏名欄 ' + text(cs[1].text), 'table: exact person name field')
    title = s.title.get_text(' ', strip=True) if s.title else ''
    if matching(title, p):
        main = s.select_one('main,article,#main,#content,.entry-content') or s
        return (main, title, 'dedicated page title + main')
    return (None, None, None)
BAD = re.compile('生年月日|誕生|生まれ|出生|住所|〒|電話|FAX|ファクス|メール|連絡先|[\\w.+-]+@[\\w.-]+|\\d{2,4}[-－]\\d{2,4}[-－]\\d{3,4}|妻|夫婦|長男|長女|次男|次女|家族|子ども[0-9０-９]|子供[0-9０-９]|人家族|児の父|児の母|(?:[一二三四五六七八九]+児|[一二三四五六七八九]+[男女](?:[一二三四五六七八九]+[男女]|の父|の母))|[0-9０-９]+児|息子|娘|配偶者|(?:祖父|祖母|父|母)(?:は|が|も|と|の跡|：)|結婚|趣味|血液型|好きな|出身地')
KEYS = {'経歴': 'career', '経歴等': 'career', '略歴': 'career', '主な経歴': 'career', '職歴': 'career', '学歴': 'career', '最終学歴': 'career', '議員歴': 'career', '議会歴': 'career', '役職': 'organization', '主な役職': 'organization', '現職': 'organization', '地域活動': 'community', '社会活動': 'community', '所属団体': 'organization', '政策': 'policy', '基本政策': 'policy', '重点政策': 'policy', '任期中に取り組みたいこと': 'policy'}
CAREER = re.compile('卒業|修了|卒[（(、。 ]|大学|大学院|専門学校|入社|入職|勤務|退職|教諭|教員|保育士|弁護士|税理士|会社員|銀行員|看護師|当選|初当選|議長|副議長|PTA|ＰＴＡ|保護者会|自治会|町内会|町会|理事|顧問|監事|事務局長|代表取締役|社長|専務|執行役員|会長|経験|従事|創業|起業|経営|入学|中退|留学|議会議員|消防団|[0-9０-９]+期|高等学校|高校|行政書士|社会保険労務士|社会福祉士|介護福祉士|理学療法士|作業療法士|歯科医師|医師|獣医師|博士|修士|学士|校長|教授|講師|防災士|民生委員|保護司|商工会|青年会議所')

def category(v, default):
    if default == 'policy':
        return default
    if re.search('PTA|ＰＴＡ|保護者会|自治会|町内会|町会|消防団', v):
        return 'community'
    if re.search('理事|顧問|監事|代表取締役|専務|社長|執行役員', v):
        return 'organization'
    return default

def facts(scope, p, u, stype, heading, selector):
    found = []
    existing = norm(' '.join((f.get('summary', '') + ' ' + f.get('title', '') for f in p.get('findings', []))))

    def add(v, key, cat):
        v = text(v)
        v = re.sub('^[・●○■\\-\\s]+', '', v)
        if len(v) < 3 or v in ['PTA', 'ＰＴＡ'] or len(v) > 230 or BAD.search(v):
            return
        if cat != 'policy' and re.search('子育て経験|育児経験|父親|母親', v):
            return
        if cat != 'policy' and (not CAREER.search(v)):
            return
        if norm(v) in existing:
            return
        c = category(v, cat)
        v = v.rstrip('。')
        summary = '政策として「' + v + '」を掲載。実現状況は未確認。' if c == 'policy' else '掲載経歴：' + v + '。'
        if len(summary) > 245:
            return
        year = re.search('(?:19|20)\\d{2}(?:[（(][^）)]{0,12}[）)])?(?:年|[./-]\\d{1,2})|(?:昭和|平成|令和)\\d{1,2}年', unicodedata.normalize('NFKC', v))
        title = {'career': '経歴・学歴', 'community': '地域活動・PTA等', 'organization': '団体・役職', 'policy': '掲げる政策'}[c]
        found.append({'category': c, 'title': title + '：' + v[:42], 'summary': summary, 'period': '記載年：' + year.group(0) + '（継続・終了時期は未確認）' if year else '掲載時点・期間不明', 'url': u, 'sourceType': stype, 'asOf': '掲載日時不明', 'checkedAt': DAY, 'evidence': {'matchedName': p['name'], 'sectionHeading': heading[:100] if heading else key, 'selector': selector + ' / ' + key, 'rule': '本人名一致の独立プロフィール範囲内。対象見出しまたは履歴欄の短い事実記載。家族・連絡先除外'}})
    for tr in scope.select('tr'):
        cs = tr.find_all(['td', 'th'], recursive=False)
        if len(cs) < 2:
            continue
        k = norm(cs[0].get_text())
        if len(k) < 35 and re.match('^(?:19|20)[0-9]{2}|^(?:昭和|平成|令和)[0-9０-９]+', k):
            add(' '.join((c.get_text(' ', strip=True) for c in cs[:2])), '経歴年表', 'career')
        if k not in KEYS:
            continue
        v = cs[1]
        for br in v.select('br'):
            br.replace_with('\n')
        for line in v.get_text('\n', strip=True).splitlines():
            for part in re.split('[。；;]', line):
                add(part, k, KEYS[k])
    for dt in scope.select('dt'):
        k = norm(dt.text)
        dd = dt.find_next_sibling('dd')
        if k in KEYS and dd:
            for br in dd.select('br'):
                br.replace_with('\n')
            for line in dd.get_text('\n', strip=True).splitlines():
                for part in re.split('[。；;]', line):
                    add(part, k, KEYS[k])
    for h in scope.select('h1,h2,h3,h4,h5'):
        k = norm(h.get_text())
        km = next((key for key in KEYS if k == key or (k in ['プロフィール', '略歴・プロフィール'] and key == '経歴')), None)
        if not km:
            continue
        for sib in h.next_siblings:
            if isinstance(sib, Tag) and re.fullmatch('h[1-6]', sib.name):
                break
            if not isinstance(sib, Tag):
                continue
            for line in sib.get_text('\n', strip=True).splitlines():
                for part in re.split('[。；;]', line):
                    add(part, km, KEYS[km])
    unique = {}
    for f in found:
        unique[f['category'], norm(f['summary'])] = f
    return list(unique.values())[:14]

def relevant_links(scope, p, u):
    links = []
    for tr in scope.select('tr'):
        cs = tr.find_all(['td', 'th'], recursive=False)
        if len(cs) > 1 and re.search('ホームページ|HP等|個人HP|ウェブサイト|Website', cs[0].get_text(), re.I):
            for a in cs[1].select('a[href]'):
                nu = urllib.parse.urljoin(u, a['href'])
                if nu.startswith('http'):
                    links.append((nu, '本人HP掲載リンク'))
    for dt in scope.select('dt'):
        if re.search('ホームページ|HP等|個人HP|ウェブサイト|Website', dt.get_text(), re.I):
            dd = dt.find_next_sibling('dd')
            if dd:
                for a in dd.select('a[href]'):
                    nu = urllib.parse.urljoin(u, a['href'])
                    if nu.startswith('http'):
                        links.append((nu, '本人HP掲載リンク'))
    for a in scope.select('a[href]'):
        href = urllib.parse.urljoin(u, a.get('href', ''))
        label = text(a.get_text(' ', strip=True) + ' ' + a.get('title', '') + ' ' + ' '.join((i.get('alt', '') for i in a.select('img'))))
        if not href.startswith(('http://', 'https://')) or re.search('\\.(pdf|zip|xlsx?)(\\?|$)', href, re.I):
            continue
        if any((s in urllib.parse.urlparse(href).netloc for s in ['facebook.com', 'twitter.com', 'x.com', 'instagram.com', 'youtube.com', 'line.me', 'wikipedia.org', 'wikidata.org'])):
            continue
        if re.search('ホームページ|公式サイト|オフィシャル|個人サイト|公式HP', label):
            links.append((href, '本人HP掲載リンク'))
        elif matching(label, p) and len(label) < 80:
            links.append((href, '本人名一致リンク'))
        elif re.search('プロフィール|略歴|経歴|profile|about|政策|policy|vision', label + ' ' + urllib.parse.urlparse(href).path, re.I) and urllib.parse.urlparse(href).netloc == urllib.parse.urlparse(u).netloc:
            links.append((href, 'プロフィール・政策へのリンク'))
    return list(dict.fromkeys(links))

def stype(u):
    h = urllib.parse.urlparse(u).netloc
    if any((s in h for s in ['city.', 'town.', 'vill.', 'pref.', 'gikai.', 'shigikai', 'gijiroku.com'])):
        return '行政・議会'
    if any((s in h for s in ['cdp-japan', 'new-kokumin', 'o-ishin', 'tokyo-jimin', 'jimin.jp'])):
        return '政党公式'
    return '本人発信'

def one(p):
    res = {'id': p['id'], 'municipalityCode': p['municipalityCode'], 'name': p['name'], 'findings': []}
    attempts = []
    visited = set()
    confirmed = False
    successful = False
    newwebsite = None
    roots = []
    w = urlstr(p.get('website'))
    if w:
        roots.append((w, '既存website'))
    for a in [] if p.get('_ignoreExtra') else aliases(p):
        for u in EXTRA.get((p['municipalityCode'], norm(a)), []):
            roots.append((u, '既取得名簿の本人リンク'))
    for ss in p.get('sources', []):
        if ss.get('url'):
            roots.append((ss['url'], '既存公式出典'))
    if p.get('sourceURL'):
        roots.append((p['sourceURL'], '既存公式出典'))
    roots = list(dict.fromkeys(roots))[:4]
    queue = roots.copy()
    followed = 0
    while queue and len(visited) < 8:
        u, why = queue.pop(0)
        u = u.split('#')[0]
        if u in visited:
            continue
        visited.add(u)
        b, final, status, error = get(u)
        item = {'url': u, 'status': status}
        if error:
            item['error'] = error
        attempts.append(item)
        if not b:
            continue
        successful = True
        try:
            s = soupof(b)
        except Exception:
            continue
        scope, heading, sel = isolate(s, p)
        if scope:
            confirmed = True
            new = facts(scope, p, final, stype(final), heading, sel)
            res['findings'] += new
            for nu, rule in relevant_links(scope, p, final):
                if nu.split('#')[0] not in visited and followed < 4:
                    queue.append((nu, rule))
                    followed += 1
                    if rule == '本人HP掲載リンク' and urllib.parse.urlparse(nu).netloc != urllib.parse.urlparse(final).netloc:
                        newwebsite = {'url': nu, 'kind': '本人公式HP（公式紹介からリンク）', 'sourceUrl': final}
        else:
            for a in s.select('a[href]'):
                lab = text(a.get_text(' ', strip=True))
                if matching(lab, p) and len(lab) < 90:
                    nu = urllib.parse.urljoin(final, a['href'])
                    if nu.startswith('http') and nu.split('#')[0] not in visited and (followed < 3):
                        queue.append((nu, '公式名簿の本人名リンク'))
                        followed += 1
    unique = {}
    for f in res['findings']:
        unique[f['category'], norm(f['summary'])] = f
    res['findings'] = list(unique.values())[:24]
    if newwebsite and newwebsite['url'].split('#')[0] in visited:
        b, _, _, _ = get(newwebsite['url'])
        if b and matching(BeautifulSoup(b, 'html.parser').get_text(' ', strip=True), p):
            res['website'] = newwebsite
    status = '情報追加' if res['findings'] else '既存内容確認' if confirmed else '追加根拠未確認' if successful else '取得失敗'
    res['enrichment'] = {'checkedAt': DAY, 'status': status, 'attempted': attempts, 'note': '本人名一致を確認した範囲のみ追加。候補掲載・旧資料を現職の証明としない。既存名簿・所属の再記載は追加しない。' if confirmed else '本人名一致の経歴・政策根拠を追加確認できず。候補・現職・同姓同名の推測補完なし。'}
    return res

def main():
    out = []
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=cfg.MAX_WORKERS) as ex:
        buckets = {}
        for p in PEOPLE:
            u = urlstr(p.get('website')) or p.get('sourceURL', '')
            buckets.setdefault(urllib.parse.urlparse(u).netloc, []).append(p)
        from collections import deque
        buckets = [deque(v) for v in buckets.values()]
        ordered = []
        while any(buckets):
            for bucket in buckets:
                if bucket:
                    ordered.append(bucket.popleft())
        fs = {ex.submit(one, p): p for p in ordered}
        for f in concurrent.futures.as_completed(fs):
            p = fs[f]
            try:
                r = f.result()
            except Exception as e:
                r = {'id': p['id'], 'municipalityCode': p['municipalityCode'], 'name': p['name'], 'findings': [], 'enrichment': {'checkedAt': DAY, 'status': '取得失敗', 'attempted': [], 'note': str(e)[:200]}}
            out.append(r)
            if len(out) % 50 == 0:
                cfg.PARTIAL_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
                print('PROGRESS', len(out), 'added', sum((bool(x['findings']) for x in out)), 'facts', sum((len(x['findings']) for x in out)), 'secs', int(time.time() - start), flush=True)
    order = {p['id']: i for i, p in enumerate(PEOPLE)}
    out.sort(key=lambda r: order[r['id']])
    cfg.RESULT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print('DONE', len(out), flush=True)
if __name__ == '__main__':
    main()
