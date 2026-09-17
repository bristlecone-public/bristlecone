// Worker entry: cron → collect(); HTTP → JSON API + static dashboard.
//
// Routes (run_worker_first in wrangler.jsonc):
//   GET  /api/state                 combined dashboard document
//   GET  /api/instrument/:id        one snapshot (full series)
//   GET  /api/health                last collector runs + per-instrument age/errors
//   GET  /api/registry              instrument definitions (no data)
//   POST /api/collect?force=1&only=a,b   manual trigger; requires ADMIN_TOKEN
//                                    (Authorization: Bearer <token> header only)
// Everything else falls through to ./public via the ASSETS binding.

import { site } from './site.js';
import { instruments } from './instruments/index.js';
import { validateRegistry } from './framework/registry.js';
import { collect, buildState, publicInstrument } from './framework/collect.js';

validateRegistry(instruments);

const json = (data, status = 200, extra = {}) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', 'access-control-allow-origin': '*', ...extra },
  });

// Constant-time string comparison for the admin token. Equal-length guard, then
// XOR-accumulate every byte so total time can't leak how many leading bytes
// matched (plain `!==` short-circuits on the first mismatch). Empty inputs never
// match a non-empty token, and callers deny when env.ADMIN_TOKEN is unset.
function timingSafeEqual(a, b) {
  const enc = new TextEncoder();
  const ab = enc.encode(a || '');
  const bb = enc.encode(b || '');
  if (ab.length !== bb.length) return false;
  let diff = 0;
  for (let i = 0; i < ab.length; i++) diff |= ab[i] ^ bb[i];
  return diff === 0;
}

// Optional fan-out: Workers Free allows 5 cron triggers per account. Bind sibling
// workers as Service Bindings named PEER_* on ONE cron-bearing worker:
//   "services": [{ "binding": "PEER_ECONPULSE", "service": "econpulse" }, …]
// and every tick it POSTs /api/collect to each peer over the binding (no public
// HTTP; Worker→workers.dev fetches are blocked with error 1042). Peers verify the
// shared ADMIN_TOKEN and apply their own per-instrument cadence gating.
// PEER_FAN_UTC_HOURS (var, e.g. "0,6,12,18"): when set, fan out only on the :00 tick
// of the listed UTC hours — slow-moving peers otherwise wake (and spend a KV write)
// on every tick of this worker's cron.
async function pingPeers(env, now = Date.now()) {
  const peers = Object.keys(env).filter((k) => k.startsWith('PEER_') && typeof env[k]?.fetch === 'function');
  if (!peers.length || !env.ADMIN_TOKEN) return;
  if (env.PEER_FAN_UTC_HOURS) {
    const d = new Date(now);
    const hours = String(env.PEER_FAN_UTC_HOURS).split(',').map((x) => parseInt(x, 10));
    if (!hours.includes(d.getUTCHours()) || d.getUTCMinutes() !== 0) return;
  }
  await Promise.allSettled(peers.map((k) =>
    env[k].fetch('https://peer/api/collect', {
      method: 'POST',
      headers: { authorization: `Bearer ${env.ADMIN_TOKEN}` },
    }).catch(() => {}),
  ));
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(Promise.all([collect({ env, instruments, site }), pingPeers(env, event.scheduledTime)]));
  },

  async fetch(req, env) {
    const url = new URL(req.url);
    const p = url.pathname;

    if (p === '/api/state') {
      return json(await buildState({ env, instruments, site }));
    }
    if (p.startsWith('/api/instrument/')) {
      const id = p.slice('/api/instrument/'.length);
      const inst = instruments.find((i) => i.id === id);
      if (!inst) return json({ error: 'unknown instrument' }, 404);
      const state = await buildState({ env, instruments, site });
      return json({ instrument: publicInstrument(inst), snapshot: state.instruments?.[id] || null });
    }
    if (p === '/api/registry') return json({ site, instruments: instruments.map(publicInstrument) });
    if (p === '/api/health') {
      const state = await buildState({ env, instruments, site });
      const runlog = state.runlog || [];
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
      return json({ generatedAt: state.generatedAt || null, runs: runlog.slice(0, 10), instruments: rows });
    }
    if (p === '/api/collect') {
      // Header only — Cloudflare logs request URLs, so a ?token= query param would
      // leak the admin token into logs. Compared in constant time (see below).
      const tok = req.headers.get('authorization')?.replace(/^Bearer\s+/i, '') || '';
      if (!env.ADMIN_TOKEN || !timingSafeEqual(tok, env.ADMIN_TOKEN)) return json({ error: 'unauthorized' }, 401);
      const only = url.searchParams.get('only')?.split(',').filter(Boolean) || null;
      const force = url.searchParams.get('force') === '1';
      const { results } = await collect({ env, instruments, site, force, only });
      return json({ ok: true, results });
    }
    if (p.startsWith('/api/')) return json({ error: 'not found' }, 404);
    return env.ASSETS.fetch(req);
  },
};
