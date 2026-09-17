// ERCOT real-time supply & demand (the public grid-conditions dashboard feed).
// 5-minute SCADA system load for the Texas Interconnection plus the committed
// capacity behind it. The same document also carries a forecast tail
// (forecast: 1) which we drop — a vital sign is an observation, not a plan.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mergeSeries, ercotTime } from './_util.js';

const URL = 'https://www.ercot.com/api/1/services/read/dashboards/supply-demand.json';
const HISTORY = 576; // 2 days of 5-minute points

export const ercotDemand = defineInstrument({
  id: 'ercot-demand',
  section: 'Vitals',
  title: 'ERCOT system demand',
  unit: 'MW',
  decimals: 0,
  cadence: '30m',
  history: HISTORY,
  source: {
    name: 'ERCOT grid conditions dashboard',
    url: 'https://www.ercot.com/gridmktinfo/dashboards/supplyanddemand',
    license: 'ERCOT public data (terms: https://www.ercot.com/about/legal)',
  },
  higherIsWorse: true,
  describe:
    'How much electricity Texas is using right now; ERCOT is an isolated grid, so demand approaching committed capacity is what turns into conservation appeals and rolling outages.',
  async fetch({ http, prev }) {
    const d = await http.json(URL);
    const rows = (d.data || []).filter((r) => Number(r.forecast) === 0 && num(r.demand) > 0);
    if (!rows.length) throw new Error('supply-demand.json: no actual (forecast=0) rows');

    const pts = rows
      .map((r) => [Number(r.epoch) || ercotTime(r.timestamp), num(r.demand)])
      .filter(([t, v]) => Number.isFinite(t) && v != null);
    const last = rows[rows.length - 1];
    const demand = num(last.demand);
    const capacity = num(last.capacity);

    return {
      value: demand,
      at: new Date(Number(last.epoch) || ercotTime(last.timestamp)).toISOString(),
      series: mergeSeries(prev?.series, pts, HISTORY),
      meta: {
        committedCapacityMW: capacity,
        headroomMW: capacity != null && demand != null ? Math.round(capacity - demand) : null,
        lastUpdated: d.lastUpdated || null,
      },
    };
  },
});
