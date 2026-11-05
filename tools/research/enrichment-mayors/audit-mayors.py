#!/usr/bin/env python3
"""Revalidate parsed facts against their saved official article, with no network."""
import argparse,collections,copy,importlib.util,json,pathlib,re
import settings as cfg
P=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('research',P/'enrich-mayors.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def source(row,research):
 url=row.get('profileURL')
 if not url:return None
 if url in research.seed:return research.seed[url]
 for u in [url]+[a['url'] for a in row['enrichment']['attempted']]:
  f=research.path(u)
  if f.exists():
   r=json.loads(f.read_text())
   if r['status']==200 and r['url']==url:return r['body']
 return None

def audit(rows,registry=None,cache_dir=None):
 registry=registry if registry is not None else json.loads(cfg.INPUT.read_text(encoding='utf-8'))
 people={(r['municipalityCode'],r['name']):r for r in registry}
 research=m.Research(cache_dir or cfg.CACHE)
 out=[];removed=0;changed=0
 for original in rows:
  row=copy.deepcopy(original);person=people[(row['municipalityCode'],row['name'])];body=source(row,research)
  if row.get('profileURL'):
   doc=m.document(body,row['profileURL']) if body else None
   if not doc or not m.identity(doc,person,row['profileURL']):
    removed+=len(row['findings']);row['findings']=[];row.pop('profileURL',None)
    row['enrichment']['status']='追加根拠未確認';row['enrichment']['note']+=' 本人を示す紹介見出し・氏名欄の再照合で確認条件を満たさず、経歴は採用しなかった。'
   else:
    curated=[f for f in row['findings'] if '前回手動確認' in f.get('evidence',{}).get('rule','')]
    new=m.extract(doc,row['profileURL'],person)
    for f in new:f['evidence']['matchedName']=person['name']
    if curated:
     combined=curated+[f for f in new if ('卒業' in f['summary'] or '修了' in f['summary'])]
    else:combined=new
    # Formal institution/role names are factual fragments. Drop narrative or article links.
    clean=[]
    for f in combined:
     fragment=f.get('evidence',{}).get('sourceFragment','')
     if fragment and (m.PRIVATE.search(fragment) or re.search(r'メッセージ|広報|卒業式|父は|母は|祖父|祖母|ご挨拶|あいさつ|講演会|お知らせ',fragment)):continue
     f.setdefault('evidence',{})['matchedName']=person['name']
     f['evidence']['rule']=f['evidence'].get('rule','')+'。氏名欄・本人紹介見出し等でフルネームを確認し、歴代・前任者への言及だけでは採用しない。'
     if f not in clean:clean.append(f)
    row['findings']=clean
    if clean and row['enrichment']['status'] not in ('情報追加','既存内容確認'):
     row['enrichment']['status']='情報追加'
     row['enrichment']['note']='保存済みの本人一致する公式紹介本文を再抽出し、経歴・役職の根拠を確認。年月・現任継続・経歴の網羅性を推測しない。'
    if not clean:row['enrichment']['status']='追加根拠未確認';row['enrichment']['note']+=' 根拠行の再点検後、短く確実に補完できる事実を確認できなかった。経歴がないとの意味ではない。'
  if row['findings']!=original['findings']:changed+=1
  out.append(row)
 return out,{'revalidatedPeople':len(out),'changedPeople':changed,'rejectedFindingsForIdentity':removed,'peopleWithFindings':sum(bool(r['findings']) for r in out),'findings':sum(len(r['findings']) for r in out),'statuses':dict(collections.Counter(r['enrichment']['status'] for r in out))}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--input',type=pathlib.Path,default=cfg.COLLECTED);a.add_argument('--output',type=pathlib.Path,default=cfg.AUDITED);args=a.parse_args()
 text=args.input.read_text();rows=[json.loads(l) for l in text.splitlines()] if args.input.suffix=='.jsonl' else json.loads(text)
 out,stats=audit(rows);cfg.write_json(args.output,out);print(json.dumps(stats,ensure_ascii=False))
