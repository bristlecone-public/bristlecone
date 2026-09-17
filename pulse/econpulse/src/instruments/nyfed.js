// Federal Reserve Bank of New York — reference rates API.
// Keyless JSON, no documented rate limit, published every business day ~08:00 ET
// for the *previous* business day's trading.
//
//   https://markets.newyorkfed.org/api/rates/unsecured/effr/last/<n>.json
//   https://markets.newyorkfed.org/api/rates/secured/sofr/last/<n>.json
//
// Response: { refRates: [{ effectiveDate, type, percentRate, percentPercentile1/25/75/99,
//                          targetRateFrom, targetRateTo, volumeInBillions, revisionIndicator }, …] }
// newest-first. `targetRate*` only appears on EFFR.

import { defineInstrument } from '../framework/registry.js';

const BASE = 'https://markets.newyorkfed.org/api/rates';
const DEPTH = 750; // ≈ 3 years of business days

async function refRates(http, path) {
  const d = await http.json(`${BASE}/${path}/last/${DEPTH}.json`);
  const rows = d?.refRates || [];
  if (!rows.length) throw new Error(`NY Fed ${path}: empty refRates`);
  const series = rows
    .map((r) => [Date.parse(`${r.effectiveDate}T00:00:00Z`), Number(r.percentRate)])
    .filter(([t, v]) => Number.isFinite(t) && Number.isFinite(v))
    .sort((a, b) => a[0] - b[0]);
  return { rows, series, latest: rows[0] };
}

export const effectiveFedFunds = defineInstrument({
  id: 'fed-funds-effective',
  section: 'Rates',
  title: 'Effective fed funds rate',
  unit: '%',
  decimals: 2,
  cadence: '6h',
  history: 780,
  // Published each business day for the PREVIOUS business day, so the latest
  // obs is 1 day old midweek and 3+ across a weekend/holiday. Without this the
  // default 18h stale threshold flags current data every weekend.
  staleAfter: '4d',
  source: {
    name: 'Federal Reserve Bank of New York — reference rates',
    url: 'https://www.newyorkfed.org/markets/reference-rates/effr',
    license: 'public domain (U.S. government)',
  },
  describe: "What banks actually paid to borrow reserves overnight — the rate the FOMC steers. It should sit inside the Fed's target range; where it sits in that range says how tight cash is.",
  async fetch({ http }) {
    // SOFR rides along in meta: same publication, and the SOFR–EFFR gap is the
    // standard tell for repo-market funding stress.
    const [effr, sofr] = await Promise.all([
      refRates(http, 'unsecured/effr'),
      refRates(http, 'secured/sofr').catch(() => null),
    ]);
    const l = effr.latest;
    return {
      value: Number(l.percentRate),
      at: new Date(Date.parse(`${l.effectiveDate}T00:00:00Z`)).toISOString(),
      series: effr.series,
      meta: {
        targetRange: l.targetRateFrom != null ? `${l.targetRateFrom}–${l.targetRateTo}%` : null,
        targetLow: l.targetRateFrom ?? null,
        targetHigh: l.targetRateTo ?? null,
        volumeBn: l.volumeInBillions ?? null,
        pct1: l.percentPercentile1 ?? null,
        pct99: l.percentPercentile99 ?? null,
        revised: l.revisionIndicator ? true : false,
        sofr: sofr ? Number(sofr.latest.percentRate) : null,
        sofrDate: sofr ? sofr.latest.effectiveDate : null,
        sofrMinusEffr: sofr ? Number((sofr.latest.percentRate - l.percentRate).toFixed(3)) : null,
      },
    };
  },
});
