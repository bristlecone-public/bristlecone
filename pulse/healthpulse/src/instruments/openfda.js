// openFDA — FDA's public API over its own enforcement and shortage databases.
// Keyless usage is capped at 240 requests/minute and 1,000/day per IP, which
// these cadences use a rounding error of.
//
//   food/enforcement  → Class I recalls (reasonable probability of serious
//                       adverse health consequences or death)
//   drug/shortages    → the current national drug shortage list
//
// openFDA answers a zero-hit search with HTTP 404 + {error:{code:'NOT_FOUND'}},
// which the framework's http helper surfaces as a thrown error; both fetchers
// translate that into "nothing to report" rather than a failed instrument.

import { defineInstrument } from '../framework/registry.js';
import { fdaDateMs } from './_lib.js';

const TERMS = 'https://open.fda.gov/terms/ (public domain, no key required)';
const DAY = 86_400_000;
const RECALL_WINDOW_DAYS = 180;

const isNotFound = (err) => /NOT_FOUND|HTTP 404/i.test(String(err?.message || err));
const yyyymmdd = (ms) => new Date(ms).toISOString().slice(0, 10).replace(/-/g, '');

export const fdaFoodRecalls = defineInstrument({
  id: 'fda-food-recalls',
  section: 'Recalls & Shortages',
  kind: 'events',
  title: 'Class I food recalls',
  cadence: '12h',
  history: 120,
  source: {
    name: 'openFDA — Food Enforcement Reports',
    url: 'https://open.fda.gov/apis/food/enforcement/',
    license: TERMS,
  },
  describe:
    'FDA food recalls in the most serious class — where eating the product could reasonably cause serious harm or death. Listed newest first over the last six months.',
  async fetch({ http, now }) {
    const from = yyyymmdd(now - RECALL_WINDOW_DAYS * DAY);
    const to = yyyymmdd(now + DAY);
    const url =
      'https://api.fda.gov/food/enforcement.json' +
      `?search=classification:%22Class+I%22+AND+report_date:[${from}+TO+${to}]` +
      '&limit=50&sort=report_date:desc';

    let d;
    try {
      d = await http.json(url);
    } catch (err) {
      if (isNotFound(err)) return { items: [], meta: { window: `${from}-${to}`, total: 0 } };
      throw err;
    }

    const items = (d.results || [])
      .map((r) => {
        const t = fdaDateMs(r.report_date);
        if (!Number.isFinite(t)) return null;
        const product = String(r.product_description || '').replace(/\s+/g, ' ').trim();
        return {
          id: r.recall_number || `${r.event_id}|${r.report_date}`,
          at: new Date(t).toISOString(),
          title: `${r.recalling_firm || 'Unknown firm'} — ${product.slice(0, 140)}`,
          // openFDA has no per-recall web page; link to the machine-readable
          // record so the claim on the card is checkable.
          url: `https://api.fda.gov/food/enforcement.json?search=recall_number:%22${encodeURIComponent(r.recall_number || '')}%22`,
          severity: /ongoing/i.test(r.status || '') ? 'serious' : 'info',
          meta: {
            status: r.status,
            state: r.state,
            reason: String(r.reason_for_recall || '').slice(0, 200),
            distribution: String(r.distribution_pattern || '').slice(0, 120),
          },
        };
      })
      .filter(Boolean);

    return {
      items,
      meta: {
        window: `${from}–${to}`,
        total: d.meta?.results?.total ?? null,
        lastUpdated: d.meta?.last_updated ?? null,
      },
    };
  },
});

export const drugShortages = defineInstrument({
  id: 'drug-shortages',
  section: 'Recalls & Shortages',
  title: 'Drug products in shortage',
  unit: 'listings',
  decimals: 0,
  cadence: '12h',
  // `at` is FDA's last_updated date (pinned to midnight), so data age is ≥1 day
  // as soon as it publishes and grows between updates. Default 18h window would
  // flag the card as stale even when it holds FDA's current list.
  staleAfter: '14d',
  history: 365,
  source: {
    name: 'openFDA — Drug Shortages',
    url: 'https://open.fda.gov/apis/drug/shortages/',
    license: TERMS,
  },
  // FDA publishes no severity banding for the size of the shortage list, and
  // the count moves with how finely products are broken out, so no thresholds.
  higherIsWorse: true,
  describe:
    'How many drug product listings FDA currently records as being in shortage. Counts packaged products rather than distinct molecules, so read the trend rather than the absolute number.',
  async fetch({ http, now }) {
    const d = await http.json('https://api.fda.gov/drug/shortages.json?count=status');
    const byStatus = Object.fromEntries((d.results || []).map((r) => [r.term, r.count]));
    const value = byStatus.Current;
    if (value == null) throw new Error(`no "Current" bucket in ${JSON.stringify(Object.keys(byStatus))}`);
    const updated = d.meta?.last_updated;
    return {
      value,
      at: /^\d{4}-\d{2}-\d{2}$/.test(String(updated)) ? `${updated}T00:00:00.000Z` : new Date(now).toISOString(),
      meta: { byStatus, lastUpdated: updated ?? null },
    };
  },
});
