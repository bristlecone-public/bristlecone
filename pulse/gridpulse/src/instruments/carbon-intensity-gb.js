// Great Britain carbon intensity, from the National Energy System Operator /
// Carbon Intensity API. Half-hourly grams of CO₂ per kWh of electricity
// consumed. `/intensity/date` returns the whole of today in one call, with
// `actual` filled in for settlement periods that have already happened and null
// for the ones still ahead — so a cold start gets a populated chart immediately.
//
// The API's own published index bands (revised each year as the grid cleans up)
// give this instrument a real, accepted scale rather than an invented one.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mergeSeries } from './_util.js';

const URL = 'https://api.carbonintensity.org.uk/intensity/date';
const HISTORY = 336; // 7 days of half-hourly points

export const gbCarbonIntensity = defineInstrument({
  id: 'gb-carbon-intensity',
  section: 'Carbon',
  title: 'GB grid carbon intensity',
  unit: 'gCO₂/kWh',
  decimals: 0,
  cadence: '30m',
  history: HISTORY,
  source: {
    name: 'Carbon Intensity API (NESO)',
    url: 'https://carbonintensity.org.uk/',
    license: 'CC-BY 4.0',
  },
  // The API's own index bands: low / moderate / high / very high.
  thresholds: [
    { level: 'critical', gte: 235 }, // "very high"
    { level: 'serious', gte: 150 }, // "high"
    { level: 'warning', gte: 90 }, // "moderate"
  ],
  higherIsWorse: true,
  describe:
    'Grams of CO₂ emitted per kilowatt-hour used in Britain — the same electricity is several times dirtier on a still, cold evening than on a windy afternoon.',
  async fetch({ http, prev, now }) {
    const d = await http.json(URL);
    const rows = (d?.data || []).filter((r) => r?.from);
    if (!rows.length) throw new Error('carbonintensity.org.uk returned no periods');

    // The day file runs to midnight, so the tail is forecast for periods that
    // have not happened. Keep only periods that have started — a vital sign is
    // an observation, and leaving them in would skew delta and range.
    const t1 = now || Date.now();
    const pts = rows
      .map((r) => [Date.parse(r.from), num(r.intensity?.actual ?? r.intensity?.forecast)])
      .filter(([t, v]) => Number.isFinite(t) && v != null && t <= t1)
      .sort((a, b) => a[0] - b[0]);
    if (!pts.length) throw new Error('no settlement period had an actual or forecast intensity');

    // Latest period with a settled actual; forecast-only periods stay in the
    // series but should not become the headline number.
    const settled = rows.filter((r) => r.intensity?.actual != null);
    const last = settled[settled.length - 1] || rows[rows.length - 1];

    return {
      value: num(last.intensity?.actual ?? last.intensity?.forecast),
      at: new Date(Date.parse(last.from)).toISOString(),
      series: mergeSeries(prev?.series, pts, HISTORY),
      meta: {
        index: last.intensity?.index || null,
        forecast: num(last.intensity?.forecast),
        actual: num(last.intensity?.actual),
        periodTo: last.to || null,
      },
    };
  },
});
