// GOES integral particle fluxes — the two radiation-environment gauges.
//   protons  ≥10 MeV  → NOAA S-scale (solar radiation storms, polar HF, aviation)
//   electrons ≥2 MeV  → satellite internal charging (SWPC alerts at 1,000 pfu)
// Both come from the 6-hour products (small payloads, 5-minute rows); the series
// accumulates locally so the sparkline covers days, not hours.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

const PROTONS = 'https://services.swpc.noaa.gov/json/goes/primary/integral-protons-6-hour.json';
const ELECTRONS = 'https://services.swpc.noaa.gov/json/goes/primary/integral-electrons-6-hour.json';

function pick(rows, energy) {
  return rows
    .filter((r) => r.energy === energy)
    .map((r) => ({ t: Date.parse(r.time_tag), v: num(r.flux), sat: r.satellite }))
    .filter((r) => Number.isFinite(r.t) && r.v != null && r.v >= 0)
    .sort((a, b) => a.t - b.t);
}

export const protonFlux10MeV = defineInstrument({
  id: 'proton-flux-10mev',
  section: 'Radiation',
  title: 'Proton flux ≥10 MeV',
  unit: 'pfu',
  decimals: 2,
  cadence: '1h',
  history: 2016, // one week at 5-minute resolution
  source: {
    name: 'NOAA SWPC / GOES integral protons',
    url: 'https://www.swpc.noaa.gov/products/goes-proton-flux',
    license: 'public domain (US Gov)',
  },
  // NOAA S-scale is defined directly on this quantity:
  // S1 = 10 pfu, S2 = 100, S3 = 1,000, S4 = 10,000, S5 = 100,000.
  thresholds: [
    { level: 'critical', gte: 1000 },
    { level: 'serious', gte: 100 },
    { level: 'warning', gte: 10 },
  ],
  higherIsWorse: true,
  describe:
    'Flux of ≥10 MeV solar protons at geostationary orbit; crossing 10 particle-flux-units is a NOAA S1 radiation storm, which blacks out HF radio over the poles and adds radiation dose on polar flights.',
  async fetch({ http, prev }) {
    const rows = await http.json(PROTONS);
    const p10 = pick(rows, '>=10 MeV');
    if (!p10.length) throw new Error('no ">=10 MeV" proton rows');
    const last = p10[p10.length - 1];
    const latestOf = (e) => pick(rows, e).at(-1)?.v ?? null;
    return {
      value: last.v,
      at: new Date(last.t).toISOString(),
      series: [...(prev?.series || []), ...p10.map((r) => [r.t, r.v])],
      meta: {
        satellite: last.sat ?? null,
        flux_ge_1MeV: latestOf('>=1 MeV'),
        flux_ge_50MeV: latestOf('>=50 MeV'),
        flux_ge_100MeV: latestOf('>=100 MeV'),
        peak6h: Math.max(...p10.map((r) => r.v)),
      },
    };
  },
});

export const electronFlux2MeV = defineInstrument({
  id: 'electron-flux-2mev',
  section: 'Radiation',
  title: 'Electron flux ≥2 MeV',
  unit: 'pfu',
  decimals: 0,
  cadence: '1h',
  history: 2016,
  source: {
    name: 'NOAA SWPC / GOES integral electrons',
    url: 'https://www.swpc.noaa.gov/products/goes-electron-flux',
    license: 'public domain (US Gov)',
  },
  // SWPC issues its ALTEF3 alert when the 2 MeV integral flux exceeds 1,000 pfu,
  // the level at which deep-dielectric charging risk to satellites becomes real.
  thresholds: [
    { level: 'serious', gte: 10000 },
    { level: 'warning', gte: 1000 },
  ],
  higherIsWorse: true,
  describe:
    'Flux of ≥2 MeV electrons in the outer radiation belt; sustained values above 1,000 pfu (SWPC’s alert level) build up charge deep inside satellites and are a known cause of on-orbit anomalies.',
  async fetch({ http, prev }) {
    const rows = await http.json(ELECTRONS);
    const e2 = pick(rows, '>=2 MeV');
    if (!e2.length) throw new Error('no ">=2 MeV" electron rows');
    const last = e2[e2.length - 1];
    return {
      value: last.v,
      at: new Date(last.t).toISOString(),
      series: [...(prev?.series || []), ...e2.map((r) => [r.t, r.v])],
      meta: { satellite: last.sat ?? null, peak6h: Math.max(...e2.map((r) => r.v)) },
    };
  },
});
