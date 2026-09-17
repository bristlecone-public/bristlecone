// ERCOT energy storage resources — 5-minute net output of the Texas battery
// fleet. Positive = discharging into the grid, negative = charging off it.
// The feed carries both `previousDay` and `currentDay`, so a cold start gets
// two days of series for free.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mergeSeries, ercotTime } from './_util.js';

const URL = 'https://www.ercot.com/api/1/services/read/dashboards/energy-storage-resources.json';
const HISTORY = 576; // 2 days of 5-minute points

export const ercotStorage = defineInstrument({
  id: 'ercot-storage',
  section: 'Texas / ERCOT',
  title: 'ERCOT battery net output',
  unit: 'MW',
  decimals: 0,
  cadence: '30m',
  history: HISTORY,
  source: {
    name: 'ERCOT energy storage resources dashboard',
    url: 'https://www.ercot.com/gridmktinfo/dashboards/energystorage',
    license: 'ERCOT public data (terms: https://www.ercot.com/about/legal)',
  },
  higherIsWorse: false,
  describe:
    'What the Texas battery fleet is doing right now: positive means it is discharging to hold the grid up, negative means it is soaking up surplus solar to be ready for the evening peak.',
  async fetch({ http, prev }) {
    const d = await http.json(URL);
    const rows = [...(d?.previousDay?.data || []), ...(d?.currentDay?.data || [])]
      .filter((r) => r && r.netOutput != null)
      .sort((a, b) => (Number(a.epoch) || 0) - (Number(b.epoch) || 0));
    if (!rows.length) throw new Error('energy-storage-resources.json: no netOutput rows');

    const pts = rows
      .map((r) => [Number(r.epoch) || ercotTime(r.timestamp), num(r.netOutput)])
      .filter(([t, v]) => Number.isFinite(t) && v != null);

    const last = rows[rows.length - 1];
    return {
      value: num(last.netOutput),
      at: new Date(Number(last.epoch) || ercotTime(last.timestamp)).toISOString(),
      series: mergeSeries(prev?.series, pts, HISTORY),
      meta: {
        chargingMW: num(last.totalCharging),
        dischargingMW: num(last.totalDischarging),
        mode: num(last.netOutput) >= 0 ? 'discharging' : 'charging',
        lastUpdated: d.lastUpdated || null,
      },
    };
  },
});
