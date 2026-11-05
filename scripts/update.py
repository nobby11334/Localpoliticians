"""Check public sources. Changes are review candidates, never automatic politician facts."""
import concurrent.futures,datetime,hashlib,html,json,re,gzip,urllib.request,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
seed=json.loads((ROOT/'data/bunkyo.json').read_text())
status=json.loads((ROOT/'data/status.json').read_text())
previous={c['id']:c for c in status['checks']}
sources=seed['monitors']+[{'id':'national-mayor-publication','name':'全国首長名簿','url':'https://jichisoken.jp/publication/esearchpaper-142/','expected':'首長'}]
expanded=ROOT/'data/expanded-sources.json'
if expanded.exists():sources+=json.loads(expanded.read_text())
# Enriched individual profiles rotate through 28 daily batches to limit load.
profile_sources={};base_urls={s['url'] for s in sources}
for path in sorted((ROOT/'data/enrichment').glob('*.json.gz')):
    for person in json.loads(gzip.decompress(path.read_bytes())):
        for finding in person.get('findings',[]):
            u=finding['url']
            if u in base_urls:continue
            key=hashlib.sha256(u.encode()).hexdigest()
            if int(key[:8],16)%28!=datetime.datetime.now(datetime.timezone.utc).date().toordinal()%28:continue
            profile_sources[u]={'id':'profile-'+key[:16],'name':person['name']+' 公開プロフィール','url':u}
sources+=list(profile_sources.values())
sources=list({s['url']:s for s in sources}.values())
def check(s):
    old=previous.get(s['id'],{});out={**old,'id':s['id'],'name':s['name'],'url':s['url'],'checkedAt':now}
    try:
        req=urllib.request.Request(s['url'],headers={'User-Agent':'CivicLedger/2.0 public source monitor'})
        with urllib.request.urlopen(req,timeout=20) as r:
            mime=r.headers.get_content_type();raw=r.read(8_000_001)
            if len(raw)>8_000_000:raise ValueError('資料が取得上限8MBを超えました')
            binary=raw.startswith(b'%PDF-') or (raw.startswith(b'PK') and urllib.parse.urlparse(s['url']).path.lower().endswith(('.xlsx','.docx')))
            if binary:
                digest=hashlib.sha256(raw).hexdigest();version=4
            else:
                if mime not in ('text/html','application/xhtml+xml','text/plain'):raise ValueError('対応していない資料形式')
                text=raw.decode(r.headers.get_content_charset() or 'utf-8',errors='replace')
                text=re.sub(r'<(script|style|nav|header|footer)\b[^>]*>.*?</\1>',' ',text,flags=re.I|re.S)
                text=html.unescape(re.sub(r'<[^>]+>',' ',text));text=re.sub(r'\s+',' ',text).strip()
                expected=s.get('expected');expected=expected if isinstance(expected,list) else [expected] if expected else []
                if len(text)<100 or (expected and not any(x in re.sub(r'\s','',text) for x in expected)):raise ValueError('本文または期待する見出しを確認できません')
                digest=hashlib.sha256(text.encode()).hexdigest();version=3
        changed=old.get('extractorVersion')==version and old.get('hash') and old['hash']!=digest
        out.update(hash=digest,extractorVersion=version,lastSuccessAt=now,error=None,changed=bool(changed))
        event={'id':s['id']+'-'+digest[:16],'name':s['name'],'url':s['url'],'detectedAt':now,'hash':digest,'message':'公開資料の変更を検出。所属・経歴・実績・出馬の変化かは未確認です。'} if changed else None
        return out,event
    except Exception as e:out['error']=str(e)[:180];return out,None
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(check,sources))
checked={r[0]['id']:r[0] for r in results};status['checks']=list({**previous,**checked}.values());known={x['id'] for x in status['changes']}
status['changes'] += [r[1] for r in results if r[1] and r[1]['id'] not in known]
status['changes']=status['changes'][-500:];status['updatedAt']=now
(ROOT/'data/status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
print(f"Checked {len(results)} sources; {sum(bool(r[0].get('error')) for r in results)} failed. Previous successful hashes retained on failure.")
