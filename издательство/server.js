'use strict';
/*
 * Универсальный потоковый прокси к LLM (OpenAI-совместимый формат: DeepSeek,
 * OpenAI, и т.п.). Ключ/провайдер/модель приходят в теле каждого запроса —
 * сервер ничего не хранит, только проксирует и стримит ответ во фронт.
 * Нужен, чтобы (а) обойти CORS и (б) не светить ключ в стороннюю выдачу.
 *
 * Запуск:  node server.js   →   http://localhost:8787
 * env: PORT (8787). Ключи задаются в интерфейсе студии, не здесь.
 */
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const PORT = process.env.PORT || 8787;
const ROOT = __dirname;
const MIME = { '.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.svg':'image/svg+xml',
  '.png':'image/png','.ico':'image/x-icon' };

function send(res, code, body, type='text/plain; charset=utf-8'){ res.writeHead(code,{'Content-Type':type}); res.end(body); }

function serveStatic(req, res){
  let rel = decodeURIComponent(req.url.split('?')[0]);
  if (rel === '/' || rel === '') rel = '/index.html';
  const fp = path.normalize(path.join(ROOT, rel));
  if (!fp.startsWith(ROOT)) return send(res, 403, 'Forbidden');
  fs.readFile(fp, (e, d) => e ? send(res,404,'Not found') : send(res,200,d,MIME[path.extname(fp)]||'application/octet-stream'));
}

async function handleGenerate(req, res){
  let raw=''; req.on('data',c=>{ raw+=c; if(raw.length>5e5) req.destroy(); });
  req.on('end', async ()=>{
    let b={}; try{ b=JSON.parse(raw||'{}'); }catch{}
    const apiKey = (b.apiKey||'').trim();
    const baseURL = (b.baseURL||'https://api.deepseek.com').replace(/\/+$/,'');
    const model = b.model || 'deepseek-chat';
    if(!apiKey) return send(res, 400, 'NO_KEY: не задан API-ключ для этого агента (откройте настройки агента или глобальные настройки).');
    let up;
    try{
      up = await fetch(`${baseURL}/chat/completions`, {
        method:'POST',
        headers:{ 'Content-Type':'application/json', 'Authorization':`Bearer ${apiKey}` },
        body: JSON.stringify({ model, messages:b.messages||[], stream:true,
          temperature: typeof b.temperature==='number'? b.temperature : 1.0 }),
      });
    }catch(e){ return send(res, 502, 'UPSTREAM_FAIL: '+e.message); }
    if(!up.ok || !up.body){ const t=await up.text().catch(()=> ''); return send(res, up.status||502, 'API_ERROR '+up.status+': '+t.slice(0,400)); }
    res.writeHead(200, { 'Content-Type':'text/plain; charset=utf-8', 'Cache-Control':'no-cache' });
    const reader=up.body.getReader(), dec=new TextDecoder(); let buf='';
    try{
      while(true){
        const {value,done}=await reader.read(); if(done) break;
        buf += dec.decode(value,{stream:true});
        const lines=buf.split('\n'); buf=lines.pop();
        for(const line of lines){
          const s=line.trim(); if(!s.startsWith('data:')) continue;
          const data=s.slice(5).trim(); if(data==='[DONE]') continue;
          try{ const d=JSON.parse(data).choices?.[0]?.delta?.content; if(d) res.write(d); }catch{}
        }
      }
    }catch{}
    res.end();
  });
}

http.createServer((req,res)=>{
  res.setHeader('Access-Control-Allow-Origin','*');
  res.setHeader('Access-Control-Allow-Headers','Content-Type');
  if(req.method==='OPTIONS') return send(res,204,'');
  if(req.method==='POST' && req.url==='/api/generate') return handleGenerate(req,res);
  if(req.method==='GET') return serveStatic(req,res);
  send(res,405,'Method not allowed');
}).listen(PORT, ()=>{
  console.log(`ИИ-Издательство → http://localhost:${PORT}`);
  console.log('Прокси готов. Ключи задаются в интерфейсе студии (Настройки).');
});
