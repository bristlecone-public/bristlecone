// CMU Delphi Epidata — covidcast, `nssp` source: CDC's National Syndromic
// Surveillance Program weekly percentage of emergency department visits with a
// COVID-19 / influenza / RSV diagnosis, at the national level.
//
// Delphi returns the whole weekly series in one keyless call, which is why this
// is used here rather than the equivalent Socrata table. Upstream is weekly
// (Fridays); `time_type=week` means `time_values` are MMWR epiweeks.
// Docs: https://cmu-delphi.github.io/delphi-epidata/api/covidcast-signals/nssp.html

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mmwrWeekEndMs, epiweekRange } from './_lib.js';

const API = 'https://api.delphi.cmu.edu/epidata/covidcast/';

const SOURCE = {
  name: 'CDC NSSP via CMU Delphi Epidata',
  url: 'https://cmu-delphi.github.io/delphi-epidata/api/covidcast-signals/nssp.html',
  license: 'public domain (US Government work), served by CMU Delphi',
};

async function nsspSignal({ http, now }, signal) {
  const url =
    `${API}?data_source=nssp&signal=${signal}` +
    `&geo_type=nation&geo_value=us&time_type=week&time_values=${epiweekRange(now, 3)}`;
  const d = await http.json(url);
  if (d.result !== 1) throw new Error(`covidcast result ${d.result}: ${d.message || 'no data'}`);
  const series = (d.epidata || [])
    .map((r) => [mmwrWeekEndMs(r.time_value), num(r.value)])
    .filter(([t, v]) => Number.isFinite(t) && v != null)
    .sort((a, b) => a[0] - b[0]);
  if (!series.length) throw new Error(`signal ${signal} returned no usable weeks`);
  const [t, v] = series[series.length - 1];
  const last = d.epidata[d.epidata.length - 1];
  return {
    value: v,
    at: new Date(t).toISOString(),
    series,
    meta: { signal, epiweek: last?.time_value, issue: last?.issue, weeks: series.length },
  };
}

function edInstrument({ id, title, signal, describe }) {
  return defineInstrument({
    id,
    section: 'Emergency Dept',
    title,
    unit: '% of ED visits',
    decimals: 2,
    cadence: '12h', // upstream is weekly
    // Weekly feed keyed by epiweek; newest point is 7–14 days old normally, so
    // the default 36h stale window would flag a healthy card. See cdc-nwss-wval.
    staleAfter: '21d',
    history: 160,
    source: SOURCE,
    // No accepted national cut-offs for these percentages, so no thresholds:
    // the shape of the curve is the signal, not any fixed line.
    higherIsWorse: true,
    describe,
    fetch: (ctx) => nsspSignal(ctx, signal),
  });
}

export const edVisitsCovid = edInstrument({
  id: 'ed-visits-covid',
  title: 'COVID-19 ED visits',
  signal: 'pct_ed_visits_covid',
  describe:
    'Share of US emergency department visits with a COVID-19 diagnosis. Unlike case counts this does not depend on home testing or reporting habits, so it stays comparable season to season.',
});

export const edVisitsInfluenza = edInstrument({
  id: 'ed-visits-influenza',
  title: 'Influenza ED visits',
  signal: 'pct_ed_visits_influenza',
  describe:
    'Share of US emergency department visits with an influenza diagnosis — the sharpest weekly marker of where the flu season sits, peaking well above 5% in bad years.',
});
