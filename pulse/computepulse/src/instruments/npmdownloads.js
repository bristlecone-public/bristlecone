// npm registry download counts — keyless, no rate limit published.
// The /range/ endpoint hands back a full month of daily numbers, so we can
// publish a real 7-day-rolling series instead of waiting weeks for one to grow.

import { defineInstrument } from '../framework/registry.js';

const PACKAGES = ['openai', '@anthropic-ai/sdk', '@google/genai', 'langchain', 'ai'];
const RANGE = 'https://api.npmjs.org/downloads/range/last-month/';

export const npmAiSdkDownloads = defineInstrument({
  id: 'npm-ai-sdk-downloads',
  section: 'Ecosystem',
  title: 'AI SDK downloads from npm',
  unit: 'downloads/week',
  decimals: 0,
  cadence: '1d',
  // npm's download API trails real time by a couple of days, and `at` is the
  // last day of the last complete 7-day rolling window, so the data age is
  // legitimately several days. Allow for that lag before flagging stale.
  staleAfter: '7d',
  history: 400,
  source: {
    name: 'npm registry download API',
    url: 'https://github.com/npm/registry/blob/master/docs/download-counts.md',
    license: 'public API, keyless',
  },
  higherIsWorse: false,
  describe:
    'Combined weekly npm installs of the five SDKs most JavaScript apps use to call a model (OpenAI, Anthropic, Google GenAI, LangChain, Vercel AI) — a demand signal from the builder side rather than the lab side.',
  async fetch({ http, prev }) {
    const daily = new Map(); // 'YYYY-MM-DD' -> total downloads
    const perPackage = {};
    let ok = 0;

    await Promise.all(
      PACKAGES.map(async (pkg) => {
        let d;
        try {
          d = await http.json(RANGE + pkg);
        } catch {
          perPackage[pkg] = null;
          return;
        }
        const rows = d?.downloads;
        if (!Array.isArray(rows) || !rows.length) { perPackage[pkg] = null; return; }
        ok++;
        for (const r of rows) daily.set(r.day, (daily.get(r.day) || 0) + (r.downloads || 0));
        perPackage[pkg] = rows.slice(-7).reduce((s, r) => s + (r.downloads || 0), 0);
      }),
    );
    if (!ok) throw new Error('npm: no package ranges fetched');
    if (ok < PACKAGES.length && !daily.size) throw new Error('npm: all package ranges empty');

    // 7-day rolling sums over contiguous days only.
    const days = [...daily.keys()].sort();
    const points = [];
    for (let i = 6; i < days.length; i++) {
      if (Date.parse(days[i]) - Date.parse(days[i - 6]) !== 6 * 86_400_000) continue;
      let sum = 0;
      for (let k = i - 6; k <= i; k++) sum += daily.get(days[k]);
      points.push([Date.parse(days[i]), sum]);
    }
    if (!points.length) throw new Error('npm: not enough contiguous days for a weekly total');

    const last = points[points.length - 1];
    return {
      // Carry the previous series forward: the API only exposes ~30 days, but
      // the collector dedupes by timestamp so history accumulates past that.
      series: [...(prev?.series || []), ...points],
      value: last[1],
      at: new Date(last[0] + 86_399_000).toISOString(),
      meta: { packages: ok, ...perPackage },
    };
  },
});
