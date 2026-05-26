'use strict';

/* ============ ШАБЛОНЫ АГЕНТОВ + ПРОМТЫ ============ */
const TEMPLATES = [
  { role:'scout',  name:'Скаут',        title:'Редактор-аквизитор', emoji:'🔎',
    prompt:'Ты — литературный скаут. Оцени потенциал книги под рынок и аудиторию: вердикт (в производство / доработать / отклонить), главный крючок, целевую полку, риски. Без воды.' },
  { role:'dev',    name:'Структурный редактор', title:'Developmental editor', emoji:'🧭',
    prompt:'Ты — структурный редактор. Улучши композицию: сюжет, арки персонажей, темп, логику. Дай конкретные правки списком и перепиши проблемные места.' },
  { role:'writer', name:'Райтер',       title:'Автор / гострайтер', emoji:'✍️',
    prompt:'Ты — писатель-прозаик. Пиши живой образный текст строго по брифу, жанру и «Библии книги», держи единый голос. Выдавай готовую прозу, не план.' },
  { role:'line',   name:'Литред',       title:'Литературный редактор', emoji:'🔧',
    prompt:'Ты — литературный редактор. Убирай воду и штампы, усиливай ритм и образность, сохраняй авторский голос. Возвращай отредактированный текст.' },
  { role:'proof',  name:'Корректор',    title:'Proofreader', emoji:'🔍',
    prompt:'Ты — корректор. Исправь орфографию, пунктуацию, грамматику, единообразие оформления. Верни вычитанный текст и список ключевых правок.' },
  { role:'continuity', name:'Континуитет', title:'Хранитель канона', emoji:'🧩',
    prompt:'Ты — агент-континуитета. Сверь текст с «Библией книги» (персонажи, мир, таймлайн) и материалами коллег. Найди противоречия в именах, деталях, хронологии и логике. Верни список расхождений и исправленный фрагмент.' },
  { role:'factcheck', name:'Фактчек',   title:'Проверка фактов', emoji:'✅',
    prompt:'Ты — фактчекер. Проверь утверждения на достоверность, пометь сомнительные места и предложи корректные формулировки. Для нон-фикшн особенно строго.' },
  { role:'art',    name:'Арт-директор', title:'Дизайнер обложки', emoji:'🎨',
    prompt:'Ты — арт-директор. Составь бриф обложки под жанр и аудиторию: концепция, композиция, палитра, типографика, настроение. Дай 2–3 варианта.' },
  { role:'layout', name:'Верстальщик',  title:'Вёрстка / EPUB', emoji:'📐',
    prompt:'Ты — верстальщик. Опиши параметры вёрстки для EPUB и печати: форматы, шрифты, отступы, оглавление, колонтитулы.' },
  { role:'meta',   name:'Метаданные',   title:'Distribution', emoji:'🏷️',
    prompt:'Ты — специалист по метаданным. Подготовь для площадок (KDP и др.): 2–3 точные категории, 7 ключевых фраз (long-tail, языком читателя — жанр и тропы, не «литературный» язык автора), аннотацию до 200 знаков, рекомендованную цену.' },
  { role:'mkt',    name:'Маркетолог',   title:'SMM / промо', emoji:'📣',
    prompt:'Ты — книжный маркетолог. Спланируй запуск как систему: ниша, идея серии, план первых 7 дней и 3 готовых поста (тизер / цитата / релиз) под целевую аудиторию.' },
];

const PRICES = { // $ за 1M токенов (вход/выход), грубо для оценки
  'deepseek-chat':{in:0.14,out:0.28}, 'deepseek-reasoner':{in:0.55,out:2.19},
  'gpt-4o-mini':{in:0.15,out:0.60}, 'gpt-4o':{in:2.5,out:10},
};
const KDP_CHECKLIST =
`## Чек-лист публикации (KDP и др.)
- [ ] Указать использование ИИ при загрузке (обязательно, иначе бан)
- [ ] Не более 3 новых книг в день (антифлуд)
- [ ] 2–3 точные категории (не слишком широкие)
- [ ] 7 ключевых фраз языком читателя (жанр/тропы, long-tail)
- [ ] Аннотация до 200 знаков, цепляющая
- [ ] Вычитка корректором пройдена
- [ ] Континуитет проверен (имена, таймлайн, факты)
- [ ] Обложка под жанр и аудиторию
- [ ] План запуска и посты готовы`;

/* ============ СОСТОЯНИЕ ============ */
const KEY='izd_studio_v3';
const uid=()=>Date.now().toString(36)+Math.random().toString(36).slice(2,6);
function freshNode(t,x,y){ return { id:uid(), name:t.name, role:t.title, emoji:t.emoji, prompt:t.prompt, promptHistory:[],
  x,y, useGlobal:true, baseURL:'',apiKey:'',model:'',temperature:1.0, requireApproval:false, approved:false,
  output:'', summary:'', status:'idle', error:'', cacheHash:'', tokensIn:0, tokensOut:0, ms:0 }; }
function defaultState(){
  const nodes=TEMPLATES.filter(t=>!['continuity','factcheck'].includes(t.role)).map((t,i)=>freshNode(t,60+(i%3)*250,40+Math.floor(i/3)*180));
  const edges=[]; for(let i=0;i<nodes.length-1;i++) edges.push({id:uid(),from:nodes[i].id,to:nodes[i+1].id});
  return { project:{title:'',genre:'',audience:'',brief:'',mode:'write',input:'',disclosure:'Текст подготовлен с использованием ИИ'},
    bible:[], log:[],
    global:{ baseURL:'https://api.deepseek.com', apiKey:'', model:'deepseek-chat', temperature:1.0,
      maxContextChars:8000, maxRetries:2, costCapUSD:0, proxyToken:'' },
    nodes, edges };
}
let state=load();
function load(){ try{ const s=JSON.parse(localStorage.getItem(KEY)); return s&&s.nodes? Object.assign(defaultState(),s) : defaultState(); }catch{ return defaultState(); } }
function save(){ localStorage.setItem(KEY, JSON.stringify(state)); }

const NW=212, PORT_Y=23;
const node=id=>state.nodes.find(n=>n.id===id);
const $=s=>document.querySelector(s);
const esc=s=>(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const cfg=n=> n.useGlobal? state.global : { baseURL:n.baseURL||state.global.baseURL, apiKey:n.apiKey||state.global.apiKey,
  model:n.model||state.global.model, temperature:typeof n.temperature==='number'?n.temperature:state.global.temperature };
const hasKey=()=> state.nodes.some(n=>cfg(n).apiKey) || !!state.global.apiKey;
const wait=ms=>new Promise(r=>setTimeout(r,ms));

/* ============ КОНТЕКСТ + БИБЛИЯ ============ */
function bibleFor(text){
  const low=(text||'').toLowerCase();
  return state.bible.filter(b=>{ const keys=(b.keys||'').split(',').map(s=>s.trim().toLowerCase()).filter(Boolean);
    return !keys.length || keys.some(k=>low.includes(k)); }).map(b=>`• ${b.keys||'канон'}: ${b.text}`).join('\n');
}
function buildMessages(n){
  const pr=state.project;
  const preds=state.edges.filter(e=>e.to===n.id).map(e=>node(e.from)).filter(Boolean);
  let prior=preds.filter(p=>p.output).map(p=>`— ${p.name}:\n${p.summary||p.output}`).join('\n\n');
  const budget=state.global.maxContextChars||8000;
  if(prior.length>budget) prior=prior.slice(0,budget)+'\n…[обрезано по бюджету контекста]';
  const scan=[pr.title,pr.genre,pr.brief,pr.input,prior].join(' ');
  const bible=bibleFor(scan);
  let user=`Книга: «${pr.title||'без названия'}»\nЖанр: ${pr.genre||'не задан'}\nАудитория: ${pr.audience||'не задана'}\n`+
    `Режим: ${pr.mode==='write'?'пишем с нуля':'редактируем готовый текст'}\n`+(pr.brief?`Бриф: ${pr.brief}\n`:'');
  if(bible) user+=`\nБиблия книги (канон, соблюдать строго):\n${bible}\n`;
  if(pr.mode==='edit'&&pr.input&&preds.length===0) user+=`\nИсходный текст:\n${pr.input}\n`;
  if(prior) user+=`\nМатериалы от предыдущих агентов:\n${prior}\n`;
  user+=`\nВыполни свою роль и выдай конкретный результат.`;
  return [ {role:'system',content:n.prompt}, {role:'user',content:user} ];
}
const tokEst=s=>Math.max(1,Math.round((s||'').length/4));
const nodeCost=n=>{ const p=PRICES[cfg(n).model]||{in:0.14,out:0.28}; return (n.tokensIn||0)/1e6*p.in+(n.tokensOut||0)/1e6*p.out; };
const projectCost=()=>state.nodes.reduce((s,n)=>s+nodeCost(n),0);
const money=v=>'$'+v.toFixed(v<1?4:2);

/* ============ ЖУРНАЛ ============ */
function logRow(node,status,msg,extra={}){ state.log.unshift({t:Date.now(),node,status,msg,...extra}); if(state.log.length>200) state.log.pop(); }

/* ============ РЕНДЕР ============ */
const nodesEl=$('#nodes'), edgesEl=$('#edges');
function render(){
  $('#proj-title').value=state.project.title; $('#proj-genre').value=state.project.genre;
  $('#proj-aud').value=state.project.audience; $('#proj-brief').value=state.project.brief; $('#proj-mode').value=state.project.mode;
  const ks=$('#api-state'); ks.textContent=hasKey()?'● ключ задан':'● ключ не задан'; ks.classList.toggle('ok',hasKey());
  $('#cost-state').textContent='Σ '+money(projectCost());
  $('#input-btn').style.display=state.project.mode==='edit'?'':'none';
  const paused=isPaused();
  const rb=$('#run-btn'); rb.textContent=paused?'▶ Продолжить':'▶ Запустить конвейер';
  $('#canvas-hint').textContent='Тяни блок за шапку • соединяй кружки (выход→вход) • клик по связи — удалить';
  renderNodes(); renderEdges();
}
function renderNodes(){
  nodesEl.innerHTML=state.nodes.map(n=>{
    const out=n.error?`⚠ ${esc(n.error)}`:(n.output?esc(n.output):'нет результата');
    const meta=(n.tokensIn||n.tokensOut)?`<span>${(n.tokensIn+n.tokensOut)} ток.</span><span>${money(nodeCost(n))}</span>${n.ms?`<span>${(n.ms/1000).toFixed(1)}с</span>`:''}`:'';
    const appr=n.status==='review'?`<div class="node-foot"><button class="btn ok sm" data-action="approve" data-id="${n.id}">✅ Принять</button><button class="btn ghost sm" data-action="open-node" data-id="${n.id}">✍ Правка</button></div>`:
      `<div class="node-foot"><button class="btn ghost sm" data-action="open-node" data-id="${n.id}">⚙ Настроить</button><button class="btn ghost sm" data-action="run-node" data-id="${n.id}">▶ Прогнать</button></div>`;
    return `<div class="node ${n.status}" data-node="${n.id}" style="left:${n.x}px;top:${n.y}px">
      <div class="port in" data-port="in" data-id="${n.id}"></div>
      <div class="port out" data-port="out" data-id="${n.id}"></div>
      <div class="node-head" data-drag="${n.id}">
        <div class="node-emoji">${n.emoji}</div>
        <div><div class="node-name">${esc(n.name)}${n.requireApproval?' 🔒':''}</div><div class="node-role">${esc(n.role)}</div></div>
        <div class="node-status"></div>
      </div>
      <div class="node-body ${n.output||n.error?'':'empty'}" id="body-${n.id}">${out}</div>
      ${meta?`<div class="node-meta">${meta}</div>`:''}
      ${appr}
    </div>`;
  }).join('');
}
function portPos(id,side){ const n=node(id); return {x:n.x+(side==='out'?NW:0), y:n.y+PORT_Y+7}; }
function edgePath(a,b){ const dx=Math.max(40,Math.abs(b.x-a.x)*0.5); return `M ${a.x} ${a.y} C ${a.x+dx} ${a.y}, ${b.x-dx} ${b.y}, ${b.x} ${b.y}`; }
function renderEdges(){
  edgesEl.innerHTML=state.edges.map(e=>{ if(!node(e.from)||!node(e.to)) return '';
    const d=edgePath(portPos(e.from,'out'),portPos(e.to,'in'));
    const flow=node(e.from).status==='running'||node(e.to).status==='running';
    return `<path class="edge ${flow?'flow':''}" d="${d}"></path><path class="edge hit" d="${d}" data-edge="${e.id}"></path>`; }).join('');
}

/* ============ DRAG + СВЯЗИ ============ */
const canvas=$('#canvas'); let drag=null, wire=null;
nodesEl.addEventListener('mousedown',e=>{
  const p=e.target.closest('.port.out'); if(p){ wire={from:p.dataset.id}; e.stopPropagation(); e.preventDefault(); return; }
  const h=e.target.closest('[data-drag]'); if(!h) return;
  const n=node(h.dataset.drag); const pt=canvasPoint(e); drag={id:n.id,dx:pt.x-n.x,dy:pt.y-n.y}; e.preventDefault();
});
function canvasPoint(e){ const r=canvas.getBoundingClientRect(); return {x:e.clientX-r.left+canvas.scrollLeft, y:e.clientY-r.top+canvas.scrollTop}; }
window.addEventListener('mousemove',e=>{
  if(drag){ const n=node(drag.id); const pt=canvasPoint(e); n.x=Math.max(0,pt.x-drag.dx); n.y=Math.max(0,pt.y-drag.dy);
    const el=nodesEl.querySelector(`[data-node="${n.id}"]`); if(el){ el.style.left=n.x+'px'; el.style.top=n.y+'px'; } renderEdges(); }
  else if(wire){ const a=portPos(wire.from,'out'),b=canvasPoint(e); let t=edgesEl.querySelector('.edge-temp');
    if(!t){ t=document.createElementNS('http://www.w3.org/2000/svg','path'); t.setAttribute('class','edge-temp'); edgesEl.appendChild(t); } t.setAttribute('d',edgePath(a,b)); }
});
window.addEventListener('mouseup',e=>{
  if(drag){ drag=null; save(); }
  if(wire){ const tgt=document.elementFromPoint(e.clientX,e.clientY); const ip=tgt&&tgt.closest&&tgt.closest('.port.in');
    if(ip) addEdge(wire.from,ip.dataset.id); wire=null; const t=edgesEl.querySelector('.edge-temp'); if(t)t.remove(); renderEdges(); }
});
function addEdge(from,to){ if(from===to) return toast('Нельзя соединить агента с собой','err');
  if(state.edges.some(x=>x.from===from&&x.to===to)) return;
  if(wouldCycle(from,to)) return toast('Связь создаёт петлю — отклонено','err');
  state.edges.push({id:uid(),from,to}); save(); renderEdges(); }
function wouldCycle(from,to){ const seen=new Set(),st=[to]; while(st.length){ const c=st.pop(); if(c===from) return true; if(seen.has(c)) continue; seen.add(c); state.edges.filter(e=>e.from===c).forEach(e=>st.push(e.to)); } return false; }
edgesEl.addEventListener('click',e=>{ const p=e.target.closest('[data-edge]'); if(!p) return; state.edges=state.edges.filter(x=>x.id!==p.dataset.edge); save(); renderEdges(); toast('Связь удалена'); });

/* ============ ГЕНЕРАЦИЯ ============ */
async function runNode(id){
  const n=node(id); const c=cfg(n);
  if(!c.apiKey){ n.status='error'; n.error='не задан API-ключ'; logRow(n.name,'error','нет ключа'); save(); renderNodes(); openSettings(); return false; }
  const msgs=buildMessages(n); const hash=JSON.stringify([msgs,c.model,c.temperature]);
  if(n.cacheHash===hash && n.output){ n.status='done'; n.error=''; logRow(n.name,'cache','из кэша (без вызова)'); save(); renderNodes(); renderEdges(); return true; }
  n.status='running'; n.output=''; n.error=''; save(); renderNodes(); renderEdges();
  const maxR=state.global.maxRetries|0, t0=performance.now();
  for(let attempt=0; attempt<=maxR; attempt++){
    let acc='';
    try{
      const res=await fetch('/api/generate',{ method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({ baseURL:c.baseURL, apiKey:c.apiKey, model:c.model, temperature:c.temperature, proxyToken:state.global.proxyToken, messages:msgs }) });
      if(!res.ok){ const t=await res.text(); const retri=res.status===429||res.status>=500;
        if(retri&&attempt<maxR){ logRow(n.name,'retry',`HTTP ${res.status}, повтор #${attempt+1}`); await wait(1000*2**attempt); continue; }
        throw new Error('HTTP '+res.status+': '+t.slice(0,160)); }
      const reader=res.body.getReader(), dec=new TextDecoder();
      while(true){ const {value,done}=await reader.read(); if(done) break; acc+=dec.decode(value,{stream:true});
        const b=document.getElementById('body-'+id); if(b){ b.classList.remove('empty'); b.textContent=acc; b.scrollTop=b.scrollHeight; } }
      if(!acc.trim()) throw new Error('пустой ответ от модели');
      n.output=acc; n.summary=acc.length>600?acc.slice(0,600)+'…':acc; n.cacheHash=hash;
      n.tokensIn=tokEst(msgs.map(m=>m.content).join('')); n.tokensOut=tokEst(acc); n.ms=Math.round(performance.now()-t0);
      n.status= n.requireApproval && !n.approved ? 'review' : 'done'; n.error='';
      logRow(n.name,'ok',`${n.tokensIn+n.tokensOut} ток., ${(n.ms/1000).toFixed(1)}с`,{cost:nodeCost(n)});
      save(); renderNodes(); renderEdges(); return true;
    }catch(err){
      if(attempt<maxR && /network|fetch|Failed/i.test(String(err.message))){ logRow(n.name,'retry','сеть, повтор #'+(attempt+1)); await wait(1000*2**attempt); continue; }
      n.status='error'; n.error=String(err.message||err); n.output=acc; logRow(n.name,'error',n.error);
      save(); renderNodes(); renderEdges(); toast('Ошибка «'+n.name+'»: '+n.error,'err'); return false;
    }
  }
  return false;
}
function topoOrder(){
  const indeg=new Map(state.nodes.map(n=>[n.id,0])); state.edges.forEach(e=>indeg.set(e.to,(indeg.get(e.to)||0)+1));
  const q=state.nodes.filter(n=>indeg.get(n.id)===0).map(n=>n.id), order=[];
  while(q.length){ const id=q.shift(); order.push(id); state.edges.filter(e=>e.from===id).forEach(e=>{ indeg.set(e.to,indeg.get(e.to)-1); if(indeg.get(e.to)===0) q.push(e.to); }); }
  return order.length===state.nodes.length? order : state.nodes.map(n=>n.id);
}
const isPaused=()=>state.nodes.some(n=>n.status==='review');
let order=null, pos=0, running=false;
async function runPipeline(resume){
  if(running) return;
  if(!hasKey()){ toast('Сначала задайте API-ключ','err'); return openSettings(); }
  if(!resume){ order=topoOrder(); pos=0; state.nodes.forEach(n=>{ n.status='idle'; n.error=''; n.approved=false; }); save(); renderNodes(); renderEdges(); }
  running=true; $('#run-btn').disabled=true; $('#run-btn').textContent='⏳ Работает…';
  while(pos<order.length){
    const n=node(order[pos]);
    if(state.global.costCapUSD>0 && projectCost()>=state.global.costCapUSD){ toast('Достигнут лимит бюджета '+money(state.global.costCapUSD),'err'); break; }
    const ok=await runNode(order[pos]); if(!ok) break;
    if(n.requireApproval && !n.approved){ toast('Агент «'+n.name+'» ждёт приёмки','warn'); break; }
    pos++;
  }
  running=false; $('#run-btn').disabled=false; render();
  if(pos>=order.length && state.nodes.every(n=>n.status==='done')) toast('Конвейер завершён ✓','ok');
}
function approveNode(id){ const n=node(id); n.approved=true; n.status='done'; logRow(n.name,'ok','принято вручную');
  if(order && order[pos]===id) pos++; save(); render(); if(order && pos<order.length) runPipeline(true); }

/* ============ DRAWER ============ */
const drawer=$('#drawer'), scrim=$('#scrim');
function openDrawer(title,html,mount){ $('#drawer-title').textContent=title; const b=$('#drawer-body'); b.innerHTML=html;
  drawer.classList.add('show'); scrim.classList.add('show'); if(mount) mount(b); }
function closeDrawer(){ drawer.classList.remove('show'); scrim.classList.remove('show'); }
$('#drawer-close').onclick=closeDrawer; scrim.onclick=closeDrawer;
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeDrawer(); });

function openNode(id){
  const n=node(id);
  const outBlock=n.error?`<div class="deliverable err"><div class="label">Ошибка</div>${esc(n.error)}</div>`:(n.output?`<div class="deliverable"><div class="label">Результат · ${n.tokensIn+n.tokensOut} ток. · ${money(nodeCost(n))}</div>${esc(n.output)}</div>`:'');
  const hist=n.promptHistory.length?`<div class="section-label">История промта (${n.promptHistory.length})</div>`+
    n.promptHistory.slice(0,5).map((h,i)=>`<div class="histrow"><span>${new Date(h.t).toLocaleString('ru-RU')}</span><button class="btn ghost sm" data-revert="${i}">↩ вернуть</button></div>`).join(''):'';
  openDrawer(`${n.emoji} ${esc(n.name)}`,`
    <div class="row2"><div class="field"><label>Имя</label><input id="f-name" value="${esc(n.name)}"></div>
      <div class="field"><label>Должность</label><input id="f-role" value="${esc(n.role)}"></div></div>
    <div class="field"><label>Системный промт</label><textarea id="f-prompt" rows="6">${esc(n.prompt)}</textarea>
      <div class="hint">Кто этот агент и как работает. Получает контекст книги, библию и результаты предыдущих агентов.</div></div>
    <label class="check"><input type="checkbox" id="f-appr" ${n.requireApproval?'checked':''}> Требовать мою приёмку (пауза конвейера)</label>
    <div class="section-label">Подключение (API)</div>
    <label class="check"><input type="checkbox" id="f-global" ${n.useGlobal?'checked':''}> Использовать глобальные настройки</label>
    <div id="own-cfg" style="${n.useGlobal?'display:none':''}">
      <div class="field"><label>API base URL</label><input id="f-base" value="${esc(n.baseURL)}" placeholder="${esc(state.global.baseURL)}"></div>
      <div class="row2"><div class="field"><label>Модель</label><input id="f-model" value="${esc(n.model)}" placeholder="${esc(state.global.model)}"></div>
        <div class="field"><label>Температура</label><input id="f-temp" type="number" step="0.1" min="0" max="2" value="${n.temperature}"></div></div>
      <div class="field"><label>API-ключ агента</label><input id="f-key" type="password" value="${esc(n.apiKey)}" placeholder="пусто — глобальный"></div>
    </div>
    <div class="actions"><button class="btn ok" id="f-save">Сохранить</button>
      <button class="btn ghost" id="f-run">▶ Прогнать</button><button class="btn danger" id="f-del">Удалить</button></div>
    ${hist}
    <div class="section-label">Текущий результат</div>
    ${outBlock||'<div class="hint" style="color:var(--faint)">Пока пусто.</div>'}
  `,b=>{
    b.querySelector('#f-global').onchange=ev=>{ b.querySelector('#own-cfg').style.display=ev.target.checked?'none':''; };
    const collect=()=>{ const np=b.querySelector('#f-prompt').value; if(np!==n.prompt){ n.promptHistory.unshift({t:Date.now(),prompt:n.prompt}); if(n.promptHistory.length>20) n.promptHistory.pop(); }
      n.name=b.querySelector('#f-name').value.trim()||n.name; n.role=b.querySelector('#f-role').value.trim(); n.prompt=np;
      n.requireApproval=b.querySelector('#f-appr').checked; n.useGlobal=b.querySelector('#f-global').checked;
      n.baseURL=b.querySelector('#f-base').value.trim(); n.model=b.querySelector('#f-model').value.trim();
      n.apiKey=b.querySelector('#f-key').value.trim(); const tv=parseFloat(b.querySelector('#f-temp').value); n.temperature=isNaN(tv)?1:tv; };
    b.querySelector('#f-save').onclick=()=>{ collect(); n.cacheHash=''; save(); render(); toast('Сохранено','ok'); };
    b.querySelector('#f-run').onclick=()=>{ collect(); n.cacheHash=''; save(); render(); runNode(n.id); };
    b.querySelector('#f-del').onclick=()=>{ state.nodes=state.nodes.filter(x=>x.id!==n.id); state.edges=state.edges.filter(e=>e.from!==n.id&&e.to!==n.id); save(); render(); closeDrawer(); toast('Агент удалён'); };
    b.querySelectorAll('[data-revert]').forEach(btn=>btn.onclick=()=>{ const h=n.promptHistory[+btn.dataset.revert]; if(h){ b.querySelector('#f-prompt').value=h.prompt; toast('Версия подставлена — нажмите Сохранить'); } });
  });
}
function openSettings(){
  const g=state.global;
  openDrawer('⚙ Глобальные настройки',`
    <div class="field"><label>API base URL</label><input id="g-base" value="${esc(g.baseURL)}"></div>
    <div class="row2"><div class="field"><label>Модель</label><input id="g-model" value="${esc(g.model)}"></div>
      <div class="field"><label>Температура</label><input id="g-temp" type="number" step="0.1" min="0" max="2" value="${g.temperature}"></div></div>
    <div class="field"><label>API-ключ (общий)</label><input id="g-key" type="password" value="${esc(g.apiKey)}" placeholder="sk-...">
      <div class="hint">Хранится только в этом браузере и уходит на локальный прокси, не в сторонние сервисы.</div></div>
    <div class="field"><label>Пресет провайдера</label><select id="g-preset"><option value="">— выбрать —</option>
      <option value="https://api.deepseek.com|deepseek-chat">DeepSeek (deepseek-chat)</option>
      <option value="https://api.deepseek.com|deepseek-reasoner">DeepSeek R1 (deepseek-reasoner)</option>
      <option value="https://api.openai.com/v1|gpt-4o-mini">OpenAI (gpt-4o-mini)</option></select></div>
    <div class="section-label">Лимиты и надёжность</div>
    <div class="row2"><div class="field"><label>Бюджет контекста (символов)</label><input id="g-ctx" type="number" value="${g.maxContextChars}"></div>
      <div class="field"><label>Ретраи при сбое</label><input id="g-retry" type="number" min="0" max="5" value="${g.maxRetries}"></div></div>
    <div class="row2"><div class="field"><label>Лимит бюджета, $ (0 = без)</label><input id="g-cap" type="number" step="0.1" value="${g.costCapUSD}"></div>
      <div class="field"><label>Токен прокси (если выложен в сеть)</label><input id="g-ptok" value="${esc(g.proxyToken)}" placeholder="не обязательно"></div></div>
    <div class="actions"><button class="btn ok" id="g-save">Сохранить</button></div>
  `,b=>{
    b.querySelector('#g-preset').onchange=ev=>{ if(!ev.target.value) return; const [u,m]=ev.target.value.split('|'); b.querySelector('#g-base').value=u; b.querySelector('#g-model').value=m; };
    b.querySelector('#g-save').onclick=()=>{ g.baseURL=b.querySelector('#g-base').value.trim()||g.baseURL; g.model=b.querySelector('#g-model').value.trim()||g.model;
      g.apiKey=b.querySelector('#g-key').value.trim(); const t=parseFloat(b.querySelector('#g-temp').value); g.temperature=isNaN(t)?1:t;
      g.maxContextChars=parseInt(b.querySelector('#g-ctx').value)||8000; g.maxRetries=parseInt(b.querySelector('#g-retry').value)||0;
      g.costCapUSD=parseFloat(b.querySelector('#g-cap').value)||0; g.proxyToken=b.querySelector('#g-ptok').value.trim();
      save(); render(); toast('Настройки сохранены','ok'); }; });
}
function openBible(){
  const rows=state.bible.map(b=>`<div class="bible-row" data-bid="${b.id}">
    <input class="bk" value="${esc(b.keys)}" placeholder="ключи: имя, прозвище (пусто = всегда)">
    <textarea class="bt" rows="2" placeholder="канон: факт о персонаже / мире / таймлайне">${esc(b.text)}</textarea>
    <button class="icon-btn" data-delbible="${b.id}">✕</button></div>`).join('');
  openDrawer('📖 Библия книги',`
    <p class="hint" style="margin-top:0">Канон книги. Запись подмешивается в контекст агента, когда её ключ встречается в тексте (пустые ключи — всегда). Защищает от противоречий и дрейфа.</p>
    <div id="bible-list">${rows||'<div class="hint" style="color:var(--faint)">Пока пусто.</div>'}</div>
    <div class="actions" style="margin-top:14px"><button class="btn ghost" id="b-add">＋ Запись</button><button class="btn ok" id="b-save">Сохранить</button></div>
  `,b=>{
    b.querySelector('#b-add').onclick=()=>{ state.bible.push({id:uid(),keys:'',text:''}); save(); openBible(); };
    b.querySelectorAll('[data-delbible]').forEach(x=>x.onclick=()=>{ state.bible=state.bible.filter(e=>e.id!==x.dataset.delbible); save(); openBible(); });
    b.querySelector('#b-save').onclick=()=>{ b.querySelectorAll('.bible-row').forEach(r=>{ const e=state.bible.find(x=>x.id===r.dataset.bid); if(e){ e.keys=r.querySelector('.bk').value.trim(); e.text=r.querySelector('.bt').value.trim(); } }); save(); toast('Библия сохранена','ok'); closeDrawer(); }; });
}
function openLog(){
  const rows=state.log.length?state.log.map(l=>`<div class="logrow l-${l.status}"><span class="lt">${new Date(l.t).toLocaleTimeString('ru-RU')}</span>
    <span class="ln">${esc(l.node)}</span><span class="ls">${l.status}</span><span class="lm">${esc(l.msg)}</span></div>`).join(''):'<div class="hint" style="color:var(--faint)">Журнал пуст.</div>';
  openDrawer('📋 Журнал вызовов',`<div class="log">${rows}</div>
    <div class="actions" style="margin-top:14px"><button class="btn ghost" id="log-clear">Очистить</button></div>`,
    b=>{ b.querySelector('#log-clear').onclick=()=>{ state.log=[]; save(); openLog(); }; });
}
function openInput(){
  openDrawer('📄 Исходный текст',`<div class="field"><label>Рукопись для редактирования</label>
    <textarea id="i-text" rows="16" placeholder="Вставьте текст…">${esc(state.project.input)}</textarea></div>
    <div class="actions"><button class="btn ok" id="i-save">Сохранить</button></div>`,
    b=>{ b.querySelector('#i-save').onclick=()=>{ state.project.input=b.querySelector('#i-text').value; save(); toast('Исходник сохранён','ok'); closeDrawer(); }; });
}
function openExport(){
  openDrawer('⬇ Экспорт / импорт',`
    <div class="section-label" style="border:0;margin-top:0;padding:0">Готовая книга</div>
    <div class="field"><label>Раскрытие ИИ (для площадок)</label><input id="x-disc" value="${esc(state.project.disclosure)}"></div>
    <div class="actions"><button class="btn ok" id="x-book">📕 Скачать книгу (.md)</button></div>
    <div class="section-label">Схема пайплайна</div>
    <div class="actions"><button class="btn ghost" id="x-exp">⬇ Экспорт проекта (.json)</button>
      <label class="btn ghost" style="cursor:pointer">📥 Импорт<input type="file" id="x-imp" accept="application/json" hidden></label></div>
    <div class="hint">Экспорт сохраняет агентов, промты, связи, библию и настройки (кроме ключей лучше чистить вручную).</div>
  `,b=>{
    b.querySelector('#x-disc').onchange=ev=>{ state.project.disclosure=ev.target.value; save(); };
    b.querySelector('#x-book').onclick=exportBook;
    b.querySelector('#x-exp').onclick=()=>download((state.project.title||'pipeline')+'.json', JSON.stringify(state,null,2));
    b.querySelector('#x-imp').onchange=ev=>{ const f=ev.target.files[0]; if(!f) return; const r=new FileReader(); r.onload=()=>{ try{ state=Object.assign(defaultState(),JSON.parse(r.result)); save(); render(); closeDrawer(); toast('Проект импортирован','ok'); }catch{ toast('Не удалось прочитать файл','err'); } }; r.readAsText(f); };
  });
}
function download(name,text){ const u=URL.createObjectURL(new Blob([text],{type:'text/plain'})); const a=document.createElement('a'); a.href=u; a.download=name; a.click(); URL.revokeObjectURL(u); }
function exportBook(){
  const pr=state.project;
  const term=state.nodes.filter(n=>!state.edges.some(e=>e.from===n.id)); // конечные узлы
  const body=state.nodes.filter(n=>n.output).map(n=>`### ${n.emoji} ${n.name} — ${n.role}\n\n${n.output}`).join('\n\n---\n\n');
  download((pr.title||'book')+'.md',
    `# ${pr.title||'Без названия'}\n\n> Раскрытие: ${pr.disclosure}\n\nЖанр: ${pr.genre} · Аудитория: ${pr.audience}\n\n${KDP_CHECKLIST}\n\n---\n\n${body||'(нет результатов — запустите конвейер)'}\n`);
  toast('Книга собрана','ok');
}

/* ============ ТОСТЫ ============ */
let toastT; function toast(m,k=''){ const t=$('#toast'); t.textContent=m; t.className='toast show '+k; clearTimeout(toastT); toastT=setTimeout(()=>t.className='toast '+k,2600); }

/* ============ СОБЫТИЯ ============ */
document.addEventListener('click',e=>{ const t=e.target.closest('[data-action]'); if(!t) return; const a=t.dataset.action,id=t.dataset.id;
  if(a==='run'){ isPaused()?runPipeline(true):runPipeline(false); }
  else if(a==='settings') openSettings(); else if(a==='add-node') addNodePicker(); else if(a==='auto-layout') autoLayout();
  else if(a==='edit-input') openInput(); else if(a==='open-node') openNode(id); else if(a==='run-node') runNode(id);
  else if(a==='approve') approveNode(id); else if(a==='bible') openBible(); else if(a==='log') openLog(); else if(a==='export') openExport();
});
function bindProj(sel,key){ const el=$(sel); el.addEventListener('change',()=>{ state.project[key]=el.value; save(); render(); }); }
['title','genre','audience','brief','mode'].forEach(k=>bindProj('#proj-'+(k==='audience'?'aud':k),k));
function autoLayout(){ state.nodes.forEach((n,i)=>{ n.x=60+(i%3)*250; n.y=40+Math.floor(i/3)*180; });
  state.edges=[]; for(let i=0;i<state.nodes.length-1;i++) state.edges.push({id:uid(),from:state.nodes[i].id,to:state.nodes[i+1].id}); save(); render(); toast('Схема выстроена в цепочку'); }
function addNodePicker(){
  openDrawer('＋ Добавить агента',`<div class="field"><label>Готовая роль</label><select id="add-tpl">
    ${TEMPLATES.map((t,i)=>`<option value="${i}">${t.emoji} ${t.name} — ${t.title}</option>`).join('')}
    <option value="custom">⚙️ Произвольный агент</option></select></div>
    <div class="hint">Появится на холсте. Свяжите вручную или «Авто-схема».</div>
    <div class="actions" style="margin-top:16px"><button class="btn ok" id="add-go">Добавить</button></div>`,
    b=>{ b.querySelector('#add-go').onclick=()=>{ const v=b.querySelector('#add-tpl').value;
      const t=v==='custom'?{name:'Новый агент',title:'роль',emoji:'🤖',prompt:'Ты — агент издательства. Опиши свою роль.'}:TEMPLATES[+v];
      state.nodes.push(freshNode(t,canvas.scrollLeft+80,canvas.scrollTop+80)); save(); render(); closeDrawer(); toast('Агент добавлен'); }; });
}

render();
