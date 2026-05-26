'use strict';

/* ============ ДЕФОЛТНЫЕ АГЕНТЫ + ПРОМТЫ ============ */
const TEMPLATES = [
  { role:'scout',  name:'Скаут',        title:'Редактор-аквизитор', emoji:'🔎',
    prompt:'Ты — литературный скаут и редактор-аквизитор. Оцени коммерческий и художественный потенциал книги под конкретный рынок и аудиторию. Дай чёткий вердикт (в производство / доработать / отклонить), главный крючок, целевую полку и риски. Без воды.' },
  { role:'dev',    name:'Структурный редактор', title:'Developmental editor', emoji:'🧭',
    prompt:'Ты — структурный (developmental) редактор. Проанализируй и улучши композицию: сюжет, арки персонажей, темп, логику. Дай конкретные правки списком и при необходимости перепиши проблемные места.' },
  { role:'writer', name:'Райтер',       title:'Автор / гострайтер', emoji:'✍️',
    prompt:'Ты — профессиональный писатель-прозаик. Пиши живой, образный текст строго по брифу и в заданном жанре, держи единый голос. Выдавай готовую прозу, а не план.' },
  { role:'line',   name:'Литред',       title:'Литературный редактор', emoji:'🔧',
    prompt:'Ты — литературный редактор. Улучшай текст на уровне фраз: убирай воду и штампы, усиливай ритм и образность, сохраняй авторский голос. Возвращай отредактированный текст.' },
  { role:'proof',  name:'Корректор',    title:'Proofreader', emoji:'🔍',
    prompt:'Ты — корректор. Исправляй орфографию, пунктуацию, грамматику и единообразие оформления. Возвращай вычитанный текст и краткий список ключевых правок.' },
  { role:'art',    name:'Арт-директор', title:'Дизайнер обложки', emoji:'🎨',
    prompt:'Ты — арт-директор. Составь подробный бриф обложки: концепция, композиция, палитра, типографика, настроение — под жанр и аудиторию. Дай 2–3 варианта.' },
  { role:'layout', name:'Верстальщик',  title:'Вёрстка / EPUB', emoji:'📐',
    prompt:'Ты — верстальщик. Опиши параметры вёрстки для EPUB и печати: форматы, шрифты, отступы, оглавление, колонтитулы.' },
  { role:'meta',   name:'Метаданные',   title:'Distribution', emoji:'🏷️',
    prompt:'Ты — специалист по метаданным и дистрибуции. Подготовь категории, ключевые слова, аннотацию для магазина (до 200 знаков) и рекомендованную цену в рублях.' },
  { role:'mkt',    name:'Маркетолог',   title:'SMM / промо', emoji:'📣',
    prompt:'Ты — книжный маркетолог. Составь план запуска и 3 готовых рекламных поста (тизер / цитата / релиз) под целевую аудиторию.' },
];

/* ============ СОСТОЯНИЕ ============ */
const KEY='izd_studio_v2';
const uid=()=>Date.now().toString(36)+Math.random().toString(36).slice(2,6);

function freshNode(t, x, y){
  return { id:uid(), name:t.name, role:t.title, emoji:t.emoji, prompt:t.prompt,
    x, y, useGlobal:true, baseURL:'', apiKey:'', model:'', temperature:1.0,
    output:'', status:'idle', error:'' };
}
function defaultState(){
  const nodes = TEMPLATES.map((t,i)=> freshNode(t, 60+(i%3)*250, 40+Math.floor(i/3)*180));
  const edges = [];
  for(let i=0;i<nodes.length-1;i++) edges.push({ id:uid(), from:nodes[i].id, to:nodes[i+1].id });
  return {
    project:{ title:'', genre:'', audience:'', brief:'', mode:'write', input:'' },
    global:{ baseURL:'https://api.deepseek.com', apiKey:'', model:'deepseek-chat', temperature:1.0 },
    nodes, edges,
  };
}
let state = load();
function load(){ try{ const s=JSON.parse(localStorage.getItem(KEY)); return s&&s.nodes? s : defaultState(); }catch{ return defaultState(); } }
function save(){ localStorage.setItem(KEY, JSON.stringify(state)); }

const NW=212, PORT_Y=23;
const node=id=>state.nodes.find(n=>n.id===id);
const $=s=>document.querySelector(s);
const esc=s=>(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const cfg=n=> n.useGlobal ? state.global : {
  baseURL:n.baseURL||state.global.baseURL, apiKey:n.apiKey||state.global.apiKey,
  model:n.model||state.global.model, temperature:typeof n.temperature==='number'?n.temperature:state.global.temperature };
const hasKey=()=> state.nodes.some(n=>cfg(n).apiKey) || !!state.global.apiKey;

/* ============ РЕНДЕР ============ */
const nodesEl=$('#nodes'), edgesEl=$('#edges');
function render(){
  $('#proj-title').value=state.project.title;
  $('#proj-genre').value=state.project.genre;
  $('#proj-aud').value=state.project.audience;
  $('#proj-brief').value=state.project.brief;
  $('#proj-mode').value=state.project.mode;
  const ks=$('#api-state');
  ks.textContent = hasKey() ? '● ключ задан' : '● ключ не задан';
  ks.classList.toggle('ok', hasKey());
  $('#input-btn').style.display = state.project.mode==='edit' ? '' : 'none';
  $('#canvas-hint').textContent = 'Тяни блок за шапку • соединяй кружки (выход→вход) • клик по связи — удалить';
  renderNodes(); renderEdges();
}
function renderNodes(){
  nodesEl.innerHTML = state.nodes.map(n=>{
    const out = n.error ? `⚠ ${esc(n.error)}` : (n.output ? esc(n.output) : 'нет результата');
    return `<div class="node ${n.status}" data-node="${n.id}" style="left:${n.x}px;top:${n.y}px">
      <div class="port in"  data-port="in"  data-id="${n.id}"></div>
      <div class="port out" data-port="out" data-id="${n.id}"></div>
      <div class="node-head" data-drag="${n.id}">
        <div class="node-emoji">${n.emoji}</div>
        <div><div class="node-name">${esc(n.name)}</div><div class="node-role">${esc(n.role)}</div></div>
        <div class="node-status"></div>
      </div>
      <div class="node-body ${n.output||n.error?'':'empty'}" id="body-${n.id}">${out}</div>
      <div class="node-foot">
        <button class="btn ghost sm" data-action="open-node" data-id="${n.id}">⚙ Настроить</button>
        <button class="btn ghost sm" data-action="run-node" data-id="${n.id}">▶ Прогнать</button>
      </div>
    </div>`;
  }).join('');
}
function portPos(id, side){ const n=node(id); return { x:n.x+(side==='out'?NW:0), y:n.y+PORT_Y+7 }; }
function edgePath(a,b){ const dx=Math.max(40,Math.abs(b.x-a.x)*0.5); return `M ${a.x} ${a.y} C ${a.x+dx} ${a.y}, ${b.x-dx} ${b.y}, ${b.x} ${b.y}`; }
function renderEdges(){
  edgesEl.innerHTML = state.edges.map(e=>{
    if(!node(e.from)||!node(e.to)) return '';
    const d=edgePath(portPos(e.from,'out'), portPos(e.to,'in'));
    const flow = node(e.from).status==='running' || node(e.to).status==='running';
    return `<path class="edge ${flow?'flow':''}" d="${d}"></path>
            <path class="edge hit" d="${d}" data-edge="${e.id}"></path>`;
  }).join('');
}

/* ============ ПЕРЕТАСКИВАНИЕ УЗЛОВ ============ */
const canvas=$('#canvas');
let drag=null;
nodesEl.addEventListener('mousedown', e=>{
  const h=e.target.closest('[data-drag]'); if(!h) return;
  const n=node(h.dataset.drag); const r=canvas.getBoundingClientRect();
  drag={ id:n.id, dx:e.clientX - r.left + canvas.scrollLeft - n.x, dy:e.clientY - r.top + canvas.scrollTop - n.y };
  e.preventDefault();
});

/* ============ ПРОВОДА (связи) ============ */
let wire=null;
nodesEl.addEventListener('mousedown', e=>{
  const p=e.target.closest('.port.out'); if(!p) return;
  wire={ from:p.dataset.id }; e.stopPropagation(); e.preventDefault();
});
function canvasPoint(e){ const r=canvas.getBoundingClientRect(); return { x:e.clientX-r.left+canvas.scrollLeft, y:e.clientY-r.top+canvas.scrollTop }; }

window.addEventListener('mousemove', e=>{
  if(drag){
    const n=node(drag.id); const pt=canvasPoint(e);
    n.x=Math.max(0, pt.x-drag.dx); n.y=Math.max(0, pt.y-drag.dy);
    const el=nodesEl.querySelector(`[data-node="${n.id}"]`); if(el){ el.style.left=n.x+'px'; el.style.top=n.y+'px'; }
    renderEdges();
  } else if(wire){
    const a=portPos(wire.from,'out'), b=canvasPoint(e);
    let temp=edgesEl.querySelector('.edge-temp');
    if(!temp){ temp=document.createElementNS('http://www.w3.org/2000/svg','path'); temp.setAttribute('class','edge-temp'); edgesEl.appendChild(temp); }
    temp.setAttribute('d', edgePath(a,b));
  }
});
window.addEventListener('mouseup', e=>{
  if(drag){ drag=null; save(); }
  if(wire){
    const tgt=document.elementFromPoint(e.clientX,e.clientY);
    const ip=tgt && tgt.closest && tgt.closest('.port.in');
    if(ip){ const to=ip.dataset.id; addEdge(wire.from, to); }
    wire=null; const t=edgesEl.querySelector('.edge-temp'); if(t) t.remove(); renderEdges();
  }
});
function addEdge(from, to){
  if(from===to) return toast('Нельзя соединить агента с собой','err');
  if(state.edges.some(x=>x.from===from&&x.to===to)) return;
  if(wouldCycle(from,to)) return toast('Связь создаёт петлю — отклонено','err');
  state.edges.push({ id:uid(), from, to }); save(); renderEdges();
}
function wouldCycle(from,to){ // добавление from→to создаст цикл, если to уже достигает from
  const seen=new Set(); const stack=[to];
  while(stack.length){ const c=stack.pop(); if(c===from) return true; if(seen.has(c)) continue; seen.add(c);
    state.edges.filter(e=>e.from===c).forEach(e=>stack.push(e.to)); }
  return false;
}

/* ============ КЛИК ПО ХОЛСТУ (удаление связи, действия) ============ */
edgesEl.addEventListener('click', e=>{
  const p=e.target.closest('[data-edge]'); if(!p) return;
  state.edges=state.edges.filter(x=>x.id!==p.dataset.edge); save(); renderEdges(); toast('Связь удалена');
});

/* ============ ГЕНЕРАЦИЯ ============ */
function buildMessages(n){
  const pr=state.project;
  const preds=state.edges.filter(e=>e.to===n.id).map(e=>node(e.from)).filter(Boolean);
  const priorTxt=preds.filter(p=>p.output).map(p=>`— ${p.name} (${p.role}):\n${p.output}`).join('\n\n');
  let user=`Книга: «${pr.title||'без названия'}»\nЖанр: ${pr.genre||'не задан'}\nАудитория: ${pr.audience||'не задана'}\n`+
    `Режим: ${pr.mode==='write'?'пишем с нуля':'редактируем готовый текст'}\n`+
    (pr.brief?`Бриф: ${pr.brief}\n`:'');
  if(pr.mode==='edit' && pr.input && preds.length===0) user+=`\nИсходный текст:\n${pr.input}\n`;
  if(priorTxt) user+=`\nМатериалы от предыдущих агентов:\n${priorTxt}\n`;
  user+=`\nВыполни свою роль и выдай конкретный результат.`;
  return [ { role:'system', content:n.prompt }, { role:'user', content:user } ];
}

async function runNode(id){
  const n=node(id); const c=cfg(n);
  if(!c.apiKey){ n.status='error'; n.error='не задан API-ключ (Настройки агента или ⚙ глобальные)'; save(); renderNodes(); openSettings(); return false; }
  n.status='running'; n.output=''; n.error=''; save(); renderNodes(); renderEdges();
  let acc='';
  try{
    const res=await fetch('/api/generate',{ method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ baseURL:c.baseURL, apiKey:c.apiKey, model:c.model, temperature:c.temperature, messages:buildMessages(n) }) });
    if(!res.ok){ const t=await res.text(); throw new Error(t.slice(0,200)); }
    const reader=res.body.getReader(), dec=new TextDecoder();
    while(true){ const {value,done}=await reader.read(); if(done) break;
      acc+=dec.decode(value,{stream:true});
      const b=document.getElementById('body-'+id); if(b){ b.classList.remove('empty'); b.textContent=acc; b.scrollTop=b.scrollHeight; }
    }
    if(!acc.trim()) throw new Error('пустой ответ от модели');
    n.output=acc; n.status='done'; n.error=''; save(); renderNodes(); renderEdges(); return true;
  }catch(err){
    n.status='error'; n.error=String(err.message||err); n.output=acc; save(); renderNodes(); renderEdges();
    toast('Ошибка агента «'+n.name+'»: '+n.error,'err'); return false;
  }
}

function topoOrder(){
  const indeg=new Map(state.nodes.map(n=>[n.id,0]));
  state.edges.forEach(e=>indeg.set(e.to,(indeg.get(e.to)||0)+1));
  const q=state.nodes.filter(n=>indeg.get(n.id)===0).map(n=>n.id); const order=[];
  while(q.length){ const id=q.shift(); order.push(id);
    state.edges.filter(e=>e.from===id).forEach(e=>{ indeg.set(e.to,indeg.get(e.to)-1); if(indeg.get(e.to)===0) q.push(e.to); }); }
  return order.length===state.nodes.length ? order : state.nodes.map(n=>n.id);
}
let running=false;
async function runPipeline(){
  if(running) return;
  if(!hasKey()){ toast('Сначала задайте API-ключ','err'); return openSettings(); }
  running=true; const btn=$('#run-btn'); btn.disabled=true; btn.textContent='⏳ Работает…';
  state.nodes.forEach(n=>{ n.status='idle'; n.output=''; n.error=''; }); save(); renderNodes();
  for(const id of topoOrder()){ const okk=await runNode(id); if(!okk) break; }
  running=false; btn.disabled=false; btn.textContent='▶ Запустить конвейер';
  if(state.nodes.every(n=>n.status==='done')) toast('Конвейер завершён ✓','ok');
}

/* ============ DRAWER / НАСТРОЙКИ ============ */
const drawer=$('#drawer'), scrim=$('#scrim');
function openDrawer(title, html, mount){
  $('#drawer-title').textContent=title; const b=$('#drawer-body'); b.innerHTML=html;
  drawer.classList.add('show'); scrim.classList.add('show'); if(mount) mount(b);
}
function closeDrawer(){ drawer.classList.remove('show'); scrim.classList.remove('show'); }
$('#drawer-close').onclick=closeDrawer; scrim.onclick=closeDrawer;
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeDrawer(); });

function openNode(id){
  const n=node(id);
  const outBlock = n.error
    ? `<div class="deliverable err"><div class="label">Ошибка</div>${esc(n.error)}</div>`
    : (n.output?`<div class="deliverable"><div class="label">Результат</div>${esc(n.output)}</div>`:'');
  openDrawer(`${n.emoji} ${esc(n.name)}`, `
    <div class="row2">
      <div class="field"><label>Имя</label><input id="f-name" value="${esc(n.name)}"></div>
      <div class="field"><label>Должность</label><input id="f-role" value="${esc(n.role)}"></div>
    </div>
    <div class="field"><label>Системный промт (описание агента)</label>
      <textarea id="f-prompt" rows="6">${esc(n.prompt)}</textarea>
      <div class="hint">Кто этот агент и как он работает. Получает контекст книги и результаты предыдущих агентов.</div></div>

    <div class="section-label">Подключение (API)</div>
    <label class="check"><input type="checkbox" id="f-global" ${n.useGlobal?'checked':''}> Использовать глобальные настройки</label>
    <div id="own-cfg" style="${n.useGlobal?'display:none':''}">
      <div class="field"><label>API base URL</label><input id="f-base" value="${esc(n.baseURL)}" placeholder="${esc(state.global.baseURL)}"></div>
      <div class="row2">
        <div class="field"><label>Модель</label><input id="f-model" value="${esc(n.model)}" placeholder="${esc(state.global.model)}"></div>
        <div class="field"><label>Температура</label><input id="f-temp" type="number" step="0.1" min="0" max="2" value="${n.temperature}"></div>
      </div>
      <div class="field"><label>API-ключ агента</label><input id="f-key" type="password" value="${esc(n.apiKey)}" placeholder="оставьте пустым — возьмётся глобальный"></div>
    </div>

    <div class="actions">
      <button class="btn ok" id="f-save">Сохранить</button>
      <button class="btn ghost" id="f-run">▶ Прогнать этого агента</button>
      <button class="btn danger" id="f-del">Удалить агента</button>
    </div>
    <div class="section-label">Текущий результат</div>
    ${outBlock || '<div class="hint" style="color:var(--faint)">Пока пусто — запустите агента.</div>'}
  `, b=>{
    b.querySelector('#f-global').onchange=ev=>{ b.querySelector('#own-cfg').style.display=ev.target.checked?'none':''; };
    const collect=()=>{ n.name=b.querySelector('#f-name').value.trim()||n.name; n.role=b.querySelector('#f-role').value.trim();
      n.prompt=b.querySelector('#f-prompt').value; n.useGlobal=b.querySelector('#f-global').checked;
      n.baseURL=b.querySelector('#f-base').value.trim(); n.model=b.querySelector('#f-model').value.trim();
      n.apiKey=b.querySelector('#f-key').value.trim(); const tv=parseFloat(b.querySelector('#f-temp').value); n.temperature=isNaN(tv)?1.0:tv; };
    b.querySelector('#f-save').onclick=()=>{ collect(); save(); render(); toast('Сохранено','ok'); };
    b.querySelector('#f-run').onclick=()=>{ collect(); save(); render(); runNode(n.id); };
    b.querySelector('#f-del').onclick=()=>{ state.nodes=state.nodes.filter(x=>x.id!==n.id);
      state.edges=state.edges.filter(e=>e.from!==n.id&&e.to!==n.id); save(); render(); closeDrawer(); toast('Агент удалён'); };
  });
}

function openSettings(){
  const g=state.global;
  openDrawer('⚙ Глобальные настройки', `
    <div class="field"><label>API base URL</label><input id="g-base" value="${esc(g.baseURL)}"></div>
    <div class="row2">
      <div class="field"><label>Модель по умолчанию</label><input id="g-model" value="${esc(g.model)}"></div>
      <div class="field"><label>Температура</label><input id="g-temp" type="number" step="0.1" min="0" max="2" value="${g.temperature}"></div>
    </div>
    <div class="field"><label>API-ключ (общий для всех агентов)</label>
      <input id="g-key" type="password" value="${esc(g.apiKey)}" placeholder="sk-...">
      <div class="hint">Ключ хранится только в этом браузере и уходит на локальный прокси (server.js), а не в сторонние сервисы. Каждому агенту можно задать свой ключ в его настройках.</div></div>
    <div class="field"><label>Пресеты провайдера</label>
      <select id="g-preset">
        <option value="">— выбрать —</option>
        <option value="https://api.deepseek.com|deepseek-chat">DeepSeek (deepseek-chat)</option>
        <option value="https://api.deepseek.com|deepseek-reasoner">DeepSeek R1 (deepseek-reasoner)</option>
        <option value="https://api.openai.com/v1|gpt-4o-mini">OpenAI (gpt-4o-mini)</option>
      </select></div>
    <div class="actions"><button class="btn ok" id="g-save">Сохранить</button></div>
  `, b=>{
    b.querySelector('#g-preset').onchange=ev=>{ const v=ev.target.value; if(!v) return; const [u,m]=v.split('|');
      b.querySelector('#g-base').value=u; b.querySelector('#g-model').value=m; };
    b.querySelector('#g-save').onclick=()=>{ g.baseURL=b.querySelector('#g-base').value.trim()||g.baseURL;
      g.model=b.querySelector('#g-model').value.trim()||g.model; g.apiKey=b.querySelector('#g-key').value.trim();
      const tv=parseFloat(b.querySelector('#g-temp').value); g.temperature=isNaN(tv)?1.0:tv; save(); render(); toast('Настройки сохранены','ok'); };
  });
}

function openInput(){
  openDrawer('📄 Исходный текст', `
    <div class="field"><label>Рукопись для редактирования</label>
      <textarea id="i-text" rows="16" placeholder="Вставьте текст, который агенты будут редактировать…">${esc(state.project.input)}</textarea></div>
    <div class="actions"><button class="btn ok" id="i-save">Сохранить</button></div>
  `, b=>{ b.querySelector('#i-save').onclick=()=>{ state.project.input=b.querySelector('#i-text').value; save(); toast('Исходник сохранён','ok'); closeDrawer(); }; });
}

/* ============ ТОСТЫ ============ */
let toastT;
function toast(msg, kind=''){ const t=$('#toast'); t.textContent=msg; t.className='toast show '+kind;
  clearTimeout(toastT); toastT=setTimeout(()=>t.className='toast '+kind, 2600); }

/* ============ СОБЫТИЯ ============ */
document.addEventListener('click', e=>{
  const t=e.target.closest('[data-action]'); if(!t) return;
  const a=t.dataset.action, id=t.dataset.id;
  if(a==='run') runPipeline();
  else if(a==='settings') openSettings();
  else if(a==='add-node') addNodePicker();
  else if(a==='auto-layout') autoLayout();
  else if(a==='edit-input') openInput();
  else if(a==='open-node') openNode(id);
  else if(a==='run-node') runNode(id);
});
function bindProj(sel, key){ const el=$(sel); el.addEventListener('change',()=>{ state.project[key]=el.value; save(); render(); }); }
bindProj('#proj-title','title'); bindProj('#proj-genre','genre'); bindProj('#proj-aud','audience');
bindProj('#proj-brief','brief'); bindProj('#proj-mode','mode');

function autoLayout(){
  state.nodes.forEach((n,i)=>{ n.x=60+(i%3)*250; n.y=40+Math.floor(i/3)*180; });
  state.edges=[]; for(let i=0;i<state.nodes.length-1;i++) state.edges.push({id:uid(),from:state.nodes[i].id,to:state.nodes[i+1].id});
  save(); render(); toast('Схема выстроена в цепочку');
}
function addNodePicker(){
  openDrawer('＋ Добавить агента', `
    <div class="field"><label>Готовая роль</label><select id="add-tpl">
      ${TEMPLATES.map((t,i)=>`<option value="${i}">${t.emoji} ${t.name} — ${t.title}</option>`).join('')}
      <option value="custom">⚙️ Произвольный агент</option>
    </select></div>
    <div class="hint">Агент появится на холсте. Связи нарисуйте сами или нажмите «Авто-схема».</div>
    <div class="actions" style="margin-top:16px"><button class="btn ok" id="add-go">Добавить</button></div>
  `, b=>{ b.querySelector('#add-go').onclick=()=>{ const v=b.querySelector('#add-tpl').value;
    const t = v==='custom' ? {name:'Новый агент',title:'роль',emoji:'🤖',prompt:'Ты — агент издательства. Опиши свою роль в промте.'} : TEMPLATES[+v];
    const sc=$('#canvas'); state.nodes.push(freshNode(t, sc.scrollLeft+80, sc.scrollTop+80)); save(); render(); closeDrawer(); toast('Агент добавлен'); }; });
}

render();
