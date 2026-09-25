let S=null,P=null,V=[],currentTable=null;const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const COLORS=['#4f46e5','#db2777','#16a34a','#ea580c','#0891b2','#9333ea','#65a30d','#dc2626','#0f766e','#c026d3'];
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function toast(s){let x=$('#toast');x.textContent=s;x.classList.add('show');clearTimeout(toast.t);toast.t=setTimeout(()=>x.classList.remove('show'),2300)}
async function api(url,opt={}){let r;try{r=await fetch(url,opt)}catch(e){toast('אין חיבור לשרת המקומי');throw e}let d;try{d=await r.json()}catch(e){let msg='השרת החזיר תשובה לא תקינה ('+r.status+')';toast(msg);throw Error(msg)}if(!r.ok){let msg=d.error||'שגיאה '+r.status;toast(msg);throw Error(msg)}return d}
const json=(method,body)=>({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
async function load(){let d=await api('/api/state');S=d.state;P=d.project;V=d.violations||[];render()}
function group(gid){return P.groups.find(g=>g.id===gid)}function table(tid){return P.tables.find(t=>t.id===tid)}
function color(gid){let i=P.groups.findIndex(g=>g.id===gid);return COLORS[(i<0?0:i)%COLORS.length]}
function render(){if(!P)return;P.hall.seating_type??='round_tables';P.hall_objects??=[];P.settings??={seat_preference:'front_center',front_weight:1,center_weight:.35};P.tables.forEach(t=>{t.kind??='table';t.shape??='round'});$('#projectTitle').textContent=P.name;$('#hallName').value=P.hall.name;$('#stageLabel').value=P.hall.stage_label;$('#seatingType').value=P.hall.seating_type;renderBuilder();renderHall('#hallCanvas',true);renderHall('#assignCanvas',false);renderAssignmentPro();renderGroups();renderPeople();renderRules();renderWaiting();renderVersions();renderProjects();renderStats()}
$$('.steps button').forEach(b=>b.onclick=()=>{$$('.steps button').forEach(x=>x.classList.remove('active'));b.classList.add('active');$$('.view').forEach(v=>v.classList.remove('active'));$('#view-'+b.dataset.view).classList.add('active')});
function commonMapSetup(h){h.style.setProperty('--grid-cell',CELL+'px');h.style.width=(GRID_COLS*CELL)+'px';h.style.height=(GRID_ROWS*CELL)+'px';h.style.minWidth=(GRID_COLS*CELL)+'px';h.style.minHeight=(GRID_ROWS*CELL)+'px';h.classList.add('unified-hall-map')}
function commonMapStyle(el,r){el.style.right=(r.gx*CELL+1)+'px';el.style.top=(r.gy*CELL+1)+'px';el.style.left='auto';el.style.width=(r.gw*CELL-2)+'px';el.style.height=(r.gh*CELL-2)+'px';el.style.transform='none'}
function renderHall(sel,editable){let h=$(sel);if(!h)return;h.innerHTML='';commonMapSetup(h);h.classList.toggle('edit',editable&&$('#editMode').checked);let by={};P.people.forEach(x=>{if(x.table_id)(by[x.table_id]??=[]).push(x)});
 P.hall_objects??=[];P.hall_objects.forEach(o=>{let z=document.createElement('div');z.className='hall-object object-'+(o.kind||'zone');commonMapStyle(z,gridRect(o));z.innerHTML='<span>'+esc(o.name||'')+'</span>';h.appendChild(z)});
 P.tables.forEach(t=>{let d=document.createElement('div');d.className='table unified-seat '+(t.kind==='seat'?'chair':('shape-'+(t.shape||'round')));commonMapStyle(d,gridRect(t));let occ=by[t.id]||[];d.innerHTML=`<span class="name">${esc(t.name)}</span><span class="meta">${occ.length}/${t.capacity} · דירוג ${t.rank}</span><span class="dots">${Array.from({length:t.capacity},(_,i)=>{let o=occ.find(x=>x.seat===i);return `<i class="seatdot ${o?'full':''} ${o?.locked?'lock':''}" style="${o?'background:'+color(o.group_id):''}" title="${esc(o?.name||'פנוי')}"></i>`}).join('')}</span>`;d.onclick=()=>openTable(t.id);if(editable)d.onpointerdown=e=>dragStart(e,d,t);h.appendChild(d)})}
let drag=null;
function dragStart(e,el,t){if(!$('#editMode').checked)return;let r=gridRect(t),p=mapCellXY(e,$('#hallCanvas'));drag={el,t,canvas:$('#hallCanvas'),r,off:{x:p.x-r.gx,y:p.y-r.gy},last:null};el.setPointerCapture(e.pointerId);el.onpointermove=dragMove;el.onpointerup=dragEnd;e.preventDefault()}
function mapCellXY(e,canvas){let r=canvas.getBoundingClientRect();return{x:clampI(Math.floor((r.right-e.clientX)/CELL),0,GRID_COLS-1),y:clampI(Math.floor((e.clientY-r.top)/CELL),0,GRID_ROWS-1)}}
function dragMove(e){if(!drag)return;let p=mapCellXY(e,drag.canvas),nr={...drag.r,gx:clampI(p.x-drag.off.x,0,GRID_COLS-drag.r.gw),gy:clampI(p.y-drag.off.y,0,GRID_ROWS-drag.r.gh)};commonMapStyle(drag.el,nr);drag.last=nr}
async function dragEnd(){if(drag?.last){let d=drag,dx=d.last.gx-d.r.gx,dy=d.last.gy-d.r.gy;drag=null;use(await api('/api/tables/bulk',json('POST',{ids:[d.t.id],action:'move',grid_dx:dx,grid_dy:dy,dx:0,dy:0})))}else drag=null}
$('#editMode').onchange=()=>renderHall('#hallCanvas',true);
$('#saveHall').onclick=async()=>{let d=await api('/api/hall',json('POST',{name:$('#hallName').value,stage_label:$('#stageLabel').value,seating_type:$('#seatingType').value}));use(d);toast('מבנה האולם נשמר')};
$('#addTable').onclick=async()=>{let d=await api('/api/tables',json('POST',{capacity:4,rank:10,x:50,y:50}));use(d);openTable(P.tables.at(-1).id)};
function openTable(id){currentTable=id;let t=table(id);if(!t)return;$('#tName').value=t.name;$('#tKind').value=t.kind||'table';$('#tShape').value=t.shape||'round';$('#tCapacity').value=t.capacity;$('#tCustomRank').checked=!!t.custom_rank;$('#tRank').value=t.rank;$('#tRank').disabled=!t.custom_rank;$('#tZone').value=t.zone||'';$('#tTags').value=(t.tags||[]).join(', ');$('#tDisabled').checked=!!t.disabled;$('#tX').value=Math.round(t.x*10)/10;$('#tY').value=Math.round(t.y*10)/10;$('#tLocked').checked=!!t.locked;let occ=P.people.filter(x=>x.table_id===id);$('#tableSeats').innerHTML='<h3>מקומות בשולחן</h3>'+Array.from({length:t.capacity},(_,i)=>{let o=occ.find(x=>x.seat===i);return `<div class="seatline"><b>מקום ${i+1}</b><select data-seat="${i}"><option value="">פנוי</option>${P.people.filter(x=>!x.table_id||x.id===o?.id).map(x=>`<option value="${x.id}" ${x.id===o?.id?'selected':''}>${esc(x.name)}${group(x.group_id)?' · '+esc(group(x.group_id).name):''}</option>`).join('')}</select>${o?`<span>${o.locked?'🔒':''}</span>`:''}</div>`}).join('');$$('#tableSeats select').forEach(s=>s.onchange=async()=>{let old=occ.find(x=>x.seat===+s.dataset.seat);if(!s.value&&old){let d=await api('/api/seat',json('POST',{person_id:old.id,table_id:null}));use(d)}else if(s.value){let d=await api('/api/seat',json('POST',{person_id:s.value,table_id:id,seat:+s.dataset.seat}));use(d)}openTable(id)});$('#tableDlg').showModal()}
async function patchTable(id,b){let d=await api('/api/tables/'+id,json('PATCH',b));use(d)}
$('#saveTable').onclick=async()=>{await patchTable(currentTable,{name:$('#tName').value,kind:$('#tKind').value,shape:$('#tShape').value,capacity:+$('#tCapacity').value,rank:+$('#tRank').value,custom_rank:$('#tCustomRank').checked,x:+$('#tX').value,y:+$('#tY').value,locked:$('#tLocked').checked});$('#tableDlg').close();toast('השולחן נשמר')};
$('#deleteTable').onclick=async()=>{if(!confirm('למחוק את השולחן?'))return;let d=await api('/api/tables/'+currentTable,{method:'DELETE'});use(d);$('#tableDlg').close()};
function renderGroups(){let box=$('#groups');box.innerHTML='';[...P.groups].sort((a,b)=>a.priority-b.priority).forEach(g=>{let d=document.createElement('div');d.className='group-row';d.draggable=true;d.dataset.id=g.id;d.innerHTML=`<i class="dot" style="background:${color(g.id)}"></i><b>${g.priority}. ${esc(g.name)}</b><span class="grow muted">${P.people.filter(x=>x.group_id===g.id).length} אנשים</span><button class="btn mini danger">✕</button>`;d.querySelector('button').onclick=async()=>{let r=await api('/api/groups/'+g.id,{method:'DELETE'});use(r)};d.ondragstart=()=>d.classList.add('dragging');d.ondragend=async()=>{d.classList.remove('dragging');let order=$$('#groups .group-row').map(x=>x.dataset.id);let r=await api('/api/groups/reorder',json('POST',{order}));use(r)};box.appendChild(d)});box.ondragover=e=>{e.preventDefault();let x=box.querySelector('.dragging');if(!x)return;let after=[...box.querySelectorAll('.group-row:not(.dragging)')].find(a=>e.clientY<a.getBoundingClientRect().top+a.offsetHeight/2);after?box.insertBefore(x,after):box.appendChild(x)};$('#personGroup').innerHTML='<option value="">ללא קבוצה</option>'+[...P.groups].sort((a,b)=>a.priority-b.priority).map(g=>`<option value="${g.id}">${esc(g.name)}</option>`).join('')}
$('#addGroup').onclick=async()=>{let n=$('#groupName').value.trim();if(!n)return;let d=await api('/api/groups',json('POST',{name:n}));$('#groupName').value='';use(d)};
function renderPeople(){let q=$('#peopleSearch').value?.toLowerCase()||'',box=$('#people');box.innerHTML='';P.people.filter(x=>x.name.toLowerCase().includes(q)||(group(x.group_id)?.name||'').toLowerCase().includes(q)).forEach(x=>{let d=document.createElement('div');d.className='person-row';let t=table(x.table_id);d.innerHTML=`<i class="dot" style="background:${color(x.group_id)}"></i><b>${esc(x.name)}</b><span class="badge">${esc(group(x.group_id)?.name||'ללא קבוצה')}</span><span class="grow muted">${t?esc(t.name)+' · מקום '+(x.seat+1):'לא משובץ'}</span><label title="נעילה"><input type="checkbox" ${x.locked?'checked':''}> 🔒</label><button class="btn mini danger">✕</button>`;d.querySelector('input').onchange=async e=>use(await api('/api/people/'+x.id,json('PATCH',{locked:e.target.checked})));d.querySelector('button').onclick=async()=>{if(confirm('למחוק את '+x.name+'?'))use(await api('/api/people/'+x.id,{method:'DELETE'}))};box.appendChild(d)})}
$('#peopleSearch').oninput=renderPeople;
$('#addPerson').onclick=async()=>{let n=$('#personName').value.trim();if(!n)return;let d=await api('/api/people',json('POST',{name:n,group_id:$('#personGroup').value||null}));$('#personName').value='';use(d)};
$('#peopleFile').onchange=async e=>{let input=e.target,f=input.files[0];if(!f)return;toast('מייבא את רשימת המוזמנים...');try{let fd=new FormData();fd.append('file',f);let d=await api('/api/people/upload',{method:'POST',body:fd});S=d.state;P=d.project;V=d.violations||[];render();toast('נוספו '+d.added+' אנשים'+(d.created_groups?' · נוצרו '+d.created_groups+' קבוצות':'')+(d.skipped?' · דולגו '+d.skipped:''))}catch(err){toast('ייבוא CSV נכשל: '+err.message)}finally{input.value=''}};
function renderRules(){let needsTable=['at_table','not_table'].includes($('#ruleType').value);$('#ruleTable').style.display=needsTable?'':'none';$('#ruleTable').innerHTML=P.tables.map(t=>`<option value="${t.id}">${esc(t.name)}</option>`).join('');$('#rulePeople').innerHTML=P.people.map(x=>`<label class="check"><input type="checkbox" value="${x.id}"> ${esc(x.name)}</label>`).join('');let names=id=>esc(P.people.find(x=>x.id===id)?.name||'?');$('#rules').innerHTML=P.rules.map(r=>`<div class="rule-row"><b>${r.level==='hard'?'🔴':'🟠'} ${({together:'ביחד',separate:'בנפרד',at_table:'חייב בשולחן',not_table:'לא בשולחן'})[r.type]}</b><span class="grow muted">${r.people.map(names).join(', ')} ${r.table_id?'· '+esc(table(r.table_id)?.name||''):''}</span><button class="btn mini danger" data-r="${r.id}">✕</button></div>`).join('');$$('#rules [data-r]').forEach(b=>b.onclick=async()=>use(await api('/api/rules/'+b.dataset.r,{method:'DELETE'})))}
$('#ruleType').onchange=renderRules;
$('#addRule').onclick=async()=>{let people=$$('#rulePeople input:checked').map(x=>x.value);let type=$('#ruleType').value;if(!people.length)return toast('יש לבחור אנשים');if(['together','separate'].includes(type)&&people.length<2)return toast('לכלל הזה יש לבחור לפחות שני אנשים');let d=await api('/api/rules',json('POST',{type,level:$('#ruleLevel').value,people,table_id:['at_table','not_table'].includes(type)?$('#ruleTable').value:null}));use(d)};
function renderWaiting(){let q=$('#waitingSearch').value?.toLowerCase()||'',box=$('#waiting');box.innerHTML='';P.people.filter(x=>!x.table_id&&x.name.toLowerCase().includes(q)).forEach(x=>{let d=document.createElement('div');d.className='person-row';d.innerHTML=`<i class="dot" style="background:${color(x.group_id)}"></i><b>${esc(x.name)}</b><span class="grow muted">${esc(group(x.group_id)?.name||'')}</span>`;box.appendChild(d)});$('#alerts').innerHTML=V.map(v=>`<div class="alert ${v.level==='hard'?'hard':''}">${v.level==='hard'?'🔴':'🟠'} ${esc(v.message)}</div>`).join('')}
$('#waitingSearch').oninput=renderWaiting;
async function autoAssign(){let d=await api('/api/assign',{method:'POST'});S=d.state;P=d.project;V=d.violations||[];render();toast(d.unseated?.length?'השיבוץ הסתיים; '+d.unseated.length+' לא שובצו':'השיבוץ החכם הושלם')}
$('#autoAssign').onclick=autoAssign;$('#autoAssign2').onclick=autoAssign;
$('#resetAssign').onclick=async()=>{if(confirm('לנקות את כל השיבוצים שאינם נעולים?'))use(await api('/api/reset',{method:'POST'}))};
function renderStats(){let seated=P.people.filter(x=>x.table_id).length,cap=P.tables.reduce((a,t)=>a+t.capacity,0);$('#stats').textContent=`${P.people.length} אנשים · ${seated} משובצים · ${cap} מקומות · ${P.tables.length} פריטי ישיבה`}
$('#saveVersion').onclick=async()=>{let n=prompt('שם לגרסה השמורה:',`גרסה ${P.snapshots.length+1}`);if(n)use(await api('/api/snapshots',json('POST',{name:n})))};
function renderVersions(){$('#versions').innerHTML=P.snapshots.length?P.snapshots.slice().reverse().map(s=>`<div class="version-row"><b>${esc(s.name)}</b><span class="grow muted">${esc(s.created)}</span><button class="btn mini" data-s="${s.id}">שחזור</button></div>`).join(''):'<p class="muted">אין עדיין גרסאות שמורות.</p>';$$('#versions [data-s]').forEach(b=>b.onclick=async()=>{if(confirm('לשחזר את הגרסה?'))use(await api('/api/snapshots/'+b.dataset.s+'/restore',{method:'POST'}))})}
function renderProjects(){$('#projectSelect').innerHTML=S.projects.map(p=>`<option value="${p.id}" ${p.id===S.active_project?'selected':''}>${esc(p.name)}</option>`).join('')}
$('#activateProject').onclick=async()=>use(await api('/api/projects/'+$('#projectSelect').value+'/activate',{method:'POST'}));
$('#newProject').onclick=async()=>{let n=$('#newProjectName').value.trim();if(n)use(await api('/api/projects',json('POST',{name:n})))};
$('#backupFile').onchange=async e=>{let f=e.target.files[0];if(!f)return;let fd=new FormData();fd.append('file',f);use(await api('/api/backup',{method:'POST',body:fd}));e.target.value=''};
$('#themeBtn').onclick=()=>{document.body.classList.toggle('dark');localStorage.theme=document.body.classList.contains('dark')?'dark':'light'};
if(localStorage.theme==='dark')document.body.classList.add('dark');
function use(d){S=d.state;P=d.project;V=d.violations||[];render()}

/* ===== Hall Builder V12 — same drafting engine as room assignment ===== */
const GRID_COLS=26,GRID_ROWS=16;let CELL=clampGridPx(localStorage.getItem('hallBuilderGridPx')||30);
function clampGridPx(v){return Math.max(16,Math.min(60,Math.round(+v||30)))}
const clampI=(v,lo,hi)=>Math.max(lo,Math.min(hi,Math.round(+v||0)));
let builderTool='move',builderLayout='round_tables',builderSelected=new Set(),builderUndo=[],builderRedo=[];
let down=null,anchor=null;
const rectCells=(a,b)=>{let out=[];for(let y=Math.min(a.y,b.y);y<=Math.max(a.y,b.y);y++)for(let x=Math.min(a.x,b.x);x<=Math.max(a.x,b.x);x++)out.push({x,y});return out};
function gridRect(t){if(t.gx!=null)return{gx:+t.gx,gy:+t.gy,gw:+(t.gw||1),gh:+(t.gh||1)};let gw=Math.max(1,Math.round((+t.w||100/GRID_COLS)/100*GRID_COLS)),gh=Math.max(1,Math.round((+t.h||100/GRID_ROWS)/100*GRID_ROWS));return{gx:clampI((+t.x/100)*GRID_COLS-gw/2,0,GRID_COLS-gw),gy:clampI((+t.y/100)*GRID_ROWS-gh/2,0,GRID_ROWS-gh),gw,gh}}
function cellSquares(r){let a=[];for(let y=r.gy;y<r.gy+r.gh;y++)for(let x=r.gx;x<r.gx+r.gw;x++)a.push({x,y});return a}
function cellsClash(a,b){return !(a.gx+a.gw<=b.gx||b.gx+b.gw<=a.gx||a.gy+a.gh<=b.gy||b.gy+b.gh<=a.gy)}
function gridStyle(el,r){el.style.right=(r.gx*CELL+1)+'px';el.style.top=(r.gy*CELL+1)+'px';el.style.width=(r.gw*CELL-2)+'px';el.style.height=(r.gh*CELL-2)+'px';el.style.left='auto'}
function applyGridDisplaySize(v,save=true){CELL=clampGridPx(v);if(save)localStorage.setItem('hallBuilderGridPx',CELL);let canvas=$('#builderCanvas');if(canvas){canvas.style.setProperty('--grid-cell',CELL+'px');canvas.style.width=(GRID_COLS*CELL)+'px';canvas.style.height=(GRID_ROWS*CELL)+'px';canvas.style.minWidth=(GRID_COLS*CELL)+'px';canvas.style.minHeight=(GRID_ROWS*CELL)+'px'}let input=$('#gridCellSize'),out=$('#gridCellSizeValue');if(input)input.value=CELL;if(out)out.value=out.textContent=CELL+'px';$$('[data-grid-px]').forEach(b=>b.classList.toggle('active',+b.dataset.gridPx===CELL));if(P)renderBuilder()}
function cellXY(e){let r=$('#builderCanvas').getBoundingClientRect();return{x:clampI(Math.floor((r.right-e.clientX)/CELL),0,GRID_COLS-1),y:clampI(Math.floor((e.clientY-r.top)/CELL),0,GRID_ROWS-1)}}
function gridArea(a,b){return{gx:Math.min(a.x,b.x),gy:Math.min(a.y,b.y),gw:Math.abs(a.x-b.x)+1,gh:Math.abs(a.y-b.y)+1}}
function builderSnapshot(){return JSON.stringify({tables:structuredClone(P.tables||[]),hall_objects:structuredClone(P.hall_objects||[]),assignments:(P.people||[]).map(x=>({id:x.id,table_id:x.table_id,seat:x.seat}))})}
function remember(){builderUndo.push(builderSnapshot());if(builderUndo.length>50)builderUndo.shift();builderRedo=[]}
async function restore(raw){use(await api('/api/layout/restore',json('POST',JSON.parse(raw))))}
const IDLE_HINT='📐 גוררים מלבן — או לוחצים על פינה אחת ואז על הפינה הנגדית.';
function setHint(t){let n=$('#builderHintText');if(n)n.textContent=t}
function bandShow(a,b,bad=false){let el=$('#draftBand'),r=gridArea(a,b);el.style.display='block';gridStyle(el,r);el.classList.toggle('bad',bad);el.dataset.kind=builderTool}
function bandHide(){let el=$('#draftBand');if(el)el.style.display='none'}
function dropAnchor(){anchor=null;bandHide();setHint(IDLE_HINT)}
function setTool(tool){dropAnchor();down=null;builderTool=tool;$$('[data-tool]').forEach(x=>x.classList.toggle('selected',x.dataset.tool===tool));$('#builderCanvas').className='hall builder-canvas room-grid tool-'+(tool==='move'?'move':tool==='erase'?'erase':'paint');$('#builderCanvas').dataset.tool=tool;$('#benchOptions').style.display=tool==='bench'?'block':'none';renderBuilder()}
function builderSetLayout(layout){builderLayout=layout;$$('.layout-card').forEach(x=>x.classList.toggle('selected',x.dataset.layout===layout));$('#genCapWrap').style.display=layout==='rows'?'none':''}
function allItems(){return [...(P.tables||[]).map(x=>({type:'table',id:x.id,r:gridRect(x),obj:x})),...(P.hall_objects||[]).map(x=>({type:'object',id:x.id,r:gridRect(x),obj:x}))]}
function itemAt(p){let all=allItems();for(let i=all.length-1;i>=0;i--){let r=all[i].r;if(p.x>=r.gx&&p.x<r.gx+r.gw&&p.y>=r.gy&&p.y<r.gy+r.gh)return all[i]}return null}
function selectionInfo(){let e=$('#selectionInfo');if(e)e.textContent=builderSelected.size?builderSelected.size+' פריטים נבחרו':'לא נבחרו פריטים'}
function icon(t){if(t.bench_id)return'▥';if(t.kind==='seat')return'♙';return t.shape==='square'?'▣':'●'}
function iconClass(t){if(t.bench_id)return'bench';if(t.kind==='seat')return'chair';return t.shape==='square'?'square':'round'}
function tableSeatDots(t){if(t.kind==='seat')return'';return '<span class="table-seat-ring"></span>'}
async function applyRect(a,b){
 let area=gridArea(a,b);
 if(builderTool==='erase'){let hits=allItems().filter(q=>cellsClash(q.r,area));if(!hits.length)return;remember();for(const q of hits){if(q.type==='table')await api('/api/tables/'+q.id,{method:'DELETE'});else await api('/api/hall-objects/'+q.id,{method:'DELETE'})}await load();return}
 remember();let d=await api('/api/layout/draw',json('POST',{kind:builderTool,...area,capacity:+$('#genCapacity').value||4}));S=d.state;P=d.project;V=d.violations||[];builderSelected=new Set((d.created||[]).filter(id=>P.tables.some(t=>t.id===id)));render()
}
function renderBuilder(){let canvas=$('#builderCanvas');if(!canvas||!P)return;P.hall_objects??=[];P.tables??=[];builderSelected=new Set([...builderSelected].filter(id=>P.tables.some(t=>t.id===id)));$('#builderHallName').textContent=P.hall?.name||'האולם';$('#builderCount').textContent=P.tables.length+' פריטי ישיבה · '+P.tables.reduce((a,t)=>a+(+t.capacity||0),0)+' מקומות';canvas.querySelectorAll('.builder-item,.hall-object').forEach(n=>n.remove());let help=canvas.querySelector('.empty-help');if(help)help.style.display=P.tables.length+P.hall_objects.length?'none':'flex';
 P.hall_objects.forEach(o=>{let el=document.createElement('div');el.className='hall-object object-'+(o.kind||'zone');el.dataset.oid=o.id;gridStyle(el,gridRect(o));el.innerHTML='<span>'+esc(o.name||'אובייקט')+'</span>';el.style.pointerEvents='none';canvas.appendChild(el)});
 P.tables.forEach(t=>{let el=document.createElement('div');el.className='builder-item grid-item kind-'+iconClass(t)+(builderSelected.has(t.id)?' selected-item':'');el.dataset.bid=t.id;gridStyle(el,gridRect(t));el.innerHTML='<span class="item-symbol">'+icon(t)+'</span>'+tableSeatDots(t)+'<span class="item-cap">'+(t.kind==='seat'?'':t.capacity)+'</span>';el.style.pointerEvents='none';canvas.appendChild(el)});selectionInfo()
}
async function moveItem(item,nr){
 remember();
 if(item.type==='object'){use(await api('/api/hall-objects/'+item.id,json('PATCH',nr)));return}
 let t=item.obj,dx=nr.gx-item.r.gx,dy=nr.gy-item.r.gy;
 builderSelected=new Set([t.id]);use(await api('/api/tables/bulk',json('POST',{ids:[t.id],action:'move',grid_dx:dx,grid_dy:dy,dx:0,dy:0})))
}
function wireBuilderGrid(){
 let grid=$('#builderCanvas');if(!grid)return;
 grid.onpointerdown=e=>{
   if(e.button!==0)return;let p=cellXY(e);try{grid.setPointerCapture(e.pointerId)}catch{}e.preventDefault();
   if(anchor&&builderTool!=='move'){let a=anchor;dropAnchor();applyRect(a,p);down={mode:'done'};return}
   if(builderTool==='move'){
     let hit=itemAt(p);builderSelected=hit&&hit.type==='table'?new Set([hit.id]):new Set();renderBuilder();
     down={mode:hit?'drag':'none',item:hit,from:p,off:hit?{x:p.x-hit.r.gx,y:p.y-hit.r.gy}:{x:0,y:0},last:null};return
   }
   down={mode:'rect',start:p,cur:p};bandShow(p,p,builderTool==='erase')
 };
 grid.onpointermove=e=>{
   if(!down){if(anchor)bandShow(anchor,cellXY(e),builderTool==='erase');return}
   let p=cellXY(e);
   if(down.mode==='rect'){down.cur=p;bandShow(down.start,p,builderTool==='erase');return}
   if(down.mode==='drag'&&down.item){
     let r=down.item.r,nr={...r,gx:clampI(p.x-down.off.x,0,GRID_COLS-r.gw),gy:clampI(p.y-down.off.y,0,GRID_ROWS-r.gh)};
     if(allItems().some(q=>q.id!==down.item.id&&cellsClash(q.r,nr)))return;
     down.last=nr;let node=down.item.type==='table'?grid.querySelector('[data-bid="'+down.item.id+'"]'):grid.querySelector('[data-oid="'+down.item.id+'"]');if(node)gridStyle(node,nr)
   }
 };
 const up=e=>{
   let d=down;down=null;try{grid.releasePointerCapture(e.pointerId)}catch{}
   if(!d||d.mode==='done'){bandHide();return}
   if(d.mode==='drag'){bandHide();if(d.item&&d.last&&(d.last.gx!==d.item.r.gx||d.last.gy!==d.item.r.gy))moveItem(d.item,d.last);else renderBuilder();return}
   if(d.mode!=='rect'){bandHide();return}
   if(d.start.x===d.cur.x&&d.start.y===d.cur.y){anchor=d.start;bandShow(anchor,anchor,builderTool==='erase');setHint(builderTool==='erase'?'🧽 עכשיו לחצו על הפינה הנגדית של המלבן למחיקה — או Esc לביטול.':'📐 פינה ראשונה נבחרה. עכשיו לחצו על הפינה הנגדית — או Esc לביטול.');return}
   bandHide();applyRect(d.start,d.cur)
 };
 grid.onpointerup=up;grid.onpointercancel=up
}
async function bulk(action,extra={}){if(!builderSelected.size)return toast('יש לבחור פריט אחד לפחות');remember();use(await api('/api/tables/bulk',json('POST',{ids:[...builderSelected],action,...extra})))}
function initHallBuilder(){
 applyGridDisplaySize(CELL,false);
 let gi=$('#gridCellSize');if(gi){gi.value=CELL;gi.oninput=()=>applyGridDisplaySize(gi.value);gi.onchange=()=>applyGridDisplaySize(gi.value)}
 $$('[data-grid-px]').forEach(b=>b.onclick=()=>applyGridDisplaySize(b.dataset.gridPx));$$('.layout-card').forEach(x=>x.onclick=()=>builderSetLayout(x.dataset.layout));$$('[data-tool]').forEach(x=>x.onclick=()=>setTool(x.dataset.tool));
 $('#generateLayout').onclick=async()=>{if((P.tables.length+P.hall_objects.length)&&!confirm('להחליף את המבנה הקיים?'))return;remember();use(await api('/api/layout/generate',json('POST',{mode:builderLayout==='square_tables'?'square':builderLayout==='rows'?'rows':'round',rows:+$('#genRows').value||5,cols:+$('#genCols').value||6,capacity:+$('#genCapacity').value||4})))};
 $('#clearLayout').onclick=async()=>{if((P.tables.length+P.hall_objects.length)&&!confirm('לנקות את כל המפה?'))return;remember();use(await api('/api/layout/clear',{method:'POST'}))};
 $('#selectAll').onclick=()=>{builderSelected=new Set(P.tables.map(t=>t.id));renderBuilder()};$('#duplicateSelected').onclick=()=>bulk('duplicate');$('#rotateSelected').onclick=()=>bulk('rotate',{degrees:90});$('#deleteSelected').onclick=()=>builderSelected.size&&confirm('למחוק את הפריטים שנבחרו?')&&bulk('delete');$$('[data-align]').forEach(x=>x.onclick=()=>bulk('align',{mode:x.dataset.align}));$('#distX').onclick=()=>bulk('distribute',{axis:'x'});$('#distY').onclick=()=>bulk('distribute',{axis:'y'});
 $('#undoBuilder').onclick=async()=>{if(!builderUndo.length)return toast('אין פעולה לביטול');builderRedo.push(builderSnapshot());await restore(builderUndo.pop())};$('#redoBuilder').onclick=async()=>{if(!builderRedo.length)return toast('אין פעולה להחזרה');builderUndo.push(builderSnapshot());await restore(builderRedo.pop())};
 wireBuilderGrid();document.addEventListener('keydown',e=>{if($('.view.active')?.id!=='view-builder')return;let k=e.key.toLowerCase();if(e.key==='Escape')dropAnchor();if(e.key==='Delete'&&builderSelected.size){e.preventDefault();$('#deleteSelected').click()}if((e.ctrlKey||e.metaKey)&&k==='z'){e.preventDefault();$('#undoBuilder').click()}if((e.ctrlKey||e.metaKey)&&k==='y'){e.preventDefault();$('#redoBuilder').click()}});setTool('move')
}
initHallBuilder();
load();

$('#tCustomRank')?.addEventListener('change',e=>{$('#tRank').disabled=!e.target.checked});
$('#projectSettingsBtn')?.addEventListener('click',()=>{let s=P.settings||{};$('#prefMode').value=s.seat_preference||'front_center';$('#frontWeight').value=s.front_weight??1;$('#centerWeight').value=s.center_weight??.35;$('#showQuality').checked=!!s.show_quality;$('#assignmentZoom').value=String(s.assignment_zoom??1);$('#projectSettingsDlg').showModal()});
$('#saveProjectSettings')?.addEventListener('click',async()=>{let d=await api('/api/project/settings',json('POST',{seat_preference:$('#prefMode').value,front_weight:Number($('#frontWeight').value),center_weight:Number($('#centerWeight').value),show_quality:$('#showQuality').checked,assignment_zoom:Number($('#assignmentZoom').value)}));use(d);$('#projectSettingsDlg').close();toast('הגדרות הפרויקט נשמרו')});

function effectiveRankJS(t){
 if(!t)return 10;
 if(t.custom_rank)return Number(t.rank??10);
 let s=P?.settings||{},mode=s.seat_preference||'front_center',fw=Number(s.front_weight??1),cw=Number(s.center_weight??.35);
 let front=Math.max(0,Math.min(100,Number(t.y??50)))/10;
 let center=Math.abs(Math.max(0,Math.min(100,Number(t.x??50)))-50)/5;
 if(mode==='front_only')return front;
 if(mode==='center_only')return center;
 if(mode==='manual')return Number(t.rank??10);
 return front*fw+center*cw;
}
function seatIconClass(t){if(t?.bench_id)return'bench';if(t?.kind==='seat'||t?.shape==='chair')return'chair';return t?.shape==='square'?'square':'round'}
function seatIcon(t){if(t?.bench_id)return'▥';if(t?.kind==='seat'||t?.shape==='chair')return'♙';return t?.shape==='square'?'▣':'●'}
let assignmentZoom=1,qualityVisible=false;
function qualityClass(t){let r=effectiveRankJS(t);return r<=3?'quality-best':r<=6?'quality-good':r<=9?'quality-mid':'quality-low'}
function renderAssignmentPro(){
 let h=$('#assignCanvas');if(!h||!P)return;h.innerHTML='';commonMapSetup(h);P.hall_objects??=[];
 P.hall_objects.forEach(o=>{let z=document.createElement('div');z.className='hall-object object-'+(o.kind||'zone');commonMapStyle(z,gridRect(o));z.innerHTML='<span>'+esc(o.name||'')+'</span>';h.appendChild(z)});
 P.tables.forEach(t=>{let occ=P.people.filter(x=>x.table_id===t.id),d=document.createElement('div');d.className='assign-slot unified-assign-slot '+seatIconClass(t)+(qualityVisible?' '+qualityClass(t):'')+(t.disabled?' disabled-seat':'');commonMapStyle(d,gridRect(t));let names=occ.map(x=>esc(x.name)).join(' · ');d.innerHTML='<div class="assign-icon '+seatIconClass(t)+'">'+seatIcon(t)+'</div><div class="assign-name">'+esc(t.name)+'</div><div class="assign-occupants">'+(names||'פנוי')+'</div><div class="assign-meta">'+(t.zone?'📍 '+esc(t.zone)+' · ':'')+'איכות '+effectiveRankJS(t).toFixed(1)+'</div>';d.title=(t.tags||[]).join(', ');d.onclick=()=>openTable(t.id);occ.length&&d.addEventListener('dblclick',async()=>{let x=occ[0],z=await api('/api/explain/'+x.id);$('#explainTitle').textContent='למה '+z.title+' שובץ כאן?';$('#explainBody').innerHTML=z.lines.map(a=>'<div class="explain-line">'+esc(a)+'</div>').join('');$('#explainDlg').showModal()});h.appendChild(d)});
 assignmentZoom=Number(P.settings?.assignment_zoom??1);applyAssignZoom()
}
function applyAssignZoom(){let h=$('#assignCanvas');if(!h)return;h.style.transform='scale('+assignmentZoom+')';h.style.transformOrigin='top right';$('#zoomLabel').textContent=Math.round(assignmentZoom*100)+'%'}
$('#zoomIn')?.addEventListener('click',()=>{assignmentZoom=Math.min(2,assignmentZoom+.1);applyAssignZoom()});
$('#zoomOut')?.addEventListener('click',()=>{assignmentZoom=Math.max(.6,assignmentZoom-.1);applyAssignZoom()});
$('#qualityMapBtn')?.addEventListener('click',()=>{qualityVisible=!qualityVisible;renderAssignmentPro();$('#qualityMapBtn').classList.toggle('primary',qualityVisible)});
$('#printMap')?.addEventListener('click',()=>window.print());
$('#validateProject')?.addEventListener('click',async()=>{let d=await api('/api/validate'),box=$('#validationResults');box.innerHTML='<div class="validation-summary">'+d.people+' אנשים · '+d.capacity+' מקומות · '+d.unassigned+' ממתינים</div>'+(d.issues.length?d.issues.map(x=>'<div class="alert '+esc(x.level)+'">'+esc(x.message)+'</div>').join(''):'<div class="ok-card">✓ לא נמצאו בעיות במבנה הפרויקט</div>');$('#validateDlg').showModal()});
function openPersonPrefs(id){let x=P.people.find(p=>p.id===id);if(!x)return;$('#editPersonId').value=id;$('#personPrefZone').value=x.preferred_zone||'';$('#personPrefTags').value=(x.preferred_tags||[]).join(', ');$('#personSeatPref').value=x.seat_preference||'project';$('#personNote').value=x.note||'';$('#personDlg').showModal()}
$('#savePersonPrefs')?.addEventListener('click',async()=>{let id=$('#editPersonId').value;use(await api('/api/people/'+id,json('PATCH',{preferred_zone:$('#personPrefZone').value,preferred_tags:$('#personPrefTags').value.split(',').map(x=>x.trim()).filter(Boolean),seat_preference:$('#personSeatPref').value,note:$('#personNote').value})));$('#personDlg').close();toast('ההעדפות נשמרו')});
