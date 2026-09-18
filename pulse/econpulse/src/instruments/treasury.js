// U.S. Treasury Fiscal Data API — "Debt to the Penny".
// Keyless JSON, no key, no documented rate limit. Updated every business day
// around 15:00–16:00 ET with the previous business day's closing balance.
//
//   https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny
//     ?sort=-record_date&page[size]=N
//
// Row: { record_date, tot_pub_debt_out_amt, debt_held_public_amt, intragov_hold_amt }
// — all amounts are strings in dollars.

import { defineInstrument } from '../framework/registry.js';
import { viaProxy } from './_proxy.js';

const URL = 'https://api.fiscaldata.treasury.gov/services/api/fiscal_service'
  + '/v2/accounting/od/debt_to_penny'
  + '?fields=record_date,tot_pub_debt_out_amt,debt_held_public_amt,intragov_hold_amt'
  + '&sort=-record_date&page[size]=520';

const TRILLION = 1e12;

export const federalDebt = defineInstrument({
  id: 'federal-debt',
  section: 'Fiscal',
  title: 'Total public debt outstanding',
  unit: '$T',
  decimals: 3,
  cadence: '6h',
  history: 520,
  // Republished each business day with the prior business day's balance, so the
  // latest record is 1 day old midweek and 3+ across a weekend/holiday.
  staleAfter: '4d',
  higherIsWorse: true,
  // No accepted threshold scale exists for a debt *level* — status stays 'unknown'
  // and the sparkline plus delta carry the story.
  source: {
    name: 'U.S. Treasury — Fiscal Data (Debt to the Penny)',
    url: 'https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/debt-to-the-penny',
    license: 'public domain (U.S. government)',
  },
  describe: 'Every dollar the federal government owes, counted to the cent and republished each business day. Roughly four fifths is held by the public; the rest is owed to government trust funds.',
  async fetch({ http, env }) {
    // fiscaldata 525s (SSL handshake) from this Worker's shared egress IP while
    // returning 200 from a residential one; a homelab job parks it in KV.
    // See _proxy.js. Falls back to a direct fetch when there is none.
    const d = await viaProxy({ env, http, key: 'treasury-debt', url: URL });
    const rows = d?.data || [];
    if (!rows.length) throw new Error('Treasury debt_to_penny: empty data array');

    const series = rows
      .map((r) => [Date.parse(`${r.record_date}T00:00:00Z`), Number(r.tot_pub_debt_out_amt) / TRILLION])
      .filter(([t, v]) => Number.isFinite(t) && Number.isFinite(v))
      .sort((a, b) => a[0] - b[0]);
    if (!series.length) throw new Error('Treasury debt_to_penny: no parseable rows');

    const latest = rows[0];
    const [t, v] = series[series.length - 1];
    const held = Number(latest.debt_held_public_amt);
    const intragov = Number(latest.intragov_hold_amt);
    // Same weekday a year ago is ~253 business rows back; clamp to what we have.
    const yearAgo = series[Math.max(0, series.length - 253)]?.[1] ?? null;

    return {
      value: v,
      at: new Date(t).toISOString(),
      series,
      meta: {
        recordDate: latest.record_date,
        heldByPublicT: Number.isFinite(held) ? Number((held / TRILLION).toFixed(3)) : null,
        intragovernmentalT: Number.isFinite(intragov) ? Number((intragov / TRILLION).toFixed(3)) : null,
        yearOverYearT: yearAgo != null ? Number((v - yearAgo).toFixed(3)) : null,
      },
    };
  },
});
