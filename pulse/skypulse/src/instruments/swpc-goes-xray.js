// GOES long-wavelength (0.1–0.8 nm) X-ray flux — the flare gauge.
// 1-minute data, last 6 hours. Value shown in µW/m² so the R-scale thresholds
// (M1 = 10 µW/m², X1 = 100, X10 = 1000) are readable; the flare class is in meta.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

const URL = 'https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json';

export function flareClass(fluxWm2) {
  if (fluxWm2 == null || !(fluxWm2 > 0)) return null;
  const bands = [['A', 1e-8], ['B', 1e-7], ['C', 1e-6], ['M', 1e-5], ['X', 1e-4]];
  let letter = 'A';
  let base = 1e-8;
  for (const [l, b] of bands) if (fluxWm2 >= b) { letter = l; base = b; }
  const n = fluxWm2 / base;
  return `${letter}${n >= 10 ? n.toFixed(0) : n.toFixed(1)}`;
}

export const goesXrayFlux = defineInstrument({
  id: 'goes-xray-flux',
  section: 'Vitals',
  title: 'Solar X-ray flux (GOES 0.1–0.8 nm)',
  unit: 'µW/m²',
  decimals: 2,
  cadence: '1h',
  history: 1440, // one day at 1-minute resolution
  source: { name: 'NOAA SWPC / GOES', url: 'https://www.swpc.noaa.gov/products/goes-x-ray-flux', license: 'public domain (US Gov)' },
  // NOAA R-scale: M1 (1e-5 W/m²) = R1, X1 (1e-4) = R3, X10 (1e-3) = R4, X20 = R5
  thresholds: [
    { level: 'critical', gte: 1000 },
    { level: 'serious', gte: 100 },
    { level: 'warning', gte: 10 },
  ],
  higherIsWorse: true,
  describe: 'Soft X-ray output of the Sun measured by GOES; a jump to M-class (10 µW/m²) or X-class (100 µW/m²) is a solar flare that can black out HF radio on the sunlit side of Earth.',
  async fetch({ http, prev }) {
    const rows = await http.json(URL);
    const fresh = rows
      .filter((r) => r.energy === '0.1-0.8nm')
      .map((r) => [Date.parse(r.time_tag), num(r.flux)])
      .filter(([t, v]) => Number.isFinite(t) && v != null && v > 0)
      .map(([t, v]) => [t, v * 1e6]);
    if (!fresh.length) throw new Error('no 0.1-0.8nm rows');
    const [t, v] = fresh.at(-1);
    const peak = fresh.reduce((m, p) => (p[1] > m[1] ? p : m), fresh[0]);
    return {
      value: v,
      at: new Date(t).toISOString(),
      series: [...(prev?.series || []), ...fresh],
      meta: {
        class: flareClass(v / 1e6),
        fluxWm2: v / 1e6,
        peak6h: { class: flareClass(peak[1] / 1e6), at: new Date(peak[0]).toISOString() },
        satellite: rows.at(-1)?.satellite ?? null,
      },
    };
  },
});
