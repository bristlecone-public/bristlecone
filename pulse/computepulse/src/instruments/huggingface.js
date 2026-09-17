// Hugging Face Hub API — keyless, JSON, documented at https://huggingface.co/docs/hub/api
// Rate limit observed: 500 requests / 5 min per IP ("ratelimit-policy" header).

import { defineInstrument } from '../framework/registry.js';

const API = 'https://huggingface.co/api';
const HUB = 'https://huggingface.co';

// Orgs whose releases move the field. Used for the "lab releases" wall.
const NOTABLE_ORGS = [
  'meta-llama', 'google', 'mistralai', 'Qwen', 'deepseek-ai', 'microsoft',
  'openai', 'anthropic', 'nvidia', 'allenai', 'xai-org', 'moonshotai', 'zai-org',
];

const MAX_PAGES = 12; // 1000 models/page; ~4-5 h of Hub traffic per page

export const hfNewModels = defineInstrument({
  id: 'hf-new-models-24h',
  section: 'Vitals',
  title: 'New models published on Hugging Face',
  unit: 'models/24h',
  decimals: 0,
  cadence: '6h',
  // Real runner is gridpulse's 6-hourly PEERS fan-out (empty cron), so the
  // observation refreshes every ~6h, not hourly. Keep the card "fresh" up to
  // one missed fan-out; only flag stale past two cycles.
  staleAfter: '12h',
  history: 720, // 30 days of hourly points
  source: {
    name: 'Hugging Face Hub API',
    url: 'https://huggingface.co/api/models?sort=createdAt&direction=-1',
    license: 'Hub metadata, free/keyless API',
  },
  higherIsWorse: false,
  describe:
    'Model repositories created on the Hugging Face Hub in the last 24 hours — the broadest available pulse of how fast open model publishing is moving.',
  async fetch({ http, now }) {
    const cutoff = now - 24 * 3600_000;
    let url = `${API}/models?sort=createdAt&direction=-1&limit=1000`;
    let count = 0;
    let pages = 0;
    let oldest = null;
    let reachedCutoff = false;

    while (url && pages < MAX_PAGES) {
      const res = await http.raw(url);
      const batch = await res.json();
      pages++;
      if (!Array.isArray(batch) || !batch.length) { reachedCutoff = true; break; }
      for (const m of batch) {
        const t = Date.parse(m.createdAt);
        if (!Number.isFinite(t)) continue;
        if (t >= cutoff) count++;
        oldest = t;
      }
      if (oldest != null && oldest < cutoff) { reachedCutoff = true; break; }
      const next = /<([^>]+)>;\s*rel="next"/.exec(res.headers.get('link') || '');
      url = next ? next[1] : null;
      if (!url) { reachedCutoff = true; break; }
    }
    if (!pages) throw new Error('Hugging Face: no pages returned');

    return {
      value: count,
      at: new Date(now).toISOString(),
      meta: {
        pages,
        perHour: Math.round(count / 24),
        // true = the Hub produced more models in 24 h than MAX_PAGES could cover,
        // so `value` is a floor rather than an exact count.
        truncated: !reachedCutoff,
        oldestScanned: oldest ? new Date(oldest).toISOString() : null,
      },
    };
  },
});

export const hfLabReleases = defineInstrument({
  id: 'hf-lab-releases',
  section: 'Models',
  kind: 'events',
  title: 'Latest model releases from major labs',
  cadence: '6h',
  staleAfter: '12h', // effective cadence is the 6h fan-out; tolerate one missed cycle
  history: 120,
  source: {
    name: 'Hugging Face Hub API',
    url: 'https://huggingface.co/models?sort=created',
    license: 'Hub metadata, free/keyless API',
  },
  describe:
    'The newest public model repos from the labs that set the frontier (Meta, Google, Qwen, DeepSeek, Mistral, NVIDIA, AI2, xAI, Moonshot, Z.ai and friends).',
  async fetch({ http }) {
    const results = await Promise.all(
      NOTABLE_ORGS.map(async (org) => {
        try {
          return await http.json(
            `${API}/models?author=${encodeURIComponent(org)}&sort=createdAt&direction=-1&limit=3`,
          );
        } catch {
          return [];
        }
      }),
    );
    const items = [];
    for (const batch of results) {
      if (!Array.isArray(batch)) continue;
      for (const m of batch) {
        const at = Date.parse(m.createdAt);
        if (!Number.isFinite(at)) continue;
        items.push({
          id: `hf:${m.id}`,
          at: new Date(at).toISOString(),
          title: m.id,
          url: `${HUB}/${m.id}`,
          severity: 'info',
          meta: {
            likes: m.likes ?? 0,
            downloads: m.downloads ?? 0,
            task: m.pipeline_tag || null,
          },
        });
      }
    }
    if (!items.length) throw new Error('Hugging Face: no lab releases returned');
    return { items };
  },
});

export const hfDailyPapers = defineInstrument({
  id: 'hf-daily-papers',
  section: 'Research',
  kind: 'events',
  title: 'Papers of the day',
  cadence: '6h',
  history: 120,
  source: {
    name: 'Hugging Face Daily Papers',
    url: 'https://huggingface.co/papers',
    license: 'Hub metadata, free/keyless API',
  },
  describe:
    'The arXiv preprints the ML community is actually upvoting today — a curated counterweight to raw submission volume.',
  async fetch({ http }) {
    const rows = await http.json(`${API}/daily_papers?limit=30`);
    const items = [];
    for (const row of rows || []) {
      const p = row.paper || {};
      const at = Date.parse(row.publishedAt || p.publishedAt);
      if (!p.id || !Number.isFinite(at)) continue;
      items.push({
        id: `arxiv:${p.id}`,
        at: new Date(at).toISOString(),
        title: p.title || row.title || p.id,
        url: `${HUB}/papers/${p.id}`,
        severity: 'info',
        meta: { upvotes: p.upvotes ?? 0, comments: row.numComments ?? 0 },
      });
    }
    if (!items.length) throw new Error('Hugging Face: daily_papers returned nothing usable');
    return { items };
  },
});
