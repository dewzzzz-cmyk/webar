'use strict';
/*
 * Лёгкий прокси для DeepSeek (без зависимостей).
 * Хранит ключ на сервере и стримит ответ модели во фронтенд.
 *
 * Запуск:
 *   DEEPSEEK_API_KEY=sk-... node server.js
 * затем открыть http://localhost:8787
 *
 * Переменные окружения:
 *   DEEPSEEK_API_KEY  — ключ (обязателен для реальной генерации)
 *   DEEPSEEK_MODEL    — модель (по умолчанию deepseek-chat)
 *   DEEPSEEK_BASE     — базовый URL (по умолчанию https://api.deepseek.com)
 *   PORT              — порт (по умолчанию 8787)
 */
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const PORT  = process.env.PORT || 8787;
const KEY   = process.env.DEEPSEEK_API_KEY || '';
const MODEL = process.env.DEEPSEEK_MODEL || 'deepseek-chat';
const BASE  = process.env.DEEPSEEK_BASE || 'https://api.deepseek.com';
const ROOT  = __dirname;

// Промты агентов. Реальным сейчас работает только 'chap', но таблица
// готова к подключению остальных узлов.
const PROMPTS = {
  idea:  'Ты генератор книжных концепций. Предложи одну свежую идею книги одной фразой на русском.',
  plot:  'Ты архитектор сюжета. Опиши структуру сюжета книги в 2–3 фразах на русском.',
  chap:  'Ты писатель художественной прозы на русском языке. По данной идее и структуре сюжета напиши яркий, атмосферный фрагмент начала первой главы: 4–6 предложений, живой язык, без заголовков и пояснений — только текст главы.',
  edit:  'Ты редактор-критик. Дай краткое резюме правок текста в 1–2 фразах на русском.',
  art:   'Ты арт-директор. Опиши визуальную концепцию иллюстраций книги в 1–2 фразах на русском.',
  cover: 'Ты дизайнер обложек. Опиши концепцию обложки книги в 1–2 фразах на русском.',
  pub:   'Ты издатель. Кратко подтверди выпуск книги в 1 фразе на русском.',
};

const MIME = {
  '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8',
  '.css':'text/css; charset=utf-8', '.json':'application/json; charset=utf-8',
  '.svg':'image/svg+xml', '.png':'image/png', '.ico':'image/x-icon',
};

function send(res, code, body, type='text/plain; charset=utf-8'){
  res.writeHead(code, { 'Content-Type': type });
  res.end(body);
}

function serveStatic(req, res){
  let rel = decodeURIComponent(req.url.split('?')[0]);
  if (rel === '/' || rel === '') rel = '/index.html';
  // защита от выхода за пределы каталога
  const fp = path.normalize(path.join(ROOT, rel));
  if (!fp.startsWith(ROOT)) return send(res, 403, 'Forbidden');
  fs.readFile(fp, (err, data) => {
    if (err) return send(res, 404, 'Not found');
    send(res, 200, data, MIME[path.extname(fp)] || 'application/octet-stream');
  });
}

function buildMessages(stage, context){
  const sys = PROMPTS[stage] || PROMPTS.chap;
  let user = 'Создай результат для этого этапа.';
  if (stage === 'chap') {
    user = `Идея книги: ${context?.idea || 'на твой выбор'}\n` +
           `Структура сюжета: ${context?.plot || 'на твой выбор'}\n\n` +
           `Напиши фрагмент начала первой главы.`;
  }
  return [
    { role: 'system', content: sys },
    { role: 'user',   content: user },
  ];
}

async function handleGenerate(req, res){
  if (!KEY) {
    return send(res, 503, 'DEEPSEEK_API_KEY не задан на сервере — узел работает в мок-режиме.');
  }
  let raw = '';
  req.on('data', c => { raw += c; if (raw.length > 1e5) req.destroy(); });
  req.on('end', async () => {
    let body = {};
    try { body = JSON.parse(raw || '{}'); } catch { /* ignore */ }
    const messages = buildMessages(body.stage, body.context);

    let upstream;
    try {
      upstream = await fetch(`${BASE}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${KEY}`,
        },
        body: JSON.stringify({ model: MODEL, messages, stream: true, temperature: 1.1 }),
      });
    } catch (e) {
      return send(res, 502, 'Не удалось подключиться к DeepSeek: ' + e.message);
    }
    if (!upstream.ok || !upstream.body) {
      const txt = await upstream.text().catch(() => '');
      return send(res, upstream.status || 502, 'DeepSeek ошибка: ' + txt.slice(0, 300));
    }

    // стримим только текстовые дельты во фронт
    res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-cache' });
    const reader = upstream.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        for (const line of lines) {
          const s = line.trim();
          if (!s.startsWith('data:')) continue;
          const data = s.slice(5).trim();
          if (data === '[DONE]') continue;
          try {
            const delta = JSON.parse(data).choices?.[0]?.delta?.content;
            if (delta) res.write(delta);
          } catch { /* частичная строка — пропускаем */ }
        }
      }
    } catch (e) {
      // соединение оборвалось — просто закрываем
    }
    res.end();
  });
}

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return send(res, 204, '');
  if (req.method === 'POST' && req.url === '/api/generate') return handleGenerate(req, res);
  if (req.method === 'GET') return serveStatic(req, res);
  send(res, 405, 'Method not allowed');
});

server.listen(PORT, () => {
  console.log(`AI Издательство → http://localhost:${PORT}`);
  console.log(`DeepSeek: ${KEY ? 'ключ найден, реальная генерация активна' : 'ключ НЕ задан — узлы в мок-режиме'} (модель ${MODEL})`);
});
