// Real-time solar wind at L1 (DSCOVR/ACE), propagated to Earth by SWPC.
// One compact product (last hour, 1-minute rows) feeds two instruments:
// speed and IMF Bz. The wind currently arriving takes ~1 h from L1 to Earth.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

const URL = 'https://services.swpc.noaa.gov/products/geospace/propagated-solar-wind-1-hour.json';
const SOURCE = { name: 'NOAA SWPC real-time solar wind', url: 'https://www.swpc.noaa.gov/products/real-time-solar-wind', license: 'public domain (US Gov)' };

async function loadRows(http) {
  const table = await http.json(URL);
  const [head, ...body] = table;
  const idx = Object.fromEntries(head.map((h, i) => [h, i]));
  const rows = body
    .map((r) => ({
      t: Date.parse(r[idx.time_tag]),
      speed: num(r[idx.speed]),
      density: num(r[idx.density]),
      temperature: num(r[idx.temperature]),
      bz: num(r[idx.bz]),
      bt: num(r[idx.bt]),
    }))
    .filter((r) => Number.isFinite(r.t))
    .sort((a, b) => a.t - b.t);
  if (!rows.length) throw new Error('no solar wind rows');
  return rows;
}

const lastWith = (rows, k) => [...rows].reverse().find((r) => r[k] != null);

export const solarWindSpeed = defineInstrument({
  id: 'solar-wind-speed',
  section: 'Vitals',
  title: 'Solar wind speed',
  unit: 'km/s',
  decimals: 0,
  cadence: '1h',
  history: 1440,
  source: SOURCE,
  // Common operational bands (SWPC discussion practice): ≥500 elevated, ≥700 high-speed, ≥900 extreme
  thresholds: [
    { level: 'critical', gte: 900 },
    { level: 'serious', gte: 700 },
    { level: 'warning', gte: 500 },
  ],
  higherIsWorse: true,
  describe: 'Speed of the charged-particle stream from the Sun as it reaches Earth; quiet wind is 300–400 km/s, and fast streams or CME shocks above ~500 km/s drive geomagnetic activity.',
  async fetch({ http, prev }) {
    const rows = await loadRows(http);
    const last = lastWith(rows, 'speed');
    if (!last) throw new Error('no speed values');
    const fresh = rows.filter((r) => r.speed != null).map((r) => [r.t, r.speed]);
    return {
      value: last.speed,
      at: new Date(last.t).toISOString(),
      series: [...(prev?.series || []), ...fresh],
      meta: { density_pcm3: last.density, temperature_K: last.temperature },
    };
  },
});

export const solarWindBz = defineInstrument({
  id: 'solar-wind-bz',
  section: 'Solar Wind',
  title: 'IMF Bz (GSM)',
  unit: 'nT',
  decimals: 1,
  cadence: '1h',
  history: 1440,
  source: SOURCE,
  // Southward (negative) Bz couples the solar wind into the magnetosphere; -10 nT sustained is storm-capable, -20 nT strong.
  thresholds: [
    { level: 'serious', lte: -20 },
    { level: 'warning', lte: -10 },
  ],
  higherIsWorse: false,
  describe: 'North–south component of the interplanetary magnetic field; when Bz turns strongly southward (negative) the solar wind connects to Earth’s field and geomagnetic storms follow.',
  async fetch({ http, prev }) {
    const rows = await loadRows(http);
    const last = lastWith(rows, 'bz');
    if (!last) throw new Error('no Bz values');
    const fresh = rows.filter((r) => r.bz != null).map((r) => [r.t, r.bz]);
    return {
      value: last.bz,
      at: new Date(last.t).toISOString(),
      series: [...(prev?.series || []), ...fresh],
      meta: { bt_nT: last.bt },
    };
  },
});
