// ERCOT Physical Responsive Capability (PRC) — the megawatts of generation and
// load resources that can respond to a frequency drop within seconds. It is the
// number ERCOT itself watches to decide whether the grid is in an emergency:
//
//   PRC < 3000 MW   ERCOT begins watching / advisory territory
//   PRC < 2300 MW   Energy Emergency Alert Level 1 (EEA1) trigger
//   PRC < 1750 MW   EEA2 → EEA3, i.e. firm load shed
//
// The feed publishes PRC roughly every 10 seconds; we bucket it to 5 minutes so
// the sparkline covers two days rather than eight hours.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mergeSeries, downsample, ercotTime } from './_util.js';

const URL = 'https://www.ercot.com/api/1/services/read/dashboards/daily-prc.json';
const HISTORY = 576; // 2 days of 5-minute points

export const ercotPrc = defineInstrument({
  id: 'ercot-prc',
  section: 'Frequency & Reserves',
  title: 'ERCOT responsive reserves (PRC)',
  unit: 'MW',
  decimals: 0,
  cadence: '30m',
  history: HISTORY,
  source: {
    name: 'ERCOT grid conditions — physical responsive capability',
    url: 'https://www.ercot.com/gridmktinfo/dashboards/supplyanddemand',
    license: 'ERCOT public data (terms: https://www.ercot.com/about/legal)',
  },
  // Lower is worse: these are the published ERCOT Energy Emergency Alert triggers.
  thresholds: [
    { level: 'critical', lt: 1750 },
    { level: 'serious', lt: 2300 },
    { level: 'warning', lt: 3000 },
  ],
  higherIsWorse: false,
  describe:
    'Megawatts of reserve that can answer a frequency drop within seconds — ERCOT declares an energy emergency below 2,300 MW and starts shedding firm load below 1,750 MW.',
  async fetch({ http, prev }) {
    const d = await http.json(URL);
    const cc = d?.current_condition || {};
    const raw = (d?.data || [])
      .map((r) => [Number(r.epoch) || ercotTime(r.timestamp), num(r.prc)])
      .filter(([t, v]) => Number.isFinite(t) && v != null);
    if (!raw.length && cc.prc_value == null) throw new Error('daily-prc.json: no PRC values');

    const pts = downsample(raw, 5 * 60_000);
    const value = num(cc.prc_value) ?? (pts.length ? pts[pts.length - 1][1] : null);
    const at = cc.datetime
      ? new Date(Number(cc.datetime) * 1000).toISOString()
      : new Date(pts[pts.length - 1][0]).toISOString();

    return {
      value,
      at,
      series: mergeSeries(prev?.series, pts, HISTORY),
      meta: {
        eeaLevel: cc.eea_level ?? null,
        condition: cc.title || null,
        conditionNote: cc.condition_note || null,
        state: cc.state || null,
        lastUpdated: d.lastUpdated || null,
      },
    };
  },
});
