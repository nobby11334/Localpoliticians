const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state={report:null,query:'',pref:'',mode:'leads',page:0};
const size=30,normalize=s=>String(s??'').normalize('NFKC').toLowerCase();
function items(){
 const d=state.report;if(!d)return [];
 let arr=state.mode==='leads'?d.leads||[]:state.mode==='missing'?d.municipalities.filter(x=>!x.mayorCandidates):state.mode==='recorded'?d.municipalities.filter(x=>x.mayorCandidates):d.municipalities.filter(x=>d.checks?.[x.code]?.error);
 const q=normalize(state.query);
 return arr.filter(x=>(!state.pref||x.pref===state.pref)&&(!q||normalize([x.municipality,x.title,x.pref,(x.mayorCandidateNames||[]).join(' ')].join(' ')).includes(q)));
}
function render(){
 const arr=items(),pages=Math.max(1,Math.ceil(arr.length/size));state.page=Math.min(state.page,pages-1);
 $('#audit-count').textContent=arr.length.toLocaleString()+'件 ／ '+(state.page+1)+' / '+pages+'ページ';
 $('#audit-list').innerHTML=arr.slice(state.page*size,(state.page+1)*size).map(x=>state.mode==='leads'
 ?'<article class="audit-card"><small>'+esc(x.pref)+' '+esc(x.municipality)+' ／ 一次資料の確認待ち</small><h3>'+esc(x.title)+'</h3><p>掲載日：'+esc(x.published||'不明')+'</p><a target="_blank" rel="noopener noreferrer" href="'+esc(x.url)+'">記事を確認 ↗</a>　<a href="./?municipality='+encodeURIComponent(x.municipalityCode)+'">自治体台帳</a></article>'
 :'<article class="audit-card"><small>'+esc(x.pref)+' ／ '+esc(x.code)+'</small><h3>'+esc(x.municipality)+'</h3><p>首長選：'+(x.mayorCandidates||0)+'件 ／ 議員選：'+(x.councilCandidates||0)+'件</p><p>'+esc((x.mayorCandidateNames||[]).join('、')||'候補者情報は未収録')+'</p>'+(state.mode==='failed'?'<p>巡回エラー：'+esc(state.report.checks?.[x.code]?.error||'不明')+'</p>':'')+'<a href="./?municipality='+encodeURIComponent(x.code)+'">自治体台帳を開く ↗</a></article>'
 ).join('')||'<p>記録はありません。候補者の不在を意味しません。</p>';
 $('#audit-page').innerHTML='<button id="audit-prev" '+(state.page===0?'disabled':'')+'>← 前へ</button><button id="audit-next" '+(state.page===pages-1?'disabled':'')+'>次へ →</button>';
 $('#audit-prev').onclick=()=>{state.page--;render()};$('#audit-next').onclick=()=>{state.page++;render()};
}
for(const [selector,key,event] of [['#audit-pref','pref','change'],['#audit-search','query','input'],['#audit-mode','mode','change']])$(selector).addEventListener(event,e=>{state[key]=e.target.value;state.page=0;render()});
try{
 const response=await fetch('data/candidate-audit.json',{cache:'no-store'});if(!response.ok)throw Error('監査結果が利用できません');const d=await response.json();state.report=d;
 const t=d.totals||{};$('#audit-metrics').innerHTML=[['対象自治体',t.municipalities],['首長候補を登録済み',t.mayorCandidateMunicipalities],['要確認記事',t.newsLeadsForReview],['巡回済み自治体',t.checkedMunicipalities]].map(([label,n])=>'<article><small>'+esc(label)+'</small><strong>'+Number(n||0).toLocaleString()+'</strong></article>').join('');
 $('#audit-time').textContent='最終監査：'+(d.updatedAt?new Date(d.updatedAt).toLocaleString('ja-JP',{timeZone:'Asia/Tokyo'}):'不明');
 $('#audit-pref').innerHTML+=[...new Set(d.municipalities.map(x=>x.pref))].sort().map(p=>'<option value="'+esc(p)+'">'+esc(p)+'</option>').join('');
 render();
}catch(error){$('#audit-count').textContent='監査結果を取得できませんでした：'+error.message}