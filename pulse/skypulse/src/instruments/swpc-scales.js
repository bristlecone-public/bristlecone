// NOAA space weather scales, current conditions.
// SWPC publishes R (radio blackout), S (solar radiation storm) and G (geomagnetic
// storm) levels 0–5 plus a three-day forecast in one small document. The headline
// number here is the worst level currently active across the three scales.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

const URL = 'https://services.swpc.noaa.gov/products/noaa-scales.json';

const scaleNum = (block) => {
  const n = num(block?.Scale);
  return n == null ? null : n;
};

export const noaaScales = defineInstrument({
  id: 'noaa-scales',
  section: 'Geomagnetic & Aurora',
  title: 'NOAA storm scale (worst of R/S/G)',
  unit: 'level',
  decimals: 0,
  cadence: '1h',
  history: 672, // one week at 15-minute resolution
  source: {
    name: 'NOAA SWPC space weather scales',
    url: 'https://www.swpc.noaa.gov/noaa-scales-explanation',
    license: 'public domain (US Gov)',
  },
  // The NOAA scales are themselves the accepted severity ladder: 1 = minor,
  // 3 = strong, 4 = severe, 5 = extreme.
  thresholds: [
    { level: 'critical', gte: 4 },
    { level: 'serious', gte: 3 },
    { level: 'warning', gte: 1 },
  ],
  higherIsWorse: true,
  describe:
    'The highest NOAA space weather scale level in force right now — R for radio blackouts, S for radiation storms, G for geomagnetic storms — on the same 1 (minor) to 5 (extreme) ladder SWPC uses in its public warnings.',
  async fetch({ http }) {
    const doc = await http.json(URL);
    const now = doc['0'];
    if (!now) throw new Error('no current-conditions block ("0") in noaa-scales.json');
    const r = scaleNum(now.R);
    const s = scaleNum(now.S);
    const g = scaleNum(now.G);
    const levels = [r, s, g].filter((v) => v != null);
    if (!levels.length) throw new Error('no R/S/G scale values');
    const at = `${now.DateStamp}T${now.TimeStamp}Z`;
    const day = (k) => {
      const d = doc[k];
      if (!d) return null;
      return {
        date: d.DateStamp,
        rMinorProb: num(d.R?.MinorProb),
        rMajorProb: num(d.R?.MajorProb),
        sProb: num(d.S?.Prob),
        gScale: num(d.G?.Scale),
        gText: d.G?.Text ?? null,
      };
    };
    return {
      value: Math.max(...levels),
      at: new Date(at).toISOString(),
      meta: {
        R: r, S: s, G: g,
        text: { R: now.R?.Text ?? null, S: now.S?.Text ?? null, G: now.G?.Text ?? null },
        forecast: [day('1'), day('2'), day('3')].filter(Boolean),
        yesterday: doc['-1'] ? { R: scaleNum(doc['-1'].R), S: scaleNum(doc['-1'].S), G: scaleNum(doc['-1'].G) } : null,
      },
    };
  },
});
