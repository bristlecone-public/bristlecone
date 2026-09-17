// ERCOT real-time settlement point prices — the 15-minute hub average across
// the Texas market, in $/MWh. ERCOT is energy-only with a $5,000/MWh offer cap,
// so scarcity shows up as price long before it shows up as an outage: a normal
// afternoon clears near $20–40, a tight one clears in the hundreds, and a real
// emergency pins the whole grid at the cap.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mergeSeries, ercotTime } from './_util.js';

const URL = 'https://www.ercot.com/api/1/services/read/dashboards/system-wide-prices.json';
const HISTORY = 384; // 4 days of 15-minute intervals

export const ercotRtPrice = defineInstrument({
  id: 'ercot-rt-price',
  section: 'Prices',
  title: 'ERCOT real-time hub price',
  unit: '$/MWh',
  decimals: 2,
  cadence: '30m',
  history: HISTORY,
  source: {
    name: 'ERCOT system-wide prices dashboard',
    url: 'https://www.ercot.com/gridmktinfo/dashboards/systemwideprices',
    license: 'ERCOT public data (terms: https://www.ercot.com/about/legal)',
  },
  // These thresholds capture SCARCITY only (higher = worse). They do not flag
  // the other tail: high West Texas wind/solar plus transmission bottlenecks can
  // push real-time prices negative (PTC-driven curtailment), which is grid stress
  // of a different kind but currently reads as the healthiest (lowest) level. A
  // proper two-sided scale needs framework support for `lte` thresholds; deferred
  // with the pinned ERCOT egress work rather than bolted on here.
  thresholds: [
    { level: 'critical', gte: 4000 }, // approaching the $5,000/MWh system-wide offer cap
    { level: 'serious', gte: 1000 }, // sustained scarcity pricing
    { level: 'warning', gte: 100 }, // well above a normal clearing price
  ],
  higherIsWorse: true,
  describe:
    'What a megawatt-hour costs in Texas right now, averaged across trading hubs — the earliest public signal that the grid is short of supply.',
  async fetch({ http, prev }) {
    const d = await http.json(URL);
    const rt = (d?.rtSppData || [])
      .filter((r) => r && r.hbHubAvg != null)
      .sort((a, b) => (Number(a.interval) || 0) - (Number(b.interval) || 0));
    if (!rt.length) throw new Error('system-wide-prices.json: no rtSppData intervals');

    const pts = rt
      .map((r) => [Number(r.interval) || ercotTime(r.timestamp), num(r.hbHubAvg)])
      .filter(([t, v]) => Number.isFinite(t) && v != null);
    const last = rt[rt.length - 1];

    const dam = (d?.damSppData || []).map((r) => num(r.hbHubAvg)).filter((v) => v != null);
    const damAvg = dam.length ? dam.reduce((a, b) => a + b, 0) / dam.length : null;

    return {
      value: num(last.hbHubAvg),
      at: new Date(Number(last.interval) || ercotTime(last.timestamp)).toISOString(),
      series: mergeSeries(prev?.series, pts, HISTORY),
      meta: {
        hbWest: num(last.hbWest),
        hbHouston: num(last.hbHouston),
        hbNorth: num(last.hbNorth),
        dayAheadAvg: damAvg != null ? Math.round(damAvg * 100) / 100 : null,
        intervalEnding: last.intervalEnding || null,
        lastUpdated: d.lastUpdated || null,
      },
    };
  },
});
