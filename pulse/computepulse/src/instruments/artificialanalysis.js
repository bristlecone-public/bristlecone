// Artificial Analysis — the closest thing to a neutral, continuously-updated
// cross-model benchmark. Requires a free API key (x-api-key header); the
// instrument is skipped entirely until ARTIFICIAL_ANALYSIS_API_KEY is set.
//
// ⚠ Not live-verified: the endpoint answers 401 without a key, which confirms
// it exists and is keyed, but the response field names below are from the v2
// docs and have not been exercised against a real payload.

import { defineInstrument } from '../framework/registry.js';

const URL = 'https://artificialanalysis.ai/api/v2/data/llms/models';

const numOrNull = (v) => (Number.isFinite(Number(v)) ? Number(v) : null);

// Field names drift between API versions; find by shape rather than by literal.
function pick(obj, re) {
  if (!obj || typeof obj !== 'object') return null;
  for (const [k, v] of Object.entries(obj)) if (re.test(k)) { const n = numOrNull(v); if (n != null) return n; }
  return null;
}

export const aaIntelligenceIndex = defineInstrument({
  id: 'aa-intelligence-index',
  section: 'Frontier & benchmarks',
  title: 'Top Intelligence Index score',
  unit: 'index',
  decimals: 1,
  cadence: '6h',
  history: 240,
  needsKey: 'ARTIFICIAL_ANALYSIS_API_KEY',
  source: {
    name: 'Artificial Analysis',
    url: 'https://artificialanalysis.ai/',
    license: 'free API key required; see their terms for redistribution limits',
  },
  higherIsWorse: false,
  describe:
    'Best score any model currently posts on the Artificial Analysis Intelligence Index, a composite of reasoning, coding and knowledge benchmarks — the single number that tracks the capability frontier.',
  async fetch({ http, env, now }) {
    const d = await http.json(URL, {
      headers: { 'x-api-key': env.ARTIFICIAL_ANALYSIS_API_KEY },
    });
    const rows = Array.isArray(d) ? d : d?.data;
    if (!Array.isArray(rows) || !rows.length) throw new Error('Artificial Analysis: empty model list');

    const scored = rows
      .map((m) => ({
        name: m.name || m.slug || m.id,
        creator: m.model_creator?.name || m.model_creator || null,
        index: pick(m.evaluations, /intelligence.*index/i) ?? pick(m, /intelligence.*index/i),
        usdPerM: pick(m.pricing, /blended/i) ?? pick(m.pricing, /input/i),
      }))
      .filter((m) => m.index != null)
      .sort((a, b) => b.index - a.index);
    if (!scored.length) throw new Error('Artificial Analysis: no intelligence-index field found on any model');

    const top = scored[0];
    const cheapestOfTop10 = scored
      .slice(0, 10)
      .filter((m) => m.usdPerM != null)
      .sort((a, b) => a.usdPerM - b.usdPerM)[0];

    return {
      value: top.index,
      at: new Date(now).toISOString(),
      meta: {
        model: top.name,
        creator: top.creator,
        modelsScored: scored.length,
        cheapestTop10: cheapestOfTop10 ? `${cheapestOfTop10.name} @ $${cheapestOfTop10.usdPerM}/M` : null,
      },
    };
  },
});
