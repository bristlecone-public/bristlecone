// Run the collector in plain Node (no wrangler, no KV) — an in-memory KV shim
// backed by ./data/kv.json so repeated runs accumulate series locally.
//
//   node scripts/collect-local.mjs               run all due instruments
//   node scripts/collect-local.mjs --force        ignore cadence
//   node scripts/collect-local.mjs --only a,b     subset
//   node scripts/collect-local.mjs --serve        also serve public/ + /api on :8787
//   node scripts/collect-local.mjs --serve --port 8790   (or PORT=8790) — siblings collide on 8787
//   node scripts/collect-local.mjs --serve --loop 5m     collect at start + every 5m, then keep serving
//                                                        (self-hosted mode: one long-running process)
//
// Env vars are read from .dev.vars (KEY=value lines) if present.

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { createServer } from 'node:http';
import { extname, join } from 'node:path';
import { site } from '../src/site.js';
import { instruments } from '../src/instruments/index.js';
import { collect, buildState, publicInstrument } from '../src/framework/collect.js';
import { validateRegistry, parseCadence } from '../src/framework/registry.js';

validateRegistry(instruments);

const args = process.argv.slice(2);
const flag = (n) => args.includes(n);
const opt = (n) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : null; };
const PORT = Number(opt('--port') || process.env.PORT || 8787);

mkdirSync('data', { recursive: true });
const KV_PATH = 'data/kv.json';
const store = existsSync(KV_PATH) ? JSON.parse(readFileSync(KV_PATH, 'utf8')) : {};
const kv = {
  async get(k, type) { const v = store[k]; return v == null ? null : type === 'json' ? JSON.parse(v) : v; },
  async put(k, v) { store[k] = v; writeFileSync(KV_PATH, JSON.stringify(store, null, 1)); },
};

const env = { SNAPSHOTS: kv, ...process.env };
if (existsSync('.dev.vars')) {
  for (const line of readFileSync('.dev.vars', 'utf8').split(/\r?\n/)) {
    const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/.exec(line);
    if (m) env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}

async function runCollect(force) {
  const only = opt('--only')?.split(',') || null;
  const { results } = await collect({ env, instruments, site, force, only });
  for (const r of results) {
    if (r.skipped === 'not due') continue;
    const tag = r.skipped ? `skip (${r.skipped})` : r.ok ? `ok ${r.ms}ms → ${r.value}` : `FAIL ${r.error}`;
    console.log(`${new Date().toISOString()} ${r.id.padEnd(28)} ${tag}`);
  }
}

if (!flag('--serve') || flag('--collect') || opt('--loop')) await runCollect(flag('--force'));

if (flag('--serve') && opt('--loop')) {
  const ms = parseCadence(opt('--loop'));
  setInterval(() => runCollect(false).catch((e) => console.error('collect error:', e.message)), ms);
  console.log(`looping collect every ${opt('--loop')}`);
}

if (flag('--serve')) {
  const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json', '.png': 'image/png' };
  createServer(async (req, res) => {
    const url = new URL(req.url, 'http://x');
    const send = (code, body, type = 'application/json') => { res.writeHead(code, { 'content-type': type }); res.end(body); };
    if (url.pathname === '/api/state') return send(200, JSON.stringify(await buildState({ env, instruments, site })));
    if (url.pathname === '/api/registry') return send(200, JSON.stringify({ site, instruments: instruments.map(publicInstrument) }));
    if (url.pathname.startsWith('/api/instrument/')) {
      const id = url.pathname.slice('/api/instrument/'.length);
      const inst = instruments.find((i) => i.id === id);
      if (!inst) return send(404, '{"error":"unknown"}');
      const state = await buildState({ env, instruments, site });
      return send(200, JSON.stringify({ instrument: publicInstrument(inst), snapshot: state.instruments?.[id] || null }));
    }
    if (url.pathname === '/api/health') {
      const state = await buildState({ env, instruments, site });
      const now = Date.now();
      const rows = instruments.map((i) => {
        const s = state.instruments?.[i.id] || {};
        return {
          id: i.id, cadence: i.cadence, status: s.status,
          dataAgeMin: s.at ? Math.round((now - Date.parse(s.at)) / 60000) : null,
          fetchAgeMin: s.fetchedAt ? Math.round((now - Date.parse(s.fetchedAt)) / 60000) : null,
          errorCount: s.errorCount || 0, lastError: s.lastError || null, skipped: s.skipped || null,
        };
      });
      return send(200, JSON.stringify({ generatedAt: state.generatedAt || null, runs: (state.runlog || []).slice(0, 10), instruments: rows }));
    }
    if (url.pathname === '/api/collect') {
      const { results } = await collect({ env, instruments, site, force: url.searchParams.get('force') === '1' });
      return send(200, JSON.stringify({ ok: true, results }));
    }
    let file = join('public', url.pathname === '/' ? 'index.html' : url.pathname);
    if (!existsSync(file)) file = 'public/index.html';
    send(200, readFileSync(file), MIME[extname(file)] || 'application/octet-stream');
  }).listen(PORT, () => console.log(`serving http://localhost:${PORT}`));
}
