// CDC National Wastewater Surveillance System — Wastewater Viral Activity Level
// (data.cdc.gov, dataset atcp-73re). Weekly WVAL per sampling site for
// SARS-CoV-2, Influenza A and RSV, updated Fridays.
//
// CDC publishes WVAL per *site*, not as a single national number, so we ask
// Socrata to aggregate: mean site WVAL per week across every reporting site
// (~1,000 sites). That is an unweighted site mean, not CDC's official national
// figure — `meta.sites` always reports how many sites went into it.
//
// The newest week is still filling in for a few days after publication, so a
// trailing week reporting far fewer sites than the week before is dropped
// rather than shown as a fake dip.
//
// Two upstream quirks are handled here:
//
//  1. `site_wval` is contaminated. A small share of rows carry raw
//     concentration values instead of the normalized index — as of 2026-09 the
//     column maxes out at 1.25e4 (SARS-CoV-2), 6.9e8 (influenza A) and ~2.7e21
//     (RSV); these grow as new contaminated rows land. A single such row
//     annihilates a mean taken over ~1,000 sites (unguarded, the RSV weekly mean
//     for the week ending 2025-01-25 comes out at ~2.1e8), so rows above
//     WVAL_CEILING are dropped. The cut is deliberately far above the real
//     scale (CDC's top named category is "Very High" at ≥8, and the genuine
//     tail runs continuously to ~50): re-running the January 2026 COVID surge
//     with and without the guard gives identical weekly means to 2 dp, while a
//     tighter cut at 15 would understate those same weeks by ~30%.
//  2. `avg()` is used rather than `median()` — SoQL's median returns integers
//     on this column, which flattens the whole series to "1" out of season.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { socrata, socrataPage, socrataDateMs, isoDaysAgo } from './_lib.js';

const DATASET = 'atcp-73re';

const SOURCE = {
  name: 'CDC NWSS — Wastewater Viral Activity Level',
  url: socrataPage(DATASET),
  license: 'public domain (US Government work)',
};

// CDC's published WVAL categories: <1.5 Very Low, 1.5–3 Low, 3–4.5 Moderate,
// 4.5–8 High, ≥8 Very High. Mapped onto the framework's four levels.
const WVAL_THRESHOLDS = [
  { level: 'critical', gte: 8 },
  { level: 'serious', gte: 4.5 },
  { level: 'warning', gte: 3 },
];

// A trailing week with less than this share of the prior week's sites is
// treated as incomplete reporting rather than a real drop.
const COMPLETE_ENOUGH = 0.8;

// Rows above this are data errors, not very high viral activity — see header.
const WVAL_CEILING = 100;

async function wval({ http, now }, target) {
  const rows = await http.json(
    socrata(DATASET, {
      $select: 'week_end,avg(site_wval) AS wval,count(site) AS sites',
      $where: `pathogen_target='${target}' AND site_wval <= ${WVAL_CEILING} AND week_end > '${isoDaysAgo(now, 800)}'`,
      $group: 'week_end',
      $order: 'week_end',
      $limit: 300,
    }),
  );
  const pts = rows
    .map((r) => ({ t: socrataDateMs(r.week_end), v: num(r.wval), n: num(r.sites) }))
    .filter((p) => Number.isFinite(p.t) && p.v != null)
    .sort((a, b) => a.t - b.t);

  while (pts.length > 1 && pts[pts.length - 1].n < COMPLETE_ENOUGH * pts[pts.length - 2].n) pts.pop();
  if (!pts.length) throw new Error(`no WVAL weeks for pathogen_target='${target}'`);

  const last = pts[pts.length - 1];
  return {
    value: Math.round(last.v * 100) / 100,
    at: new Date(last.t).toISOString(),
    series: pts.map((p) => [p.t, Math.round(p.v * 100) / 100]),
    meta: {
      pathogenTarget: target,
      sites: last.n,
      aggregation: `unweighted mean of site WVAL (rows > ${WVAL_CEILING} excluded as data errors)`,
    },
  };
}

function wvalInstrument({ id, section, title, target, describe }) {
  return defineInstrument({
    id,
    section,
    title,
    unit: 'WVAL',
    decimals: 2,
    cadence: '12h', // upstream refreshes weekly (Fridays)
    // Weekly feed: `at` is the week-ending date, so the freshest available point
    // is routinely 7–14 days old. Without this, the default 36h window flags
    // every card as stale even when it holds the newest published week.
    staleAfter: '21d',
    history: 160, // ~3 years of weeks
    source: SOURCE,
    thresholds: WVAL_THRESHOLDS,
    higherIsWorse: true,
    describe,
    fetch: (ctx) => wval(ctx, target),
  });
}

export const wastewaterCovid = wvalInstrument({
  id: 'wastewater-covid',
  section: 'Vitals',
  title: 'SARS-CoV-2 in wastewater',
  target: 'SARS-CoV-2',
  describe:
    'Unweighted mean of CDC\'s per-site wastewater viral activity for SARS-CoV-2 across ~1,000 US sewersheds — each site counts equally, so this is not CDC\'s population-weighted national figure. Wastewater does not depend on anyone seeking care or getting tested, so it usually turns up a week or two before cases and hospital visits do. 3 is CDC "moderate", 4.5 "high", 8 "very high".',
});

export const wastewaterInfluenzaA = wvalInstrument({
  id: 'wastewater-influenza-a',
  section: 'Wastewater',
  title: 'Influenza A in wastewater',
  target: 'Influenza A virus',
  describe:
    'Unweighted mean of CDC\'s per-site wastewater viral activity for influenza A across reporting US sewersheds (each site weighted equally, not population-weighted) — an early, testing-independent read on the flu season ramping up.',
});

export const wastewaterRsv = wvalInstrument({
  id: 'wastewater-rsv',
  section: 'Wastewater',
  title: 'RSV in wastewater',
  target: 'RSV',
  describe:
    'Unweighted mean of CDC\'s per-site wastewater viral activity for respiratory syncytial virus across reporting US sewersheds (each site weighted equally, not population-weighted). RSV drives the winter surge in infant and older-adult hospitalisations, and wastewater catches it before clinical testing does.',
});
