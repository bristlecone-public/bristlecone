// npm registry download counts — the busiest software supply chain on the
// internet, and a decent proxy for "how much is the world building today".
//
// api.npmjs.org exposes a keyless downloads API. Omitting the package name
// gives the *whole registry* total:
//   /downloads/point/last-day          → { downloads, start, end }
//   /downloads/range/last-year         → { downloads: [{ day, downloads }, …] }
// Counts settle a day or two behind, and the pipeline occasionally emits a
// zero-download day when a stats run is missed — we drop those rather than
// draw a cliff.
//
// Docs: https://github.com/npm/registry/blob/main/docs/download-counts.md

import { defineInstrument } from '../framework/registry.js';

export const npmDownloads = defineInstrument({
  id: 'npm-downloads',
  section: 'Ecosystem',
  title: 'npm downloads',
  unit: '/day',
  decimals: 0,
  cadence: '6h',
  history: 365,
  // Counts settle a day or two (observed up to ~a week) behind, so the latest
  // data day is always well older than the default staleAfter (18h) — set it
  // wide enough that normal lag doesn't cry wolf but a genuinely dead feed does.
  staleAfter: '4d',
  source: {
    name: 'npm registry download counts',
    url: 'https://api.npmjs.org/downloads/point/last-day',
    license: 'npm public API',
  },
  higherIsWorse: false,
  describe:
    'Package downloads served by the npm registry in a day, whole registry — weekday peaks are roughly double the weekend, so read the shape, not one point.',
  async fetch({ http }) {
    const d = await http.json('https://api.npmjs.org/downloads/range/last-year');
    const series = (d?.downloads || [])
      .map((r) => [Date.parse(`${r.day}T00:00:00Z`), Number(r.downloads)])
      // zero days are pipeline gaps, not zero traffic
      .filter(([t, v]) => Number.isFinite(t) && Number.isFinite(v) && v > 0)
      .sort((a, b) => a[0] - b[0]);
    if (!series.length) throw new Error('npm range returned no usable days');
    const [t, v] = series[series.length - 1];
    return {
      value: v,
      at: new Date(t).toISOString(),
      series,
      meta: { days: series.length, gapsDropped: (d?.downloads?.length || 0) - series.length },
    };
  },
});
