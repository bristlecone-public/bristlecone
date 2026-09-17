// GB wholesale power price — Elexon's Market Index Data (dataset MID), the
// volume-weighted price of short-term trades in each half-hour settlement
// period. Two providers report; N2EX publishes zeros into this feed, so we take
// APX (APXMIDP), which is the one with real volume behind it.
//
// No accepted alert scale exists for wholesale power prices, so this instrument
// carries no thresholds — status stays 'unknown' and the number speaks for itself.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mergeSeries, isoZ } from './_util.js';

const HISTORY = 336; // 7 days of half-hourly settlement periods
const WINDOW_MS = 24 * 3600_000;
const PROVIDER = 'APXMIDP';

export const gbMarketPrice = defineInstrument({
  id: 'gb-market-price',
  section: 'Prices',
  title: 'GB wholesale power price',
  unit: '£/MWh',
  decimals: 2,
  cadence: '30m',
  history: HISTORY,
  source: {
    name: 'Elexon BMRS Insights — Market Index Data (MID)',
    url: 'https://bmrs.elexon.co.uk/market-index-prices',
    license: 'Elexon open data — free to use, no registration',
  },
  higherIsWorse: true,
  describe:
    'The half-hourly clearing price of electricity in Great Britain — a second, independent market to compare against Texas, on a grid with very different weather and very different plant.',
  async fetch({ http, prev, now }) {
    const t1 = now || Date.now();
    const urlStr =
      'https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index' +
      `?from=${isoZ(t1 - WINDOW_MS)}&to=${isoZ(t1)}&format=json`;
    const d = await http.json(urlStr);
    const rows = (d?.data || []).filter((r) => r?.dataProvider === PROVIDER && r.price != null);
    if (!rows.length) throw new Error(`Elexon MID returned no ${PROVIDER} rows in the last 24h`);

    const pts = rows
      .map((r) => [Date.parse(r.startTime), num(r.price)])
      .filter(([t, v]) => Number.isFinite(t) && v != null)
      .sort((a, b) => a[0] - b[0]);
    const [lastT, lastV] = pts[pts.length - 1];
    const last = rows.find((r) => Date.parse(r.startTime) === lastT) || {};

    return {
      value: lastV,
      at: new Date(lastT).toISOString(),
      series: mergeSeries(prev?.series, pts, HISTORY),
      meta: {
        provider: PROVIDER,
        volumeMWh: num(last.volume),
        settlementDate: last.settlementDate || null,
        settlementPeriod: last.settlementPeriod ?? null,
      },
    };
  },
});
