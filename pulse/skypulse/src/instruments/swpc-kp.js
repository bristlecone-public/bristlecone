// NOAA SWPC planetary K-index.
// Value: latest 1-minute *estimated* Kp (updates every minute).
// Series: official 3-hourly Kp for the last 7 days (merged with what we already hold).

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

const KP_1M = 'https://services.swpc.noaa.gov/json/planetary_k_index_1m.json';
const KP_3H = 'https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json';

const utc = (s) => new Date(String(s).replace(' ', 'T').replace(/Z?$/, 'Z')).toISOString();

export const kpPlanetary = defineInstrument({
  id: 'kp-planetary',
  section: 'Vitals',
  title: 'Planetary Kp index',
  unit: 'Kp',
  decimals: 2,
  cadence: '1h',
  history: 224, // 4 weeks of 3-hourly values
  source: { name: 'NOAA SWPC', url: 'https://www.swpc.noaa.gov/products/planetary-k-index', license: 'public domain (US Gov)' },
  // NOAA G-scale: Kp5=G1, 6=G2, 7=G3, 8=G4, 9=G5
  thresholds: [
    { level: 'critical', gte: 8 },
    { level: 'serious', gte: 7 },
    { level: 'warning', gte: 5 },
  ],
  higherIsWorse: true,
  describe: 'Global geomagnetic disturbance on the 0–9 Kp scale; Kp 5+ is a geomagnetic storm (NOAA G1) that can push aurora to mid-latitudes and disturb power grids and satellites.',
  async fetch({ http, prev }) {
    const [oneMin, threeHour] = await Promise.all([http.json(KP_1M), http.json(KP_3H)]);
    const latest = [...oneMin].filter((r) => num(r.estimated_kp) != null).sort((a, b) => Date.parse(utc(b.time_tag)) - Date.parse(utc(a.time_tag)))[0];
    if (!latest) throw new Error('no 1-minute Kp rows');
    const fresh = threeHour
      .map((r) => [Date.parse(utc(r.time_tag)), num(r.Kp)])
      .filter(([t, v]) => Number.isFinite(t) && v != null);
    const series = [...(prev?.series || []), ...fresh];
    return {
      value: num(latest.estimated_kp),
      at: utc(latest.time_tag),
      series,
      meta: { estimated: true, kpString: latest.kp, latestOfficial3h: fresh.at(-1)?.[1] ?? null },
    };
  },
});
