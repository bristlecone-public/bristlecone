// Vast.ai public marketplace search — keyless GET, returns live rentable offers.
// Heavily rate limited (observed: ~1 request per minute per IP), so this file
// makes exactly ONE request and derives every GPU price from it.

import { defineInstrument } from '../framework/registry.js';

const GPUS = ['H100 SXM', 'RTX 4090'];

const query = encodeURIComponent(
  JSON.stringify({
    gpu_name: { in: GPUS },
    rentable: { eq: true },
    type: 'on-demand',
    order: [['dph_total', 'asc']],
    limit: 200,
  }),
);

export const gpuSpotPrice = defineInstrument({
  id: 'gpu-h100-spot',
  section: 'Usage & prices',
  title: 'Cheapest rentable H100',
  unit: '$/GPU-hr',
  decimals: 3,
  cadence: '6h',
  staleAfter: '12h', // effective cadence is the 6h fan-out, not 1h
  history: 720, // 30 days
  source: {
    name: 'Vast.ai marketplace',
    url: 'https://cloud.vast.ai/create/',
    license: 'public console API, keyless',
  },
  higherIsWorse: true,
  describe:
    'Lowest advertised on-demand price for one H100 SXM on Vast.ai — a floor set by whichever independent host is cheapest right now. Vast.ai is a decentralised marketplace of smaller and hobbyist hosts, so a single cheap listing can pull this down even when vetted enterprise capacity (CoreWeave, Lambda, the hyperscalers) is tight. Read it as directional pressure on the loose end of the GPU market, not a market-wide clearing price.',
  async fetch({ http, now }) {
    const d = await http.json(`https://console.vast.ai/api/v0/bundles/?q=${query}`);
    const offers = d?.offers;
    if (!Array.isArray(offers) || !offers.length) throw new Error('Vast.ai: no offers returned');

    const best = {};
    for (const o of offers) {
      const n = o.num_gpus || 1;
      const perGpu = Number(o.dph_total) / n;
      if (!Number.isFinite(perGpu) || perGpu <= 0) continue;
      const key = o.gpu_name;
      if (!best[key] || perGpu < best[key].usd) {
        best[key] = { usd: perGpu, gpus: n, geo: (o.geolocation || '').trim() || null };
      }
    }
    const h100 = best['H100 SXM'];
    if (!h100) throw new Error('Vast.ai: no rentable "H100 SXM" offers in result set');
    const consumer = best['RTX 4090'];

    return {
      value: h100.usd,
      at: new Date(now).toISOString(),
      meta: {
        offersScanned: offers.length,
        h100Location: h100.geo,
        rtx4090UsdPerHr: consumer ? Number(consumer.usd.toFixed(4)) : null,
      },
    };
  },
});
