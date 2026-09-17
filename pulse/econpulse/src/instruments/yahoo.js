// Yahoo Finance chart endpoint — the fastest-updating feed on the board.
//
//   https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=1y&interval=1d
//
// Keyless and undocumented. It works from a plain fetch today, but it is the most
// fragile source here: Yahoo rate-limits (HTTP 429) and sometimes demands a consent
// cookie from datacentre IPs. "Stale beats fake" covers us — the card keeps the last
// good close and shows its age. If it degrades permanently, swap to the FRED daily
// close (series id SP500, keyless, ~1 day behind) via fredSeries() in ./fred.js.

import { defineInstrument } from '../framework/registry.js';

const CHART = (symbol, range = '1y', interval = '1d') =>
  `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}`
  + `?range=${range}&interval=${interval}`;

export const sp500 = defineInstrument({
  id: 'sp500',
  section: 'Markets',
  title: 'S&P 500',
  unit: '',
  decimals: 2,
  cadence: '6h',
  history: 400,
  // `at` is the last trade time, so over a weekend the freshest possible quote
  // is ~2 days old. Without this the default max(3×15m,2h)=2h threshold flags
  // the market as stale every weekend. (It refreshes each ~6h fan-out tick.)
  staleAfter: '4d',
  higherIsWorse: false,
  // No threshold scale for an index level; the % change from the previous close
  // lives in meta and the sparkline carries the trend.
  source: {
    name: 'Yahoo Finance (S&P 500, ^GSPC)',
    url: 'https://finance.yahoo.com/quote/%5EGSPC/',
    license: 'personal, non-commercial use only — see Yahoo Finance terms',
  },
  describe: 'The broad US equity benchmark, quoted during New York hours. Not an economic statistic, but the fastest-updating opinion on where the economy is going.',
  async fetch({ http }) {
    const d = await http.json(CHART('^GSPC'));
    const r = d?.chart?.result?.[0];
    if (!r) throw new Error(`Yahoo chart: no result (${d?.chart?.error?.description || 'unknown'})`);

    const stamps = r.timestamp || [];
    const closes = r.indicators?.quote?.[0]?.close || [];
    const series = [];
    for (let i = 0; i < stamps.length; i++) {
      const v = closes[i];
      if (v == null || !Number.isFinite(v)) continue; // holidays come back as null
      series.push([stamps[i] * 1000, Number(v.toFixed(2))]);
    }

    const m = r.meta || {};
    const live = Number(m.regularMarketPrice);
    const at = Number.isFinite(m.regularMarketTime) ? m.regularMarketTime * 1000 : null;
    if (Number.isFinite(live) && at) {
      // The final daily bar IS today's in-progress bar; overwrite rather than append.
      const lastDay = series.length ? new Date(series[series.length - 1][0]).toISOString().slice(0, 10) : null;
      const today = new Date(at).toISOString().slice(0, 10);
      if (lastDay === today) series.pop();
      series.push([at, Number(live.toFixed(2))]);
    }
    if (!series.length) throw new Error('Yahoo chart: no usable closes');

    const [t, v] = series[series.length - 1];
    const prevClose = Number(m.chartPreviousClose);
    const ref = Number.isFinite(m.previousClose) ? m.previousClose
      : series.length > 1 ? series[series.length - 2][1] : null;
    return {
      value: v,
      at: new Date(t).toISOString(),
      series,
      meta: {
        symbol: m.symbol || '^GSPC',
        exchange: m.fullExchangeName || null,
        changePct: ref ? Number((((v / ref) - 1) * 100).toFixed(2)) : null,
        fiftyTwoWeekHigh: m.fiftyTwoWeekHigh ?? null,
        fiftyTwoWeekLow: m.fiftyTwoWeekLow ?? null,
        yearAgoClose: Number.isFinite(prevClose) ? prevClose : null,
      },
    };
  },
});
