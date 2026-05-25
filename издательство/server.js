'use strict';
/*
 * Прокси для DeepSeek (без зависимостей). Хранит ключ на сервере и
 * стримит ответ агента во фронтенд. Состояние агентов/политики живёт
 * на фронте и приходит в теле запроса — сервер только собирает промт.
 *
 * Запуск:  DEEPSEEK_API_KEY=sk-... node server.js  →  http://localhost:8787
 *
 * env: DEEPSEEK_API_KEY (обязателен), DEEPSEEK_MODEL (deepseek-chat),
 *      DEEPSEEK_BASE (https://api.deepseek.com), PORT (8787)
 */
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const PORT  = process.env.PORT || 8787;
const KEY   = process.env.DEEPSEEK_API_KEY || '';
const MODEL = process.env.DEEPSEEK_MODEL || 'deepseek-chat';
const BASE  = process.env.DEEPSEEK_BASE || 'https://api.deepseek.com';
const ROOT  = __dirname;

// Конкретная задача каждой роли (дополняет бриф сотрудника).
const TASKS = {
  scout:  'Оцени коммерческий потенциал книги под рынок и аудиторию. Дай вердикт (в производство / доработать / отклонить), главный крючок и основной риск. Коротко.',
  dev:    'Сделай структурный разбор: сюжет, арки героев, темп. Дай 3–5 конкретных правок списком. Коротко.',
  writer: 'Напиши фрагмент начала первой главы: 5–8 предложений живой художественной прозы строго по брифу и политике. Только текст главы, без пояснений и заголовков.',
  line:   'Проведи литературную редактуру. Опиши, что улучшил, и приведи 1–2 примера «было → стало». Коротко.',
  proof:  'Дай отчёт корректора: типы и количество исправлений, унификация оформления. Коротко.',
  art:    'Составь бриф обложки: настроение, композиция, палитра, шрифт — под жанр и аудиторию. Коротко.',
  layout: 'Дай сводку вёрстки: формат (EPUB/PDF), объём, типографика, готовность файлов. Коротко.',
  meta:   'Подготовь метаданные для площадок: категории, 5 ключевых слов, аннотация до 200 знаков, рекомендованная цена в рублях.',
  mkt:    'Составь план запуска: 3 поста (тизер / цитата / релиз) и краткий медиаплан под аудиторию. Дай готовые тексты постов.',
};

const MIME = { '.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.svg':'image/svg+xml',
  '.png':'image/png','.ico':'image/x-icon' };

function send(res, code, body, type='text/plain; charset=utf-8'){
  res.writeHead(code, { 'Content-Type': type }); res.end(body);
}
function serveStatic(req, res){
  let rel = decodeURIComponent(req.url.split('?')[0]);
  if (rel === '/' || rel === '') rel = '/index.html';
  const fp = path.normalize(path.join(ROOT, rel));
  if (!fp.startsWith(ROOT)) return send(res, 403, 'Forbidden');
  fs.readFile(fp, (err, data) =>
    err ? send(res, 404, 'Not found') : send(res, 200, data, MIME[path.extname(fp)] || 'application/octet-stream'));
}

function buildMessages(b){
  const pol = b.policy || {};
  const polLines = [
    pol.reader && `Читатель: ${pol.reader}`,
    pol.loves  && `Аудитория любит: ${pol.loves}`,
    pol.hates  && `Отталкивает: ${pol.hates}`,
    pol.tone   && `Тон издательства: ${pol.tone}`,
    pol.taboo  && `Табу: ${pol.taboo}`,
  ].filter(Boolean).join('\n');

  const system =
    `Ты — ${b.name}, ${b.role} в современном независимом издательстве. ` +
    `Твои профессиональные стандарты: ${b.brief}\n` +
    (polLines ? `\nРедакционная политика, которой ты обязан следовать:\n${polLines}\n` : '') +
    `\nОтвечай по-русски, по делу, без воды и без вступлений про себя.`;

  const proj = b.project || {};
  const prior = (b.prior || []).map(p => `— ${p.name} (${p.role}):\n${p.text}`).join('\n\n');
  const notes = (b.notes || []).length ? `\n\nПравки заказчика, которые нужно учесть:\n- ${b.notes.join('\n- ')}` : '';

  const user =
    `Книга: «${proj.title || 'без названия'}»\n` +
    `Жанр: ${proj.genre || 'не задан'}\nАудитория: ${proj.audience || 'не задана'}\n` +
    `Режим: ${proj.mode === 'write' ? 'пишем с нуля' : 'редактируем готовую рукопись'}\n` +
    (proj.brief ? `Бриф проекта: ${proj.brief}\n` : '') +
    (prior ? `\nЧто уже сделали коллеги:\n${prior}\n` : '') +
    notes +
    `\n\nТвоя задача: ${TASKS[b.agentId] || 'Выполни свою роль и выдай конкретный результат.'}`;

  return [ { role:'system', content:system }, { role:'user', content:user } ];
}

async function handleGenerate(req, res){
  if (!KEY) return send(res, 503, 'DEEPSEEK_API_KEY не задан — фронт работает на заглушках.');
  let raw = '';
  req.on('data', c => { raw += c; if (raw.length > 2e5) req.destroy(); });
  req.on('end', async () => {
    let body = {}; try { body = JSON.parse(raw || '{}'); } catch {}
    let up;
    try {
      up = await fetch(`${BASE}/chat/completions`, {
        method:'POST',
        headers:{ 'Content-Type':'application/json', 'Authorization':`Bearer ${KEY}` },
        body: JSON.stringify({ model:MODEL, messages:buildMessages(body), stream:true, temperature:1.0 }),
      });
    } catch (e) { return send(res, 502, 'Не удалось подключиться к DeepSeek: ' + e.message); }
    if (!up.ok || !up.body) {
      const t = await up.text().catch(()=> ''); return send(res, up.status || 502, 'DeepSeek: ' + t.slice(0,300));
    }
    res.writeHead(200, { 'Content-Type':'text/plain; charset=utf-8', 'Cache-Control':'no-cache' });
    const reader = up.body.getReader(), dec = new TextDecoder(); let buf = '';
    try {
      while (true) {
        const { value, done } = await reader.read(); if (done) break;
        buf += dec.decode(value, { stream:true });
        const lines = buf.split('\n'); buf = lines.pop();
        for (const line of lines) {
          const s = line.trim(); if (!s.startsWith('data:')) continue;
          const data = s.slice(5).trim(); if (data === '[DONE]') continue;
          try { const d = JSON.parse(data).choices?.[0]?.delta?.content; if (d) res.write(d); } catch {}
        }
      }
    } catch {}
    res.end();
  });
}

http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return send(res, 204, '');
  if (req.method === 'POST' && req.url === '/api/generate') return handleGenerate(req, res);
  if (req.method === 'GET') return serveStatic(req, res);
  send(res, 405, 'Method not allowed');
}).listen(PORT, () => {
  console.log(`ИИ-Издательство → http://localhost:${PORT}`);
  console.log(`DeepSeek: ${KEY ? 'ключ найден, реальная генерация активна' : 'ключ НЕ задан — заглушки'} (модель ${MODEL})`);
});
