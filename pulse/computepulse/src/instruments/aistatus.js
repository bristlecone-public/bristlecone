// Provider health. Two different status-page vendors plus Google's own feed:
//   OpenAI, Anthropic  → Statuspage v2 JSON (/api/v2/status.json, /incidents.json)
//   Hugging Face       → BetterStack (index.json, aggregate_state)
//   Google Cloud       → bespoke incidents.json, filtered to AI products
// All keyless. Statuspage asks that you not poll faster than once a minute.

import { defineInstrument } from '../framework/registry.js';

const STATUSPAGE = [
  { name: 'OpenAI', base: 'https://status.openai.com' },
  { name: 'Anthropic', base: 'https://status.anthropic.com' },
];
const HF_STATUS = 'https://status.huggingface.co/index.json';
const GCP_INCIDENTS = 'https://status.cloud.google.com/incidents.json';
const GCP_AI = /vertex|gemini|generative|\bai\b|tpu/i;

// Statuspage "impact" and Google "severity" both map onto our four levels.
const IMPACT = { critical: 'critical', major: 'serious', minor: 'warning', maintenance: 'info', none: 'info' };
const GSEV = { high: 'serious', medium: 'warning', low: 'info' };

export const aiProvidersDegraded = defineInstrument({
  id: 'ai-providers-degraded',
  section: 'Vitals',
  title: 'AI providers reporting degradation',
  unit: 'of 3',
  decimals: 0,
  cadence: '6h',
  // Empty cron: driven by the 6-hourly fan-out, so this refreshes every ~6h
  // rather than every 15m. Without this the healthy card would read "stale"
  // for most of each cycle (default staleAfter would be 2h).
  staleAfter: '12h',
  history: 288, // 3 days
  source: {
    name: 'OpenAI / Anthropic / Hugging Face status pages',
    url: 'https://status.openai.com/',
    license: 'public status endpoints',
  },
  // Not a domain scale — just "how many of the three are unhappy right now".
  thresholds: [
    { level: 'serious', gte: 2 },
    { level: 'warning', gte: 1 },
  ],
  higherIsWorse: true,
  describe:
    'How many of OpenAI, Anthropic and Hugging Face are currently self-reporting anything other than fully operational.',
  async fetch({ http, now }) {
    const states = {};

    await Promise.all([
      ...STATUSPAGE.map(async (p) => {
        try {
          const d = await http.json(`${p.base}/api/v2/status.json`);
          states[p.name] = d?.status?.indicator === 'none' ? 'operational' : (d?.status?.description || d?.status?.indicator || 'unknown');
        } catch {
          states[p.name] = null;
        }
      }),
      (async () => {
        try {
          const d = await http.json(HF_STATUS);
          states['Hugging Face'] = d?.data?.attributes?.aggregate_state || 'unknown';
        } catch {
          states['Hugging Face'] = null;
        }
      })(),
    ]);

    const reporting = Object.entries(states).filter(([, v]) => v != null);
    if (!reporting.length) throw new Error('no AI status page answered');
    const degraded = reporting.filter(([, v]) => v !== 'operational');

    return {
      value: degraded.length,
      at: new Date(now).toISOString(),
      meta: {
        checked: reporting.length,
        ...Object.fromEntries(reporting),
      },
    };
  },
});

export const aiIncidents = defineInstrument({
  id: 'ai-incidents',
  section: 'Incidents',
  kind: 'events',
  title: 'AI platform incidents',
  cadence: '6h',
  staleAfter: '12h', // effective cadence is the 6h fan-out, not 15m
  history: 120,
  source: {
    name: 'OpenAI / Anthropic / Google Cloud status pages',
    url: 'https://status.anthropic.com/',
    license: 'public status endpoints',
  },
  describe:
    'Every incident the big model providers have opened on their own status pages, newest first, with their own severity rating.',
  async fetch({ http }) {
    const items = [];

    await Promise.all([
      ...STATUSPAGE.map(async (p) => {
        try {
          const d = await http.json(`${p.base}/api/v2/incidents.json`);
          for (const inc of (d?.incidents || []).slice(0, 25)) {
            const at = Date.parse(inc.started_at || inc.created_at);
            if (!Number.isFinite(at)) continue;
            items.push({
              id: `${p.name}:${inc.id}`,
              at: new Date(at).toISOString(),
              title: `${p.name} — ${inc.name}`,
              url: inc.shortlink || `${p.base}/incidents/${inc.id}`,
              severity: IMPACT[inc.impact] || 'warning',
              meta: { status: inc.status, impact: inc.impact },
            });
          }
        } catch { /* one page down must not blank the wall */ }
      }),
      (async () => {
        try {
          const d = await http.json(GCP_INCIDENTS);
          for (const inc of (Array.isArray(d) ? d : []).slice(0, 400)) {
            const products = (inc.affected_products || []).map((p) => p.title || '');
            if (!products.some((t) => GCP_AI.test(t))) continue;
            const at = Date.parse(inc.begin);
            if (!Number.isFinite(at)) continue;
            items.push({
              id: `gcp:${inc.id}`,
              at: new Date(at).toISOString(),
              title: `Google Cloud — ${inc.external_desc}`.slice(0, 240),
              url: `https://status.cloud.google.com/${inc.uri}`,
              severity: GSEV[inc.severity] || 'warning',
              meta: { products: products.join(', ').slice(0, 120), open: !inc.end },
            });
          }
        } catch { /* ditto */ }
      })(),
    ]);

    if (!items.length) throw new Error('no incident feed answered');
    return { items };
  },
});
