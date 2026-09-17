// OVATION hemispheric power — how many gigawatts are being deposited into the
// northern auroral oval. Tabular text product, 5-minute cadence, one file per UTC
// day, so the series is stitched together across midnight by the collector.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

const URL = 'https://services.swpc.noaa.gov/text/aurora-nowcast-hemi-power.txt';

// "2026-08-17_13:05" → epoch ms (UTC)
const stamp = (s) => Date.parse(`${String(s).replace('_', 'T')}:00Z`);

export const auroraHemisphericPower = defineInstrument({
  id: 'aurora-hemispheric-power',
  section: 'Geomagnetic & Aurora',
  title: 'Auroral hemispheric power (north)',
  unit: 'GW',
  decimals: 0,
  cadence: '1h',
  history: 576, // two days at 5-minute resolution
  source: {
    name: 'NOAA SWPC OVATION aurora nowcast',
    url: 'https://www.swpc.noaa.gov/products/aurora-30-minute-forecast',
    license: 'public domain (US Gov)',
  },
  // Informal OVATION hemispheric-power bands used in SWPC's aurora guidance —
  // not one of the formal NOAA scales. ~50 GW is when the oval starts reaching
  // mid-latitudes; >100 GW is a strongly expanded oval.
  thresholds: [
    { level: 'critical', gte: 150 },
    { level: 'serious', gte: 100 },
    { level: 'warning', gte: 50 },
  ],
  higherIsWorse: true,
  describe:
    'Total power the solar wind is dumping into the northern auroral oval; tens of gigawatts is routine, and above roughly 50 GW the oval expands far enough south for aurora to be seen from mid-latitudes.',
  async fetch({ http, prev }) {
    const text = await http.text(URL);
    const rows = text
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith('#'))
      .map((l) => l.split(/\s+/))
      .filter((c) => c.length >= 4)
      .map((c) => ({ t: stamp(c[0]), forecastFor: c[1], north: num(c[2]), south: num(c[3]) }))
      .filter((r) => Number.isFinite(r.t))
      .sort((a, b) => a.t - b.t);
    const withNorth = rows.filter((r) => r.north != null);
    if (!withNorth.length) throw new Error('no hemispheric-power rows (all n/a?)');
    const last = withNorth[withNorth.length - 1];
    const fresh = withNorth.map((r) => [r.t, r.north]);
    return {
      value: last.north,
      at: new Date(last.t).toISOString(),
      series: [...(prev?.series || []), ...fresh],
      meta: {
        southGW: last.south,
        forecastValidAt: last.forecastFor ? new Date(stamp(last.forecastFor)).toISOString() : null,
        note: 'Value is a 30-minute-ahead OVATION nowcast issued at the observation time.',
      },
    };
  },
});
