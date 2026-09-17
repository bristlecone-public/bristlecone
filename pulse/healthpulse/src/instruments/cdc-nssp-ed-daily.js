// CDC NSSP "Emergency Department Respiratory Daily" (data.cdc.gov, dataset
// vjzj-u7u8): percent of all ED visits with a given respiratory diagnosis, at
// daily resolution for the US and each state. Keyless Socrata JSON.
//
// The ARI (acute respiratory illness) line is the broadest, fastest-moving
// single number in US respiratory surveillance, which makes it the headline
// vital sign here. CDC republishes the file weekly (Fridays) but the rows
// themselves are daily, so one fetch backfills a year of sparkline.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { socrata, socrataPage, socrataDateMs, isoDaysAgo } from './_lib.js';

const DATASET = 'vjzj-u7u8';

const SOURCE = {
  name: 'CDC NSSP (Emergency Department Respiratory Daily)',
  url: socrataPage(DATASET),
  license: 'public domain (US Government work)',
};

async function edDaily({ http, now }, pathogen) {
  const rows = await http.json(
    socrata(DATASET, {
      $select: 'date,percent_visits',
      $where: `geography='United States' AND pathogen='${pathogen}' AND date > '${isoDaysAgo(now, 400)}'`,
      $order: 'date',
      $limit: 600,
    }),
  );
  const series = rows
    .map((r) => [socrataDateMs(r.date), num(r.percent_visits)])
    .filter(([t, v]) => Number.isFinite(t) && v != null);
  if (!series.length) throw new Error(`no ${pathogen} rows for geography='United States'`);
  const [t, v] = series[series.length - 1];
  return {
    value: v,
    at: new Date(t).toISOString(),
    series,
    meta: { geography: 'United States', pathogen, days: series.length },
  };
}

export const ariEdVisits = defineInstrument({
  id: 'ari-ed-visits',
  section: 'Vitals',
  title: 'ED visits for acute respiratory illness',
  unit: '% of ED visits',
  decimals: 2,
  cadence: '12h',
  // Rows are daily but the file is republished weekly (Fridays), so the newest
  // daily point is typically 7–13 days old. Without this the default 18h window
  // flags the card as stale on every render.
  staleAfter: '21d',
  history: 400,
  source: SOURCE,
  // No official banding exists for this percentage — CDC grades ARI activity by
  // state percentile, not by fixed cut-offs. Left unthresholded on purpose.
  higherIsWorse: true,
  describe:
    'Share of all US emergency department visits with an acute respiratory illness diagnosis — the broadest daily read on how much respiratory disease is actually reaching hospitals. Summer floor is around 6%; winter peaks have run past 20%.',
  fetch: (ctx) => edDaily(ctx, 'ARI'),
});
