// CMU Delphi Epidata — FluView (CDC ILINet), national.
//
// %ILI is the oldest continuous US respiratory signal: the share of outpatient
// visits for influenza-like illness reported by ~4,000 sentinel providers.
// `wili` is the population-weighted version, which is the number CDC compares
// against the national epidemic baseline each season.
//
// Keyless, no rate limit published; CDC publishes new weeks on Friday and
// revises recent ones, so one call returns the whole revised series.
// Docs: https://cmu-delphi.github.io/delphi-epidata/api/fluview.html

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mmwrWeekEndMs, epiweekRange } from './_lib.js';

const API = 'https://api.delphi.cmu.edu/epidata/fluview/';

export const iliNational = defineInstrument({
  id: 'ili-national',
  section: 'Vitals',
  title: 'Influenza-like illness (national %ILI)',
  unit: '% of outpatient visits',
  decimals: 2,
  cadence: '12h',
  // Weekly feed: `at` is the MMWR week-ending Saturday, so the newest available
  // point is 7–14 days old normally. Set so the card only reads "stale" when an
  // update is genuinely missed, not on every render.
  staleAfter: '21d',
  history: 200,
  source: {
    name: 'CDC ILINet via CMU Delphi Epidata',
    url: 'https://cmu-delphi.github.io/delphi-epidata/api/fluview.html',
    license: 'CC BY (Delphi) over CDC public-domain data',
  },
  // CDC's national ILI epidemic baseline has sat near 3% in recent seasons;
  // above it is "elevated". 5% / 7% mark moderate and high seasons.
  thresholds: [
    { level: 'critical', gte: 7 },
    { level: 'serious', gte: 5 },
    { level: 'warning', gte: 3 },
  ],
  higherIsWorse: true,
  describe:
    'Weighted share of outpatient doctor visits for influenza-like illness across CDC sentinel providers. Above roughly 3% means flu season is genuinely underway, not just background coughs.',
  async fetch({ http, now }) {
    const d = await http.json(`${API}?regions=nat&epiweeks=${epiweekRange(now, 3)}`);
    if (d.result !== 1) throw new Error(`epidata result ${d.result}: ${d.message || 'no data'}`);
    const series = (d.epidata || [])
      .map((r) => [mmwrWeekEndMs(r.epiweek), num(r.wili)])
      .filter(([t, v]) => Number.isFinite(t) && v != null)
      .sort((a, b) => a[0] - b[0]);
    if (!series.length) throw new Error('fluview returned no usable weeks');
    const last = d.epidata[d.epidata.length - 1];
    const [t, v] = series[series.length - 1];
    return {
      value: v,
      at: new Date(t).toISOString(),
      series,
      meta: { epiweek: last?.epiweek, providers: last?.num_providers, issue: last?.issue },
    };
  },
});
