// Monthly international sunspot number (SIDC/SILSO via NOAA SWPC) — the
// slowest-moving vital sign on the page: where we are in the 11-year solar cycle.
// The observed file goes back to 1749; we keep the last 30 years for the sparkline
// and overlay SWPC's prediction for the current month in meta.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

const OBSERVED = 'https://services.swpc.noaa.gov/json/solar-cycle/sunspots.json';
const PREDICTED = 'https://services.swpc.noaa.gov/json/solar-cycle/predicted-solar-cycle.json';

// "2026-07" → epoch ms of the first of that month, UTC
const monthMs = (tag) => Date.parse(`${tag}-01T00:00:00Z`);

export const sunspotNumber = defineInstrument({
  id: 'sunspot-number',
  section: 'Vitals',
  title: 'Sunspot number (monthly)',
  unit: 'SSN',
  decimals: 1,
  cadence: '1d', // the underlying series only advances once a month
  history: 360, // 30 years of monthly values
  // `at` is the first of the reported month, so on the last day of a 31-day
  // month the latest complete value is ~61 days old (SILSO posts month M on the
  // 1st of M+1). Without this the default max(3×cadence, 2h)=3d window would
  // brand this permanently stale.
  staleAfter: '62d',
  source: {
    name: 'NOAA SWPC / SILSO solar-cycle indices',
    url: 'https://www.swpc.noaa.gov/products/solar-cycle-progression',
    license: 'public domain (US Gov); underlying SSN © SILSO/Royal Observatory of Belgium, CC BY-NC 4.0',
  },
  // No hazard scale attaches to sunspot number — it is a cycle-phase indicator.
  thresholds: null,
  higherIsWorse: true,
  describe:
    'The international sunspot number for the most recent complete month; it tracks where the Sun sits in its ~11-year activity cycle, and high counts mean more flares, CMEs and geomagnetic storms.',
  async fetch({ http }) {
    const [observed, predicted] = await Promise.all([
      http.json(OBSERVED),
      http.json(PREDICTED).catch(() => null),
    ]);
    const series = observed
      .map((r) => [monthMs(r['time-tag']), num(r.ssn)])
      .filter(([t, v]) => Number.isFinite(t) && v != null && v >= 0)
      .sort((a, b) => a[0] - b[0]);
    if (!series.length) throw new Error('no monthly sunspot rows');
    const [t, v] = series[series.length - 1];
    const month = new Date(t).toISOString().slice(0, 7);
    const forecast = Array.isArray(predicted)
      ? predicted.find((r) => r['time-tag'] === month) || predicted[0]
      : null;
    const last132 = series.slice(-132).map((p) => p[1]);
    return {
      value: v,
      at: new Date(t).toISOString(),
      series,
      meta: {
        month,
        cycleMax11y: last132.length ? Math.max(...last132) : null,
        predictedSsn: forecast ? num(forecast.predicted_ssn) : null,
        predictedMonth: forecast ? forecast['time-tag'] : null,
      },
    };
  },
});
