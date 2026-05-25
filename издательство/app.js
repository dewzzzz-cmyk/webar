'use strict';

/* ============ ШТАТ: роли агентов ============ */
const ROSTER = [
  { id:'scout',  emoji:'🔎', name:'Скаут',                role:'Редактор-аквизитор',
    brief:'Оцениваю идею под рынок: есть ли спрос, на кого рассчитана, чем зацепит. Честно говорю «зайдёт / не зайдёт» и почему.' },
  { id:'dev',    emoji:'🧭', name:'Структурный редактор', role:'Developmental editor',
    brief:'Работаю с сюжетом, арками героев и темпом. Нахожу провисания, логические дыры и слабые переходы.' },
  { id:'writer', emoji:'✍️', name:'Райтер',               role:'Автор / гострайтер',
    brief:'Пишу и дописываю по брифу, держу единый голос и стиль книги от первой до последней строки.' },
  { id:'line',   emoji:'🔧', name:'Литред',               role:'Литературный редактор',
    brief:'Чищу фразы, убираю воду, усиливаю авторский голос, выравниваю ритм текста.' },
  { id:'proof',  emoji:'🔍', name:'Корректор',            role:'Proofreader',
    brief:'Опечатки, грамматика, пунктуация, единообразие оформления кавычек, тире и заголовков.' },
  { id:'art',    emoji:'🎨', name:'Арт-директор',         role:'Дизайнер обложки',
    brief:'Готовлю бриф и концепт обложки под жанр и аудиторию: настроение, композиция, палитра, типографика.' },
  { id:'layout', emoji:'📐', name:'Верстальщик',          role:'Вёрстка / EPUB',
    brief:'Собираю EPUB и PDF: типографика, оглавление, колонтитулы, чистый интерьер книги.' },
  { id:'meta',   emoji:'🏷️', name:'Метаданные',           role:'Distribution',
    brief:'Категории, ключевые слова, описание для карточки на площадках, рекомендованная цена.' },
  { id:'mkt',    emoji:'📣', name:'Маркетолог',           role:'SMM / промо',
    brief:'Аннотация, посты, рекламные тексты и план запуска под целевую аудиторию.' },
];
const PIPELINES = {
  write:['scout','dev','writer','line','proof','art','layout','meta','mkt'],
  edit: ['scout','dev','line','proof','art','layout','meta','mkt'],
};
const agentById = id => ROSTER.find(a => a.id === id);

/* ============ СОСТОЯНИЕ ============ */
const KEY = 'izd_state_v1';
function defaultState(){
  return {
    studio:'ИИ-Издательство',
    policy:{ reader:'', loves:'', hates:'', tone:'', taboo:'' },
    agents:Object.fromEntries(ROSTER.map(a => [a.id, { brief:a.brief, hired:true }])),
    projects:[],
  };
}
let state = load();
function load(){ try { return Object.assign(defaultState(), JSON.parse(localStorage.getItem(KEY))); } catch { return defaultState(); } }
function save(){ localStorage.setItem(KEY, JSON.stringify(state)); }

let view = 'projects';
let openId = null;

/* ============ УТИЛИТЫ ============ */
const $ = s => document.querySelector(s);
const main = $('#main');
const esc = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const rnd = (a,b) => Math.floor(a + Math.random()*(b-a));
const uid = () => Date.now().toString(36)+Math.random().toString(36).slice(2,6);
const STATE_LABEL = { locked:'в очереди', todo:'готов к работе', working:'работает…', review:'на вашем ревью', done:'принято' };

/* ============ РЕНДЕР ============ */
function render(){
  document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.view===view));
  const inWork = state.projects.filter(p => !isComplete(p)).length;
  const done = state.projects.filter(isComplete).length;
  $('#kpi-books').textContent = inWork;
  $('#kpi-done').textContent = done;
  const reviews = state.projects.reduce((n,p)=> n + p.stages.filter(s=>s.status==='review').length, 0);
  const badge = $('#nav-review');
  badge.textContent = reviews; badge.classList.toggle('show', reviews>0);
  $('#studio-name').textContent = state.studio;

  if (view==='projects') main.innerHTML = openId ? workspaceHTML(byId(openId)) : projectsHTML();
  else if (view==='staff') main.innerHTML = staffHTML();
  else if (view==='policy') main.innerHTML = policyHTML();
}
const byId = id => state.projects.find(p=>p.id===id);
const stageDone = s => s.status==='done';
const isComplete = p => p.stages.length>0 && p.stages.every(stageDone);
const progress = p => p.stages.length ? Math.round(100 * p.stages.filter(stageDone).length / p.stages.length) : 0;

/* ---- Проекты (список) ---- */
function projectsHTML(){
  const head = `<div class="page-head">
    <div><h1>Проекты</h1><p>Книги в производстве. Вы — главный редактор: ставите задачи и принимаете работу.</p></div>
    <div class="spacer"></div>
    <button class="btn" data-action="new-project">＋ Новая книга</button>
  </div>`;
  if (!state.projects.length) return head + `<div class="empty"><div class="big">📚</div>
    <h3>Пока ни одной книги</h3><p>Создайте первый проект — выберите режим и назначьте штат.</p></div>`;
  const cards = state.projects.map(p=>{
    const rev = p.stages.filter(s=>s.status==='review').length;
    const cur = p.stages.find(s=>s.status!=='done');
    const stageTxt = isComplete(p) ? 'Выпущена 🎉' : (cur ? `${agentById(cur.agentId).emoji} ${agentById(cur.agentId).name} · ${STATE_LABEL[cur.status]}` : '—');
    return `<div class="card click proj" data-action="open-project" data-id="${p.id}">
      <div class="proj-top">
        <div class="proj-cover">${p.mode==='write'?'✒️':'📖'}</div>
        <div><div class="proj-title">${esc(p.title)}</div>
          <div class="proj-meta">${esc(p.genre||'без жанра')}</div></div>
      </div>
      <span class="chip ${p.mode}">${p.mode==='write'?'пишем с нуля':'редактируем'}</span>
      <div class="progress"><i style="width:${progress(p)}%"></i></div>
      <div class="proj-foot"><span>${stageTxt}</span>
        ${rev?`<span class="review-flag">● ${rev} на ревью</span>`:`<span>${progress(p)}%</span>`}</div>
    </div>`;
  }).join('');
  return head + `<div class="grid cols">${cards}</div>`;
}

/* ---- Рабочая зона книги (конвейер) ---- */
function workspaceHTML(p){
  if (!p) { openId=null; return projectsHTML(); }
  const stages = p.stages.map((s,idx)=>{
    const a = agentById(s.agentId);
    let btn = '';
    if (s.status==='todo') btn = `<button class="btn sm" data-action="assign" data-id="${p.id}" data-idx="${idx}">▶ Поручить</button>`;
    else if (s.status==='review') btn = `<button class="btn sm warn" data-action="open-review" data-id="${p.id}" data-idx="${idx}">👀 Проверить</button>`;
    const cls = s.status==='done'?'done':s.status==='review'?'review':s.status==='working'?'working':'';
    const stream = s.status==='working' ? `<div class="stage-stream" id="stream-${idx}"></div>` : '';
    return `<div class="stage ${cls}" data-sidx="${idx}">
      <div class="stage-row">
        <div class="stage-emoji">${a.emoji}</div>
        <div class="stage-info"><div class="stage-role">${a.name}</div><div class="stage-sub">${a.role}</div></div>
        <span class="stage-state s-${s.status}">${STATE_LABEL[s.status]}</span>
        ${btn}
      </div>${stream}
    </div>`;
  }).join('');
  const complete = isComplete(p);
  const busy = p.stages.some(s=>s.status==='working');
  return `<button class="back" data-action="back">← Все проекты</button>
    <div class="page-head" style="margin-top:10px">
      <div><h1>${esc(p.title)}</h1>
        <p>${p.mode==='write'?'Пишем с нуля':'Редактируем рукопись'} · ${esc(p.genre||'без жанра')} · аудитория: ${esc(p.audience||'не задана')}</p></div>
      <div class="spacer"></div>
      <span class="tok">~${p.tokens||0} токенов</span>
      ${(!complete && !busy)?`<button class="btn ghost" data-action="autorun" data-id="${p.id}">▶▶ Авто-прогон</button>`:''}
      ${complete?`<button class="btn ok" data-action="export" data-id="${p.id}">⬇ Экспорт книги</button>`:''}
    </div>
    ${p.brief?`<div class="deliverable"><div class="label">Бриф проекта</div>${esc(p.brief)}</div>`:''}
    <div class="pipeline">${stages}</div>`;
}

/* ---- Штат ---- */
function staffHTML(){
  const head = `<div class="page-head"><div><h1>Штат</h1>
    <p>Ваши ИИ-сотрудники. Инструктаж = редакционные стандарты, через которые работает каждый.</p></div></div>`;
  const cards = ROSTER.map(a=>{
    const st = state.agents[a.id];
    const busy = state.projects.some(p => !isComplete(p) && p.stages.some(s=>s.agentId===a.id && (s.status==='working'||s.status==='review'||s.status==='todo')));
    const pill = !st.hired ? `<span class="status-pill status-off">не в штате</span>`
      : busy ? `<span class="status-pill status-busy">занят</span>` : `<span class="status-pill status-free">свободен</span>`;
    return `<div class="card agent-card ${st.hired?'':'off'}">
      <div class="agent-top"><div class="agent-emoji">${a.emoji}</div>
        <div><div class="agent-name">${a.name}</div><div class="agent-role">${a.role}</div></div></div>
      <div class="agent-brief">${esc(st.brief)}</div>
      <div class="agent-foot">${pill}<div class="spacer" style="flex:1"></div>
        <button class="btn sm ghost" data-action="edit-brief" data-id="${a.id}">✎ Инструктаж</button>
        <button class="btn sm ${st.hired?'danger':'ok'}" data-action="toggle-hire" data-id="${a.id}">${st.hired?'Уволить':'Нанять'}</button>
      </div></div>`;
  }).join('');
  return head + `<div class="grid cols">${cards}</div>`;
}

/* ---- Редполитика ---- */
function policyHTML(){
  const p = state.policy;
  return `<div class="page-head"><div><h1>Редполитика</h1>
    <p>Ваше преимущество: понимание читателя. Эти установки получает каждый агент в каждой задаче.</p></div></div>
    <div class="card" style="max-width:640px">
      <div class="field"><label>Портрет читателя</label>
        <textarea id="pol-reader" rows="3" placeholder="Кто ваш читатель: возраст, что ищет в книге, на каких авторах вырос…">${esc(p.reader)}</textarea></div>
      <div class="field"><label>Что аудитория любит</label>
        <textarea id="pol-loves" rows="2" placeholder="Динамика, живые диалоги, неожиданные финалы…">${esc(p.loves)}</textarea></div>
      <div class="field"><label>Что отталкивает</label>
        <textarea id="pol-hates" rows="2" placeholder="Затянутые описания, морализаторство, клише…">${esc(p.hates)}</textarea></div>
      <div class="field"><label>Тон голоса издательства</label>
        <input id="pol-tone" value="${esc(p.tone)}" placeholder="Например: умный, тёплый, без снобизма"></div>
      <div class="field"><label>Табу</label>
        <input id="pol-taboo" value="${esc(p.taboo)}" placeholder="Темы и приёмы, которых не допускаем"></div>
      <button class="btn" data-action="save-policy">Сохранить политику</button>
    </div>`;
}

/* ============ ЗАГЛУШКИ РЕЗУЛЬТАТОВ АГЕНТОВ ============ */
function deliverable(agentId, p, attempt){
  const pol = state.policy.reader ? ' (с учётом редполитики)' : '';
  const g = p.genre || 'жанр не задан', aud = p.audience || 'широкая аудитория';
  const v = {
    scout:[`Оценка рынка${pol}: «${p.title}» в нише «${g}». Целевой читатель — ${aud}.\nВердикт: перспективно. Главный крючок — нестандартный конфликт. Риск — перенасыщенная ниша, нужен сильный хук в первой главе.\nРекомендация: в производство.`],
    dev:[`Структурный разбор:\n• Завязка цепляет, но 2-я треть провисает — добавить точку невозврата к гл. ${rnd(7,12)}.\n• Арка героя читается, мотивация антагониста слабовата.\n• Темп: ускорить переходы между сценами, срезать 1 побочную линию.`],
    writer:[`Черновик главы 1 (фрагмент)${pol}:\n«Город просыпался не сразу — сначала открывали глаза витрины, потом фонари, и только затем люди. ${p.title ? 'Она' : 'Он'} шёл против этого пробуждения, как против течения…»\nОбъём: ~${rnd(2,5)} тыс. слов.`],
    line:[`Литредактура: вычищено ~${rnd(8,18)}% воды, усилены диалоги, выровнен ритм.\nПример: было «он быстро и стремительно побежал» → стало «он рванул».\nГолос автора сохранён.`],
    proof:[`Корректура: исправлено ${rnd(20,60)} опечаток, ${rnd(10,40)} пунктуационных, унифицированы кавычки «ёлочки» и тире. Список правок приложен.`],
    art:[`Бриф обложки${pol}: жанр ${g}, настроение — напряжённое, но не мрачное.\nКонцепт: одиночная фигура на контрастном фоне. Палитра: индиго + тёплый акцент. Шрифт заголовка — гротеск крупным кеглем.`],
    layout:[`Вёрстка готова: EPUB + PDF, ${rnd(180,420)} стр.\nОсновной кегль 11, интерлиньяж 1.4, оглавление и колонтитулы, висячая пунктуация. Файлы прошли валидатор.`],
    meta:[`Метаданные:\n• Категории: ${g} / современная проза.\n• Ключевые слова: ${g}, новинка, для ${aud}.\n• Аннотация (180 зн.) готова.\n• Рекомендованная цена: ${rnd(299,699)} ₽.`],
    mkt:[`План запуска${pol}: 3 поста (тизер → цитата → релиз), таргет на «${aud}».\nАнонс в день старта продаж, рассылка по базе, 2 рекламных текста приложены.`],
  };
  const arr = v[agentId] || ['Готово.'];
  let out = arr[0];
  if (attempt>0) out = `(переработано по правке)\n` + out;
  return out;
}

/* ============ ДЕЙСТВИЯ ============ */
function newProjectDrawer(){
  openDrawer('Новая книга', `
    <div class="field"><label>Название</label><input id="np-title" placeholder="Рабочее название книги"></div>
    <div class="field"><label>Режим</label>
      <div class="seg">
        <label><input type="radio" name="np-mode" value="write" checked>
          <div class="opt"><b>✒️ Писать с нуля</b><small>агенты создают книгу по брифу</small></div></label>
        <label><input type="radio" name="np-mode" value="edit">
          <div class="opt"><b>📖 Редактировать</b><small>довести готовую рукопись</small></div></label>
      </div></div>
    <div class="field"><label>Жанр</label><input id="np-genre" placeholder="Например: триллер, нон-фикшн, young adult"></div>
    <div class="field"><label>Целевая аудитория</label><input id="np-aud" placeholder="Кому адресована книга"></div>
    <div class="field"><label>Бриф / задача</label>
      <textarea id="np-brief" rows="4" placeholder="Идея, ключевые требования, чего точно хотите и чего избегать"></textarea></div>
    <button class="btn" id="np-create">Создать и сформировать штат</button>
  `, body=>{
    body.querySelector('#np-create').onclick = ()=>{
      const title = body.querySelector('#np-title').value.trim();
      if(!title){ body.querySelector('#np-title').focus(); return; }
      const mode = body.querySelector('input[name=np-mode]:checked').value;
      const hiredOrder = PIPELINES[mode].filter(id => state.agents[id].hired);
      const stages = hiredOrder.map((agentId,i)=>({ agentId, status:i===0?'todo':'locked', deliverable:'', attempt:0, notes:[] }));
      state.projects.unshift({
        id:uid(), title, mode,
        genre:body.querySelector('#np-genre').value.trim(),
        audience:body.querySelector('#np-aud').value.trim(),
        brief:body.querySelector('#np-brief').value.trim(),
        stages, createdAt:Date.now(),
      });
      save(); closeDrawer(); openId = state.projects[0].id; render();
    };
  });
}

function payload(p, idx){
  const s = p.stages[idx]; const a = agentById(s.agentId);
  const prior = p.stages.slice(0, idx).filter(stageDone).map(x=>{
    const xa = agentById(x.agentId); return { name:xa.name, role:xa.role, text:x.deliverable };
  });
  return { agentId:a.id, name:a.name, role:a.role, brief:state.agents[a.id].brief,
    policy:state.policy, project:{title:p.title,genre:p.genre,audience:p.audience,brief:p.brief,mode:p.mode},
    prior, notes:s.notes };
}

async function runAgent(pid, idx){
  const p = byId(pid); const s = p.stages[idx];
  s.status='working'; s.deliverable=''; save(); if(openId===pid) render();
  let acc='';
  try{
    const res = await fetch('/api/generate', { method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload(p, idx)) });
    if(!res.ok || !res.body) throw new Error('HTTP '+res.status);
    const reader = res.body.getReader(), dec = new TextDecoder();
    while(true){
      const { value, done } = await reader.read(); if(done) break;
      acc += dec.decode(value, {stream:true});
      const el = document.getElementById('stream-'+idx);
      if(el){ el.textContent = acc; el.scrollTop = el.scrollHeight; }
    }
    if(!acc.trim()) throw new Error('пустой ответ');
  }catch(e){
    acc = deliverable(s.agentId, p, s.attempt); // фолбэк-заглушка (нет ключа/сети)
  }
  s.deliverable = acc;
  p.tokens = (p.tokens||0) + Math.max(1, Math.round(acc.length/5));
  s.status='review'; save(); if(openId===pid) render();
}
const assign = (pid, idx) => runAgent(pid, idx);

async function autoRun(pid){
  const p = byId(pid);
  for(let i=0;i<p.stages.length;i++){
    if(p.stages[i].status==='done') continue;
    if(p.stages[i].status==='locked') p.stages[i].status='todo';
    await runAgent(pid, i);
    approve(pid, i);
    await new Promise(r=>setTimeout(r, 250));
  }
}

function reviewDrawer(pid, idx){
  const p = byId(pid); const s = p.stages[idx]; const a = agentById(s.agentId);
  const notes = s.notes.length ? `<div class="notes"><div class="section-label">Ваши правки</div>${
    s.notes.map(n=>`<div class="note">${esc(n)}</div>`).join('')}</div>` : '';
  openDrawer(`${a.emoji} ${a.name}`, `
    <div class="deliverable"><div class="label">${a.role} · результат</div>${esc(s.deliverable)}</div>
    ${notes}
    <div class="field"><label>Вернуть с правкой (необязательно)</label>
      <textarea id="rv-note" rows="3" placeholder="Что переделать: «усилить финал», «убрать канцелярит»…"></textarea></div>
    <div class="review-actions">
      <button class="btn ok" id="rv-approve">✅ Принять</button>
      <button class="btn warn" id="rv-return">↩ Вернуть с правкой</button>
      <button class="btn ghost" id="rv-redo">🔁 Переделать</button>
    </div>
  `, body=>{
    body.querySelector('#rv-approve').onclick = ()=>{ approve(pid,idx); closeDrawer(); };
    body.querySelector('#rv-return').onclick = ()=>{
      const note = body.querySelector('#rv-note').value.trim();
      if(note) s.notes.push(note);
      s.attempt++; closeDrawer(); runAgent(pid, idx);
    };
    body.querySelector('#rv-redo').onclick = ()=>{ s.attempt++; closeDrawer(); runAgent(pid, idx); };
  });
}

function approve(pid, idx){
  const p = byId(pid); p.stages[idx].status='done';
  const next = p.stages[idx+1];
  if(next) next.status='todo';
  save(); render();
}

function exportBook(pid){
  const p = byId(pid);
  const parts = p.stages.map(s=>`### ${agentById(s.agentId).name} — ${agentById(s.agentId).role}\n${s.deliverable}`).join('\n\n');
  const blob = new Blob([`# ${p.title}\n\nЖанр: ${p.genre}\nАудитория: ${p.audience}\n\n${parts}\n`], {type:'text/markdown'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href=url; a.download=`${p.title||'book'}.md`; a.click();
  URL.revokeObjectURL(url);
}

function editBriefDrawer(aid){
  const a = agentById(aid); const st = state.agents[aid];
  openDrawer(`${a.emoji} ${a.name} · инструктаж`, `
    <p style="color:var(--dim);margin-top:0">Опишите стандарты и вкус этого сотрудника. Это его «обучение» — через эти установки он работает над каждой книгой.</p>
    <div class="field"><label>Бриф сотрудника</label><textarea id="br-text" rows="8">${esc(st.brief)}</textarea></div>
    <button class="btn" id="br-save">Сохранить инструктаж</button>
  `, body=>{
    body.querySelector('#br-save').onclick = ()=>{
      st.brief = body.querySelector('#br-text').value.trim() || a.brief;
      save(); closeDrawer(); render();
    };
  });
}

function savePolicy(){
  state.policy = {
    reader:$('#pol-reader').value.trim(), loves:$('#pol-loves').value.trim(),
    hates:$('#pol-hates').value.trim(), tone:$('#pol-tone').value.trim(), taboo:$('#pol-taboo').value.trim(),
  };
  save();
  const btn = document.querySelector('[data-action="save-policy"]');
  btn.textContent='✓ Сохранено'; setTimeout(()=>btn.textContent='Сохранить политику',1400);
}

/* ============ DRAWER ============ */
const drawer = $('#drawer'), scrim = $('#scrim');
function openDrawer(title, html, onMount){
  $('#drawer-title').textContent = title;
  const body = $('#drawer-body'); body.innerHTML = html; body.classList.add('fade-in');
  drawer.classList.add('show'); scrim.classList.add('show'); drawer.setAttribute('aria-hidden','false');
  if(onMount) onMount(body);
}
function closeDrawer(){ drawer.classList.remove('show'); scrim.classList.remove('show'); drawer.setAttribute('aria-hidden','true'); }
$('#drawer-close').onclick = closeDrawer;
scrim.onclick = closeDrawer;

/* ============ СОБЫТИЯ ============ */
$('#nav').addEventListener('click', e=>{
  const b = e.target.closest('.nav-item'); if(!b) return;
  view = b.dataset.view; openId = null; render();
});
document.addEventListener('click', e=>{
  const t = e.target.closest('[data-action]'); if(!t) return;
  const { action, id, idx } = t.dataset;
  if(action==='new-project') newProjectDrawer();
  else if(action==='open-project'){ openId=id; render(); }
  else if(action==='back'){ openId=null; render(); }
  else if(action==='assign') assign(id, +idx);
  else if(action==='autorun') autoRun(id);
  else if(action==='open-review') reviewDrawer(id, +idx);
  else if(action==='export') exportBook(id);
  else if(action==='edit-brief') editBriefDrawer(id);
  else if(action==='toggle-hire'){ state.agents[id].hired = !state.agents[id].hired; save(); render(); }
  else if(action==='save-policy') savePolicy();
});
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeDrawer(); });

render();
