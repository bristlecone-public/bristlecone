// Cloudflare Radar — aggregate statistics from one of the largest views of
// internet traffic there is. Free to use, but every route needs an API token:
// create one at https://dash.cloudflare.com/profile/api-tokens with the
// "Account Analytics: Read" permission (that is what gates Radar read access)
// and set CLOUDFLARE_API_TOKEN. Without it these three cards say "needs key"
// and the rest of the dashboard carries on.
//
// API base: https://api.cloudflare.com/client/v4/radar/
// Docs:     https://developers.cloudflare.com/radar/
//
// ⚠ Written against the documented response shapes but NOT live-verified —
// no token was available when these were wired. Parsing is deliberately
// defensive about key names.

import { defineInstrument } from '../framework/registry.js';

const BASE = 'https://api.cloudflare.com/client/v4/radar';
const KEY = 'CLOUDFLARE_API_TOKEN';

async function radar(http, env, path, params = {}) {
  const qs = new URLSearchParams({ format: 'json', ...params }).toString();
  const d = await http.json(`${BASE}${path}?${qs}`, {
    headers: { authorization: `Bearer ${env[KEY]}`, accept: 'application/json' },
  });
  if (d && d.success === false) {
    throw new Error(`Radar ${path}: ${JSON.stringify(d.errors || d.messages).slice(0, 200)}`);
  }
  if (!d?.result) throw new Error(`Radar ${path}: no result in response`);
  // result_info (pagination totals) sits next to result, not inside it.
  return { ...d.result, result_info: d.result_info || null };
}

// Radar returns numbers as strings ("31.4") in summaries and series alike.
const n = (v) => {
  const x = Number(v);
  return Number.isFinite(x) ? x : null;
};

export const radarL7Attacks = defineInstrument({
  id: 'radar-l7-attacks',
  section: 'Vitals',
  title: 'HTTP attack traffic index',
  unit: 'index 0-1',
  decimals: 3,
  cadence: '1h',
  history: 168,
  needsKey: KEY,
  source: {
    name: 'Cloudflare Radar — Layer 7 attacks',
    url: 'https://radar.cloudflare.com/security-and-attacks',
    license: 'Cloudflare Radar terms',
  },
  higherIsWorse: true,
  describe:
    'Application-layer attack traffic mitigated across Cloudflare, min-max normalised over the trailing week (1.0 = the busiest hour of the last 7 days) — the internet\'s background hostility level.',
  async fetch({ http, env }) {
    const r = await radar(http, env, '/attacks/layer7/timeseries', { aggInterval: '1h', dateRange: '7d' });
    const s = r.serie_0 || r.serie0 || {};
    const ts = s.timestamps || [];
    const vs = s.values || [];
    const series = ts
      .map((t, i) => [Date.parse(t), n(vs[i])])
      .filter(([t, v]) => Number.isFinite(t) && v != null)
      .sort((a, b) => a[0] - b[0]);
    if (!series.length) throw new Error('empty layer7 timeseries');
    const [t, v] = series[series.length - 1];
    return {
      value: v,
      at: new Date(t).toISOString(),
      series,
      meta: { normalization: r.meta?.normalization, aggInterval: r.meta?.aggInterval },
    };
  },
});

export const radarBgpAnomalies = defineInstrument({
  id: 'radar-bgp-anomalies',
  section: 'Routing',
  title: 'BGP hijacks & route leaks (24 h)',
  unit: 'events',
  decimals: 0,
  cadence: '1h',
  history: 336,
  needsKey: KEY,
  source: {
    name: 'Cloudflare Radar — BGP anomaly detection',
    url: 'https://radar.cloudflare.com/routing',
    license: 'Cloudflare Radar terms',
  },
  higherIsWorse: true,
  describe:
    'Medium-or-better confidence BGP hijacks plus route leaks Cloudflare detected in the last 24 hours — routing is the internet\'s trust-by-default layer, and these are the moments it gets abused or fumbled.',
  async fetch({ http, env, now }) {
    // Radar rejects a dateEnd that is not strictly in the past (clock skew),
    // so end the window a minute short of now. We only need the pagination
    // totals, so ask for a single row.
    const dateEnd = new Date(now - 60_000).toISOString();
    const dateStart = new Date(now - 86_400_000).toISOString();
    const q = { dateStart, dateEnd, per_page: '1' };
    const [hijacks, allHijacks, leaks] = await Promise.all([
      // confidence 1-4 is noise; 5+ is what Radar's own routing page surfaces
      radar(http, env, '/bgp/hijacks/events', { ...q, minConfidence: '5' }),
      radar(http, env, '/bgp/hijacks/events', q),
      radar(http, env, '/bgp/leaks/events', q),
    ]);
    const count = (r) => {
      const total = r?.result_info?.total_count;
      return Number.isFinite(total) ? total : (r?.events || []).length;
    };
    const h = count(hijacks);
    const l = count(leaks);
    return {
      value: h + l,
      at: dateEnd,
      meta: { hijacks: h, hijacksAnyConfidence: count(allHijacks), leaks: l, windowHours: 24 },
    };
  },
});

export const radarHttp3Share = defineInstrument({
  id: 'radar-http3-share',
  section: 'Adoption',
  title: 'HTTP/3 share of requests',
  unit: '%',
  decimals: 1,
  cadence: '1h',
  history: 336,
  needsKey: KEY,
  source: {
    name: 'Cloudflare Radar — HTTP version summary',
    url: 'https://radar.cloudflare.com/adoption-and-usage',
    license: 'Cloudflare Radar terms',
  },
  higherIsWorse: false,
  describe:
    'Share of HTTP requests served over HTTP/3 (QUIC) rather than HTTP/1.x or HTTP/2 — how fast the transport layer of the web is actually being replaced.',
  async fetch({ http, env, now }) {
    const r = await radar(http, env, '/http/summary/http_version', { dateRange: '1d' });
    const s = r.summary_0 || {};
    const v = n(s['HTTP/3'] ?? s.HTTP3 ?? s.http3);
    if (v == null) throw new Error(`no HTTP/3 key in summary: ${Object.keys(s).join(',')}`);
    return {
      value: v,
      at: r.meta?.dateRange?.[0]?.endTime || new Date(now).toISOString(),
      meta: { 'HTTP/1.x': n(s['HTTP/1.x']), 'HTTP/2': n(s['HTTP/2']), lastUpdated: r.meta?.lastUpdated },
    };
  },
});
