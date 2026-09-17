// FRED (Federal Reserve Bank of St. Louis) — one generic series helper, many instruments.
//
// Two code paths, same output:
//   1. KEYLESS (default): https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>&cosd=<start>
//      The chart-download endpoint. Returns "observation_date,<ID>" CSV, no key, no
//      documented rate limit. Missing observations are an empty cell (holidays) or ".".
//      NOTE: multi-id (?id=A,B) returns a ZIP, so we always request ONE series per call.
//   2. KEYED (optional): if FRED_API_KEY is set in the env we use the official JSON API
//      instead (higher confidence in stability, 120 req/min). No instrument declares
//      needsKey — the key is a pure upgrade, never a requirement.
//
// Cadence is 6h for everything: FRED refreshes on the source agency's schedule and
// even the daily series only move once per business day, but a 6h poll means a new
// CPI / claims / GDPNow print shows up the same morning it lands.

import { defineInstrument } from '../framework/registry.js';

const CSV_BASE = 'https://fred.stlouisfed.org/graph/fredgraph.csv';
const API_BASE = 'https://api.stlouisfed.org/fred/series/observations';

const DAY = 86_400_000;
const MISSING = new Set(['', '.', 'NA', 'null']);

function startDate(years, now) {
  return new Date(now - years * 365.25 * DAY).toISOString().slice(0, 10);
}

// → [[epochMs, number], …] ascending, missing observations dropped.
async function fetchFredSeries({ http, env, now }, seriesId, years) {
  const cosd = startDate(years, now);
  let raw;

  if (env?.FRED_API_KEY) {
    const url = `${API_BASE}?series_id=${encodeURIComponent(seriesId)}&api_key=${env.FRED_API_KEY}`
      + `&file_type=json&observation_start=${cosd}`;
    const d = await http.json(url);
    raw = (d.observations || []).map((o) => [o.date, o.value]);
  } else {
    const url = `${CSV_BASE}?id=${encodeURIComponent(seriesId)}&cosd=${cosd}`;
    const rows = await http.csv(url);
    // Header is "observation_date,<SERIES_ID>" but FRED occasionally cases the id
    // differently than requested, so fall back to "the second column".
    raw = rows.map((r) => {
      const keys = Object.keys(r);
      const dateKey = keys.find((k) => /date/i.test(k)) || keys[0];
      const valKey = keys.find((k) => k !== dateKey) || keys[1];
      return [r[dateKey], r[valKey]];
    });
  }

  const series = [];
  for (const [date, value] of raw) {
    const v = String(value ?? '').trim();
    if (MISSING.has(v)) continue;            // holiday / not-yet-published
    const n = Number(v.replace(/,/g, ''));
    if (!Number.isFinite(n)) continue;
    const t = Date.parse(`${String(date).trim()}T00:00:00Z`);
    if (!Number.isFinite(t)) continue;
    series.push([t, n]);
  }
  series.sort((a, b) => a[0] - b[0]);
  return series;
}

/**
 * Build a FRED-backed metric instrument.
 *
 * @param seriesId  FRED series id, e.g. 'DGS10'
 * @param years     how far back to request (sizes the sparkline)
 * @param transform optional (series) => series, e.g. level → YoY %
 * @param rest      everything defineInstrument() takes (id, section, title, …)
 */
export function fredSeries({ seriesId, years = 2, transform, source, ...rest }) {
  return defineInstrument({
    kind: 'metric',
    cadence: '6h',
    source: {
      name: `FRED · ${seriesId}`,
      url: `https://fred.stlouisfed.org/series/${seriesId}`,
      license: 'FRED® terms of use; underlying data public domain (U.S. government)',
      ...source,
    },
    ...rest,
    async fetch(ctx) {
      let series = await fetchFredSeries(ctx, seriesId, years);
      if (transform) series = transform(series);
      if (!series.length) throw new Error(`FRED ${seriesId}: no usable observations`);
      const [t, v] = series[series.length - 1];
      return {
        value: v,
        at: new Date(t).toISOString(),
        series,
        meta: {
          seriesId,
          observations: series.length,
          via: ctx.env?.FRED_API_KEY ? 'FRED JSON API (keyed)' : 'fredgraph.csv (keyless)',
        },
      };
    },
  });
}

// Level series → year-over-year % change. Matches each month to the same month a
// year earlier by calendar key rather than by index, so a gap can't silently
// shift the comparison window.
function yoyPercent(series) {
  const byMonth = new Map();
  for (const [t, v] of series) {
    const d = new Date(t);
    byMonth.set(`${d.getUTCFullYear()}-${d.getUTCMonth()}`, v);
  }
  const out = [];
  for (const [t, v] of series) {
    const d = new Date(t);
    const prior = byMonth.get(`${d.getUTCFullYear() - 1}-${d.getUTCMonth()}`);
    if (prior == null || prior === 0) continue;
    out.push([t, ((v / prior) - 1) * 100]);
  }
  return out;
}

/* ────────────────────────────── Vitals ────────────────────────────── */

export const yieldCurve = fredSeries({
  seriesId: 'T10Y2Y',
  id: 'yield-curve-10y2y',
  section: 'Vitals',
  title: '10y–2y Treasury spread',
  unit: 'pp',
  decimals: 2,
  years: 3,
  history: 780,
  // Daily (business-day) series: obs date is the prior trading day, so it is
  // legitimately 2–4 days old across a weekend or holiday. Without this the UI's
  // stale marker (max(3×cadence,2h)=18h) fires every weekend on current data.
  staleAfter: '4d',
  higherIsWorse: false,
  thresholds: [{ level: 'warning', lte: 0 }],
  describe: 'The 10-year Treasury yield minus the 2-year. When it goes negative the bond market is pricing rate cuts ahead — an inversion has preceded every US recession since 1970.',
});

export const weeklyEconomicIndex = fredSeries({
  seriesId: 'WEI',
  id: 'weekly-economic-index',
  section: 'Vitals',
  title: 'Weekly Economic Index',
  unit: '% y/y',
  decimals: 2,
  years: 3,
  history: 160,
  // Weekly series (released ~5 days after the week it covers).
  staleAfter: '14d',
  higherIsWorse: false,
  thresholds: [
    { level: 'serious', lte: -2 },
    { level: 'warning', lte: 0 },
  ],
  source: { name: 'FRED · WEI (Federal Reserve Bank of Dallas)' },
  describe: 'A ten-indicator index of real economic activity — retail sales, claims, steel output, rail traffic and more — scaled to look like GDP growth, published weekly instead of quarterly.',
});

export const gdpNow = fredSeries({
  seriesId: 'GDPNOW',
  id: 'gdpnow',
  section: 'Vitals',
  title: 'GDPNow nowcast',
  unit: '% SAAR',
  decimals: 1,
  // Five years, so the ±33% COVID quarters stay off the sparkline and ordinary
  // variation is actually legible. (For quarterly series FRED returns the whole
  // quarter containing `cosd`, so this starts at Q3 2021.)
  years: 5,
  history: 22,
  // Dated to the quarter it forecasts (timestamp = quarter start), so it runs
  // 0–~90 days "old" through the quarter even while being re-estimated weekly.
  staleAfter: '120d',
  higherIsWorse: false,
  thresholds: [
    { level: 'serious', lte: -2 },
    { level: 'warning', lte: 0 },
  ],
  source: { name: 'FRED · GDPNOW (Federal Reserve Bank of Atlanta)' },
  describe: "The Atlanta Fed's running estimate of this quarter's real GDP growth, rebuilt from scratch every time a major data release lands — the closest thing to a live read on output. Dated to the quarter it forecasts, so the timestamp is the quarter start, not the vintage.",
});

/* ────────────────────────────── Rates ────────────────────────────── */

export const treasury10y = fredSeries({
  seriesId: 'DGS10',
  id: 'treasury-10y',
  section: 'Rates',
  title: '10-year Treasury yield',
  unit: '%',
  decimals: 2,
  years: 3,
  history: 780,
  staleAfter: '4d', // daily business-day series; survive weekends/holidays
  describe: 'The benchmark long-term US borrowing cost. It anchors mortgages, corporate debt and global asset pricing, and moves on growth and inflation expectations rather than Fed policy alone.',
});

export const mortgage30y = fredSeries({
  seriesId: 'MORTGAGE30US',
  id: 'mortgage-30y',
  section: 'Rates',
  title: '30-year fixed mortgage',
  unit: '%',
  decimals: 2,
  years: 3,
  history: 160,
  staleAfter: '14d', // weekly survey, published Thursdays
  thresholds: [
    { level: 'serious', gte: 8 },
    { level: 'warning', gte: 7 },
  ],
  source: { name: 'FRED · MORTGAGE30US (Freddie Mac PMMS)' },
  describe: "Freddie Mac's weekly survey average for a 30-year fixed home loan — the single number that decides whether housing transactions happen. Published Thursdays.",
});

/* ────────────────────────────── Prices ───────────────────────────── */

export const cpiYoY = fredSeries({
  seriesId: 'CPIAUCNS',
  id: 'cpi-yoy',
  section: 'Prices',
  title: 'CPI inflation (y/y)',
  unit: '%',
  decimals: 2,
  years: 8,
  history: 84,
  // Monthly, dated to the reference month and released ~2 weeks after it ends.
  staleAfter: '45d',
  transform: yoyPercent,
  thresholds: [
    { level: 'critical', gte: 6 },
    { level: 'serious', gte: 4 },
    { level: 'warning', gte: 3 },
  ],
  source: { name: 'FRED · CPIAUCNS (U.S. Bureau of Labor Statistics)' },
  describe: 'Headline consumer price inflation over the past twelve months — the 12-month change everyone quotes, computed here from the not-seasonally-adjusted CPI index (NSA is the basis of the reported headline number; year-over-year comparison already nets out seasonality). The Fed targets 2% (on a different index, PCE), so 3%+ is uncomfortable. Dated to the reference month, which is released about two weeks later.',
});

export const gasPrice = fredSeries({
  seriesId: 'GASREGW',
  id: 'gas-regular',
  section: 'Prices',
  title: 'US regular gasoline',
  unit: '$/gal',
  decimals: 3,
  years: 3,
  history: 160,
  staleAfter: '14d', // weekly survey, published Mondays
  thresholds: [
    { level: 'critical', gte: 5 },
    { level: 'serious', gte: 4 },
    { level: 'warning', gte: 3.5 },
  ],
  source: { name: 'FRED · GASREGW (U.S. Energy Information Administration)' },
  describe: 'The national average pump price for regular gasoline, surveyed every Monday by the EIA. The most visible price in the economy and a heavy influence on consumer inflation expectations.',
});

/* ────────────────────────────── Labor ────────────────────────────── */

export const unemploymentRate = fredSeries({
  seriesId: 'UNRATE',
  id: 'unemployment-rate',
  section: 'Labor',
  title: 'Unemployment rate (U-3)',
  unit: '%',
  decimals: 1,
  // Five years keeps the 14.8% April 2020 spike off the chart, which would
  // otherwise flatten every subsequent move into a straight line.
  years: 5,
  history: 72,
  // Monthly, dated to the reference month and released the following month.
  staleAfter: '45d',
  thresholds: [
    { level: 'critical', gte: 7 },
    { level: 'serious', gte: 5.5 },
    { level: 'warning', gte: 4.5 },
  ],
  source: { name: 'FRED · UNRATE (U.S. Bureau of Labor Statistics)' },
  describe: 'The share of the labour force actively looking for work, from the monthly household survey. Slow to turn, but once it rises half a point off its low it has never stopped there.',
});

export const initialClaims = fredSeries({
  seriesId: 'ICSA',
  id: 'initial-claims',
  section: 'Labor',
  title: 'Initial jobless claims',
  unit: 'claims',
  decimals: 0,
  years: 3,
  history: 160,
  staleAfter: '14d', // weekly, released Thursdays for the prior week
  thresholds: [
    { level: 'critical', gte: 400000 },
    { level: 'serious', gte: 300000 },
    { level: 'warning', gte: 250000 },
  ],
  source: { name: 'FRED · ICSA (U.S. Department of Labor)' },
  describe: 'People filing for unemployment benefits for the first time last week, seasonally adjusted. The fastest-moving labour market signal there is — it turns months before the unemployment rate.',
});

/* ────────────────────────────── Markets ──────────────────────────── */

export const vix = fredSeries({
  seriesId: 'VIXCLS',
  id: 'vix',
  section: 'Markets',
  title: 'VIX volatility index',
  unit: '',
  decimals: 2,
  years: 3,
  history: 780,
  staleAfter: '4d', // daily business-day series; survive weekends/holidays
  thresholds: [
    { level: 'critical', gte: 40 },
    { level: 'serious', gte: 30 },
    { level: 'warning', gte: 20 },
  ],
  source: { name: 'FRED · VIXCLS (Cboe)', license: 'Cboe index values redistributed via FRED' },
  describe: "The options market's estimate of how much the S&P 500 will move over the next 30 days. Below 20 is calm; above 30 means investors are paying up hard for protection.",
});

export const highYieldSpread = fredSeries({
  seriesId: 'BAMLH0A0HYM2',
  id: 'high-yield-spread',
  section: 'Markets',
  title: 'High-yield credit spread',
  unit: 'pp',
  decimals: 2,
  years: 3,
  history: 780,
  staleAfter: '4d', // daily business-day series; survive weekends/holidays
  thresholds: [
    { level: 'critical', gte: 10 },
    { level: 'serious', gte: 7 },
    { level: 'warning', gte: 5 },
  ],
  source: {
    name: 'FRED · BAMLH0A0HYM2 (ICE BofA US High Yield Index OAS)',
    license: 'ICE Data Indices, LLC — used with permission, redistributed via FRED',
  },
  describe: 'The extra yield investors demand to lend to junk-rated US companies instead of the Treasury. The cleanest real-time gauge of credit stress: it blows out before defaults, not after.',
});
