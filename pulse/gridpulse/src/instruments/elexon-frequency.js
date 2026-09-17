// GB system frequency from Elexon's BMRS Insights API (dataset FREQ), sampled
// every 15 seconds. Frequency is the one number that is identical everywhere on
// a synchronous grid and it moves the instant supply and demand disagree, so it
// is the closest thing a power system has to a pulse.
//
// Great Britain runs at 50 Hz. NESO's published bands:
//   ±0.1 Hz  normal operating range
//   ±0.2 Hz  operational limits
//   ±0.5 Hz  statutory limits (breaching these is a reportable event)
//
// No key, no registration; the API is open. We ask for the last three hours and
// keep the most extreme reading in each 5-minute bucket — for frequency the
// excursion is the story, an average would hide it.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mergeSeries, downsampleExtreme, isoZ } from './_util.js';

const HISTORY = 576; // 2 days of 5-minute buckets
const WINDOW_MS = 3 * 3600_000;

export const gbFrequency = defineInstrument({
  id: 'gb-frequency',
  section: 'Frequency & Reserves',
  title: 'GB system frequency',
  unit: 'Hz',
  decimals: 3,
  cadence: '30m',
  history: HISTORY,
  source: {
    name: 'Elexon BMRS Insights (dataset FREQ)',
    url: 'https://bmrs.elexon.co.uk/system-frequency',
    license: 'Elexon open data — free to use, no registration',
  },
  thresholds: [
    { level: 'critical', lt: 49.5 },
    { level: 'critical', gt: 50.5 },
    { level: 'serious', lt: 49.8 },
    { level: 'serious', gt: 50.2 },
    { level: 'warning', lt: 49.9 },
    { level: 'warning', gt: 50.1 },
  ],
  higherIsWorse: true, // symmetric really — deviation either way is the signal
  describe:
    'The heartbeat of the British grid: 50 Hz means generation exactly matches demand, and every dip below it means the country is drawing more power than it is making.',
  async fetch({ http, prev, now }) {
    const t1 = now || Date.now();
    const urlStr =
      'https://data.elexon.co.uk/bmrs/api/v1/system/frequency' +
      `?from=${isoZ(t1 - WINDOW_MS)}&to=${isoZ(t1)}&format=json`;
    const d = await http.json(urlStr);
    const rows = (d?.data || [])
      .map((r) => [Date.parse(r.measurementTime), num(r.frequency)])
      .filter(([t, v]) => Number.isFinite(t) && v != null)
      .sort((a, b) => a[0] - b[0]);
    if (!rows.length) throw new Error('Elexon FREQ returned no readings in the last 3h');

    const [lastT, lastV] = rows[rows.length - 1];
    const vals = rows.map((r) => r[1]);

    return {
      value: lastV,
      at: new Date(lastT).toISOString(),
      series: mergeSeries(prev?.series, downsampleExtreme(rows, 5 * 60_000, 50), HISTORY),
      meta: {
        readingsIn3h: rows.length,
        min3h: Math.min(...vals),
        max3h: Math.max(...vals),
        nominalHz: 50,
      },
    };
  },
});
