// ERCOT combined wind + solar production, hourly averaged actuals.
// `currentDay.data` is keyed by epoch; hours that have not happened yet carry
// actualWind / actualSolar = null alongside their forecasts, so we keep only
// the hours ERCOT has actually measured.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mergeSeries, ercotTime } from './_util.js';

const URL = 'https://www.ercot.com/api/1/services/read/dashboards/combine-wind-solar.json';
const HISTORY = 336; // 14 days of hourly points

export const ercotWindSolar = defineInstrument({
  id: 'ercot-wind-solar',
  section: 'Texas / ERCOT',
  title: 'ERCOT wind + solar output',
  unit: 'MW',
  decimals: 0,
  cadence: '1h',
  history: HISTORY,
  source: {
    name: 'ERCOT combined wind & solar dashboard',
    url: 'https://www.ercot.com/gridmktinfo/dashboards/combinedwindandsolar',
    license: 'ERCOT public data (terms: https://www.ercot.com/about/legal)',
  },
  higherIsWorse: false,
  describe:
    'Hourly wind plus utility-scale solar generation in Texas — on a good afternoon it covers most of the load, and when it drops out at sunset the gas fleet and batteries have to catch the fall.',
  async fetch({ http, prev }) {
    const d = await http.json(URL);
    const rows = Object.values(d?.currentDay?.data || {})
      .filter((r) => r && (r.actualWind != null || r.actualSolar != null))
      .sort((a, b) => (Number(a.epoch) || 0) - (Number(b.epoch) || 0));
    if (!rows.length) throw new Error('combine-wind-solar.json: no measured hours yet');

    const pts = rows
      .map((r) => [
        Number(r.epoch) || ercotTime(r.timestamp),
        (num(r.actualWind) || 0) + (num(r.actualSolar) || 0),
      ])
      .filter(([t, v]) => Number.isFinite(t) && v != null);

    const last = rows[rows.length - 1];
    const wind = num(last.actualWind) || 0;
    const solar = num(last.actualSolar) || 0;

    return {
      value: wind + solar,
      at: new Date(Number(last.epoch) || ercotTime(last.timestamp)).toISOString(),
      series: mergeSeries(prev?.series, pts, HISTORY),
      meta: {
        windMW: Math.round(wind),
        solarMW: Math.round(solar),
        hourEnding: last.hourEnding ?? null,
        lastUpdated: d.lastUpdated || null,
      },
    };
  },
});
