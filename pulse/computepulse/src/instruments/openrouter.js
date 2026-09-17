// OpenRouter public model catalogue — keyless JSON, one endpoint, ~400 models
// with live per-token pricing from every provider they route to.

import { defineInstrument } from '../framework/registry.js';

const MODELS_URL = 'https://openrouter.ai/api/v1/models';
const LONG_CTX = 128_000;

const price = (m) => {
  const p = Number(m?.pricing?.prompt);
  return Number.isFinite(p) ? p : null;
};

export const openrouterModels = defineInstrument({
  id: 'openrouter-models',
  section: 'Models',
  title: 'Models routable on OpenRouter',
  unit: 'models',
  decimals: 0,
  cadence: '6h',
  history: 240, // 60 days
  source: {
    name: 'OpenRouter',
    url: 'https://openrouter.ai/api/v1/models',
    license: 'public API, keyless',
  },
  higherIsWorse: false,
  describe:
    'How many distinct LLMs are commercially servable through a single aggregator right now — a proxy for how crowded the inference market has become.',
  async fetch({ http, now }) {
    const d = await http.json(MODELS_URL);
    const rows = d?.data;
    if (!Array.isArray(rows) || !rows.length) throw new Error('OpenRouter: empty model list');
    const free = rows.filter((m) => price(m) === 0).length;
    const longCtx = rows.filter((m) => (m.context_length || 0) >= LONG_CTX).length;
    const multimodal = rows.filter((m) => (m.architecture?.input_modalities || []).length > 1).length;
    const newest = rows
      .filter((m) => Number.isFinite(m.created))
      .sort((a, b) => b.created - a.created)[0];
    return {
      value: rows.length,
      at: new Date(now).toISOString(),
      meta: {
        free,
        longContext: longCtx,
        multimodal,
        newest: newest ? `${newest.id} (${new Date(newest.created * 1000).toISOString().slice(0, 10)})` : null,
      },
    };
  },
});

export const openrouterLongCtxPrice = defineInstrument({
  id: 'openrouter-price-longctx',
  section: 'Usage & prices',
  title: 'Median input price, long-context models',
  unit: '$/M tokens',
  decimals: 3,
  cadence: '6h',
  history: 240,
  source: {
    name: 'OpenRouter',
    url: 'https://openrouter.ai/models',
    license: 'public API, keyless',
  },
  higherIsWorse: true,
  describe:
    'Median list price to send a million input tokens to a paid model with at least a 128k context window — the going rate for serious LLM work.',
  async fetch({ http, now }) {
    const d = await http.json(MODELS_URL);
    const rows = d?.data;
    if (!Array.isArray(rows) || !rows.length) throw new Error('OpenRouter: empty model list');
    const paid = rows
      .filter((m) => (m.context_length || 0) >= LONG_CTX && price(m) > 0)
      .map((m) => ({ id: m.id, usdPerM: price(m) * 1e6 }))
      .sort((a, b) => a.usdPerM - b.usdPerM);
    if (!paid.length) throw new Error('OpenRouter: no paid long-context models found');
    const median = paid[Math.floor(paid.length / 2)].usdPerM;
    return {
      value: median,
      at: new Date(now).toISOString(),
      meta: {
        n: paid.length,
        cheapest: `${paid[0].id} @ $${paid[0].usdPerM.toFixed(3)}`,
        dearest: `${paid[paid.length - 1].id} @ $${paid[paid.length - 1].usdPerM.toFixed(2)}`,
        contextFloor: LONG_CTX,
      },
    };
  },
});
