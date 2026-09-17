// Kalshi — a CFTC-regulated US event exchange. Public read-only market data,
// keyless, no auth needed for /events.
//
//   https://api.elections.kalshi.com/trade-api/v2/events
//     ?series_ticker=<SERIES>&status=open&with_nested_markets=true
//
// Prices are dollars per $1 contract, i.e. already a probability. We take the
// bid/ask midpoint when a two-sided quote exists and fall back to the last trade,
// because a thin book can leave `last_price` stale for hours.

import { defineInstrument } from '../framework/registry.js';

const EVENTS = (series) =>
  'https://api.elections.kalshi.com/trade-api/v2/events'
  + `?series_ticker=${series}&status=open&with_nested_markets=true`;

// bid/ask midpoint → probability 0–1, or null if the market has no quote at all.
function impliedProb(m) {
  const bid = Number(m.yes_bid_dollars);
  const ask = Number(m.yes_ask_dollars);
  const last = Number(m.last_price_dollars);
  if (Number.isFinite(bid) && Number.isFinite(ask) && (bid > 0 || ask < 1)) return (bid + ask) / 2;
  if (Number.isFinite(last) && last > 0) return last;
  // An empty book (bid 0 / ask 1) with no trades is NOT a 50/50 quote — the old
  // `(bid+ask)/2` fallback here fabricated a spurious 0.5. Return null: "no quote".
  return null;
}

const pct = (p) => (p == null ? null : Number((p * 100).toFixed(1)));

async function openEvents(http, series) {
  const d = await http.json(EVENTS(series));
  const events = (d?.events || []).filter((e) => (e.markets || []).length);
  if (!events.length) throw new Error(`Kalshi ${series}: no open events`);
  return events;
}

/* ───────────────────────── Next FOMC decision ───────────────────────── */

// custom_strike is {Cut:'25'} / {Hike:'0'} / {Hike:'>25'} … → signed basis points.
// The open-ended ">25" buckets get a nominal ±50bp so the expected-move figure
// stays finite; they almost never carry meaningful weight.
function strikeBps(m) {
  const s = m.custom_strike || {};
  const read = (v) => (String(v).startsWith('>') ? 50 : Number(v));
  if (s.Cut != null) return -read(s.Cut);
  if (s.Hike != null) return read(s.Hike);
  return null;
}

export const fomcOdds = defineInstrument({
  id: 'fomc-hold-odds',
  section: 'Prediction markets',
  title: 'Next FOMC: no change',
  unit: '%',
  decimals: 1,
  cadence: '6h',
  history: 700, // ≈ a week of 15-minute marks
  // Thresholds would be editorialising — a high or low hold probability is not
  // itself good or bad news. Status stays 'unknown'; the number is the point.
  thresholds: null,
  source: {
    name: 'Kalshi — Fed decision (KXFEDDECISION)',
    url: 'https://kalshi.com/markets/kxfeddecision',
    license: 'public market data, Kalshi terms of use',
  },
  describe: 'The traded probability that the Fed leaves its target range unchanged at the next FOMC meeting. Real money, repriced by the market between our ~6-hourly snapshots — usually ahead of the economists.',
  async fetch({ http }) {
    const events = await openEvents(http, 'KXFEDDECISION');
    // The soonest meeting that has not yet struck.
    const upcoming = events
      .map((e) => ({ e, t: Date.parse(e.strike_date) }))
      .filter((x) => Number.isFinite(x.t))
      .sort((a, b) => a.t - b.t);
    const chosen = (upcoming.find((x) => x.t > Date.now()) || upcoming[0])?.e;
    if (!chosen) throw new Error('Kalshi KXFEDDECISION: no dated event');

    const outcomes = chosen.markets
      .map((m) => ({
        label: m.yes_sub_title || m.subtitle || m.ticker,
        ticker: m.ticker,
        bps: strikeBps(m),
        prob: impliedProb(m),
      }))
      .filter((o) => o.prob != null)
      .sort((a, b) => (a.bps ?? 0) - (b.bps ?? 0));
    if (!outcomes.length) throw new Error('Kalshi KXFEDDECISION: no quoted markets');

    // Mutually exclusive and exhaustive, so normalise away the bid/ask overround.
    const total = outcomes.reduce((s, o) => s + o.prob, 0) || 1;
    for (const o of outcomes) o.norm = o.prob / total;

    const hold = outcomes.find((o) => o.bps === 0);
    if (!hold) throw new Error('Kalshi KXFEDDECISION: no "no change" market');
    const expectedBps = outcomes.reduce((s, o) => s + (o.bps ?? 0) * o.norm, 0);

    return {
      value: pct(hold.norm),
      at: new Date().toISOString(), // a live quote — observation time is now
      meta: {
        meeting: chosen.title || chosen.event_ticker,
        meetingDate: chosen.strike_date || null,
        expectedMoveBps: Number(expectedBps.toFixed(1)),
        cutOdds: pct(outcomes.filter((o) => o.bps < 0).reduce((s, o) => s + o.norm, 0)),
        hikeOdds: pct(outcomes.filter((o) => o.bps > 0).reduce((s, o) => s + o.norm, 0)),
        outcomes: outcomes.map((o) => ({ label: o.label, bps: o.bps, pct: pct(o.norm) })),
      },
    };
  },
});

/* ───────────────────────── Recession odds ───────────────────────── */

export const recessionOdds = defineInstrument({
  id: 'recession-odds',
  section: 'Prediction markets',
  title: 'US recession starts this year',
  unit: '%',
  decimals: 1,
  cadence: '6h',
  history: 720, // ≈ 30 days of hourly marks
  thresholds: null, // no official scale for a subjective probability
  source: {
    name: 'Kalshi — Recession (KXRECSSNBER)',
    url: 'https://kalshi.com/markets/kxrecssnber',
    license: 'public market data, Kalshi terms of use',
  },
  describe: 'The traded probability that the NBER later dates the start of a US recession inside the current calendar year. Settles on the official NBER call, not on the two-negative-quarters rule of thumb.',
  async fetch({ http }) {
    const events = await openEvents(http, 'KXRECSSNBER');
    // Earliest-resolving open event = the current year's contract.
    const chosen = events
      .map((e) => ({ e, t: Date.parse(e.markets[0]?.close_time) }))
      .sort((a, b) => (a.t || Infinity) - (b.t || Infinity))[0].e;

    const market = chosen.markets[0];
    const p = impliedProb(market);
    if (p == null) throw new Error('Kalshi KXRECSSNBER: market has no quote');

    return {
      value: pct(p),
      at: new Date().toISOString(),
      meta: {
        question: chosen.title || chosen.event_ticker,
        ticker: market.ticker,
        closes: market.close_time || null,
        bid: Number(market.yes_bid_dollars) || null,
        ask: Number(market.yes_ask_dollars) || null,
        lastTrade: Number(market.last_price_dollars) || null,
      },
    };
  },
});
