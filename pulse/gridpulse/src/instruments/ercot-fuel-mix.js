// ERCOT fuel mix — 5-minute generation by fuel, reported as a nested map:
//   data["2026-08-17"]["2026-08-17 08:29:57-0500"]["Wind"].gen  → MW
//
// We publish the renewable share (wind + solar + hydro as a percentage of all
// generation). Power Storage appears in the same map and goes negative while
// batteries charge, so negative entries are excluded from the denominator —
// charging is load, not supply.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mergeSeries, ercotTime } from './_util.js';

const URL = 'https://www.ercot.com/api/1/services/read/dashboards/fuel-mix.json';
const HISTORY = 576; // 2 days of 5-minute points
const RENEWABLE = new Set(['Wind', 'Solar', 'Hydro']);

export const ercotFuelMix = defineInstrument({
  id: 'ercot-fuel-mix',
  section: 'Generation Mix',
  title: 'ERCOT renewable share',
  unit: '%',
  decimals: 1,
  cadence: '30m',
  history: HISTORY,
  source: {
    name: 'ERCOT fuel mix dashboard',
    url: 'https://www.ercot.com/gridmktinfo/dashboards/fuelmix',
    license: 'ERCOT public data (terms: https://www.ercot.com/about/legal)',
  },
  higherIsWorse: false,
  describe:
    'Share of Texas generation coming from wind, solar and hydro right now — routinely past 50% on a windy spring afternoon and near zero on a still summer night.',
  async fetch({ http, prev }) {
    const d = await http.json(URL);
    const byDay = d?.data || {};
    const pts = [];
    let lastGen = null;
    let lastT = null;

    for (const day of Object.keys(byDay).sort()) {
      for (const stamp of Object.keys(byDay[day]).sort()) {
        const t = ercotTime(stamp);
        const gen = byDay[day][stamp];
        if (t == null || !gen) continue;
        let total = 0;
        let renew = 0;
        for (const [fuel, o] of Object.entries(gen)) {
          const v = num(o?.gen);
          if (v == null) continue;
          if (v > 0) total += v;
          if (RENEWABLE.has(fuel) && v > 0) renew += v;
        }
        if (total <= 0) continue;
        pts.push([t, Math.round((renew / total) * 1000) / 10]);
        lastGen = gen;
        lastT = t;
      }
    }
    if (!pts.length) throw new Error('fuel-mix.json: no usable intervals');

    const mw = {};
    for (const [fuel, o] of Object.entries(lastGen)) {
      const v = num(o?.gen);
      if (v != null) mw[fuel] = Math.round(v);
    }

    return {
      value: pts[pts.length - 1][1],
      at: new Date(lastT).toISOString(),
      series: mergeSeries(prev?.series, pts, HISTORY),
      meta: { mwByFuel: mw, lastUpdated: d.lastUpdated || null },
    };
  },
});
