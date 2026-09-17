// APNIC Labs measures IPv6 capability by serving a 1x1 measurement image to a
// sample of real end users through an ad network — the closest thing to a
// world-wide, client-side IPv6 adoption number.
//
// The web page at stats.labs.apnic.net is a Google-Charts wrapper, but it is
// fed by a plain JSON bulk file (linked from the page itself) which carries the
// whole daily series back to 2013 with raw and 10/30/60/90-day smoothing:
//   https://data1.labs.apnic.net/v6stats/v6region/XA.json   (XA = world)
//
// The file is ~4 MB, so we scan it with a regex instead of JSON.parse-ing the
// lot, and keep only the recent tail. Updated once a day (~06:00 UTC), lagging
// 2-3 days. Format docs: https://data1.labs.apnic.net/ipv6-data-format.html

import { defineInstrument } from '../framework/registry.js';

const URL = 'https://data1.labs.apnic.net/v6stats/v6region/XA.json';
const KEEP_DAYS = 400;

// Each daily record ends "…, "raw": {…}, "type": "v6region", "date": "YYYY-MM-DD"".
const RECORD = /"raw"\s*:\s*\{([^{}]*)\}\s*,\s*"type"\s*:\s*"v6region"\s*,\s*"date"\s*:\s*"(\d{4}-\d{2}-\d{2})"/g;
const field = (blob, name) => {
  const m = new RegExp(`"${name}"\\s*:\\s*(-?[0-9.]+)`).exec(blob);
  return m ? Number(m[1]) : null;
};

export const ipv6Capable = defineInstrument({
  id: 'ipv6-capable',
  section: 'Adoption',
  title: 'IPv6-capable users',
  unit: '%',
  decimals: 2,
  cadence: '1d',
  history: KEEP_DAYS,
  // Updated ~06:00 UTC and lags 2-3 days, which sits right on the default
  // staleAfter (3d) and flips the card stale on any weekend/holiday slip.
  staleAfter: '5d',
  source: {
    name: 'APNIC Labs — IPv6 measurement (world)',
    url: 'https://stats.labs.apnic.net/ipv6/XA',
    license: '(C) APNIC — re-use with attribution',
  },
  higherIsWorse: false,
  describe:
    'Share of sampled end users worldwide whose connection can fetch a resource over IPv6 — the headline number for the internet finally outgrowing its 1981 address space.',
  async fetch({ http }) {
    const text = await http.text(URL, { timeout: 30_000 });
    const rows = [];
    RECORD.lastIndex = 0;
    let m;
    while ((m = RECORD.exec(text))) {
      const capable = field(m[1], 'capable_pc');
      const preferred = field(m[1], 'preferred_pc');
      const t = Date.parse(`${m[2]}T00:00:00Z`);
      if (Number.isFinite(t) && capable != null) rows.push({ t, capable, preferred });
    }
    if (!rows.length) throw new Error('no v6region records matched — upstream format changed?');
    rows.sort((a, b) => a.t - b.t);
    const recent = rows.slice(-KEEP_DAYS);
    const last = recent[recent.length - 1];
    return {
      value: last.capable,
      at: new Date(last.t).toISOString(),
      series: recent.map((r) => [r.t, r.capable]),
      meta: { preferredPct: last.preferred, sampleDays: rows.length, note: 'raw daily sample, unsmoothed' },
    };
  },
});
