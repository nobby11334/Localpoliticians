import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
execFileSync('python',['scripts/merge-expanded.py'],{stdio:'inherit'});
fs.mkdirSync('dist/data',{recursive:true});
const seed=JSON.parse(fs.readFileSync('data/bunkyo.json'));
// The curated Bunkyo view uses the same additive nationwide research.
const bunkyo=JSON.parse(fs.readFileSync('data/regions/13105.json'));
for(const p of seed.people){const normalized=s=>s.normalize('NFKC').replace(/[\s　]/g,'').replaceAll('﨑','崎').replaceAll('髙','高').replaceAll('塚','塚');const enriched=bunkyo.people.find(x=>normalized(x.name)===normalized(p.name));if(!enriched?.enrichment)continue;p.enrichment=enriched.enrichment;p.relatedWebsites=enriched.relatedWebsites;for(const f of enriched.findings.filter(f=>f.method)){if(!p.findings.some(x=>x.url===f.url&&x.summary===f.summary))p.findings.push(f);}}

fs.writeFileSync('dist/bunkyo.html',fs.readFileSync('web/bunkyo.template.html','utf8').replace('__SEED__',JSON.stringify(seed).replace(/</g,'\\u003c')));
for(const f of ['index.html','app.js','style.css'])fs.copyFileSync('web/'+f,'dist/'+f);
let index=fs.readFileSync('dist/index.html','utf8');
for(const asset of ['app.js','style.css']){const hash=createHash('sha256').update(fs.readFileSync('dist/'+asset)).digest('hex').slice(0,12);index=index.replaceAll('"'+asset+'"','"'+asset+'?v='+hash+'"');}
fs.writeFileSync('dist/index.html',index);
for(const f of fs.readdirSync('data'))if(f.endsWith('.json'))fs.copyFileSync('data/'+f,'dist/data/'+f);
fs.cpSync('data/regions','dist/data/regions',{recursive:true});
fs.writeFileSync('dist/.nojekyll','');
