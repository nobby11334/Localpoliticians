import fs from 'node:fs';
fs.mkdirSync('dist/data',{recursive:true});
const seed=JSON.parse(fs.readFileSync('data/bunkyo.json'));
fs.writeFileSync('dist/bunkyo.html',fs.readFileSync('web/bunkyo.template.html','utf8').replace('__SEED__',JSON.stringify(seed).replace(/</g,'\\u003c')));
for(const f of ['index.html','app.js','style.css'])fs.copyFileSync('web/'+f,'dist/'+f);
for(const f of fs.readdirSync('data'))if(f.endsWith('.json'))fs.copyFileSync('data/'+f,'dist/data/'+f);
fs.writeFileSync('dist/.nojekyll','');
