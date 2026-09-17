// CDC RESP-NET — "RESP-NET Rates and Clinical Data" (data.cdc.gov, kvib-3txy).
// Population-based surveillance of laboratory-confirmed hospitalisations for
// COVID-19 (COVID-NET), influenza (FluSurv-NET) and RSV (RSV-NET) across a
// catchment of ~30 million people, expressed as a weekly rate per 100,000.
//
// The table is long-format and heavily faceted (network × age × race × sex ×
// state × rate type), so every query pins the "all people, all sites" slice:
//   state='Overall' age_category='Overall' race='All' sex='All'
//   data_type='Weekly Rate' rate_type='Observed'
// Without the rate_type pin the same date comes back two or three times with
// Observed / Estimated / Age-Adjusted variants.
//
// Where ED-visit percentages measure how much illness shows up at the door,
// this measures how much of it is severe enough to be admitted.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { socrata, socrataPage, socrataDateMs, isoDaysAgo } from './_lib.js';

const DATASET = 'kvib-3txy';

const SOURCE = {
  name: 'CDC RESP-NET (COVID-NET / FluSurv-NET / RSV-NET)',
  url: socrataPage(DATASET),
  license: 'public domain (US Government work)',
};

async function respnet({ http, now }, network) {
  const where = [
    `surveillance_network='${network}'`,
    "state='Overall'",
    "age_category='Overall'",
    "race='All'",
    "sex='All'",
    "data_type='Weekly Rate'",
    "rate_type='Observed'",
    `date > '${isoDaysAgo(now, 800)}'`,
  ].join(' AND ');

  const rows = await http.json(
    socrata(DATASET, { $select: 'date,estimate', $where: where, $order: 'date', $limit: 300 }),
  );
  const series = rows
    .map((r) => [socrataDateMs(r.date), num(r.estimate)])
    .filter(([t, v]) => Number.isFinite(t) && v != null)
    .sort((a, b) => a[0] - b[0]);
  if (!series.length) throw new Error(`no weekly rates for ${network}`);
  const [t, v] = series[series.length - 1];
  return {
    value: v,
    at: new Date(t).toISOString(),
    series,
    meta: { network, rateType: 'Observed', weeks: series.length },
  };
}

function hospInstrument({ id, title, network, describe }) {
  return defineInstrument({
    id,
    section: 'Hospitalizations',
    title,
    unit: 'per 100k / week',
    decimals: 1,
    cadence: '12h', // upstream refreshes weekly
    // Weekly, and RESP-NET's most recent 1–2 weeks are often preliminary/late,
    // so the newest observed week can be 2–3 weeks old in normal operation.
    // Wider window than the other weekly feeds to avoid false "stale".
    staleAfter: '28d',
    history: 160,
    source: SOURCE,
    // RESP-NET rates have no official severity bands — seasonal peaks differ by
    // an order of magnitude between viruses — so the trend carries the meaning.
    higherIsWorse: true,
    describe,
    fetch: (ctx) => respnet(ctx, network),
  });
}

export const hospRateCovid = hospInstrument({
  id: 'hosp-rate-covid',
  title: 'COVID-19 hospitalisation rate',
  network: 'COVID-NET',
  describe:
    'New laboratory-confirmed COVID-19 hospital admissions per 100,000 people per week in CDC COVID-NET catchment areas — the severity end of the curve, and the number that maps most directly onto hospital strain.',
});

export const hospRateInfluenza = hospInstrument({
  id: 'hosp-rate-influenza',
  title: 'Influenza hospitalisation rate',
  network: 'FluSurv-NET',
  describe:
    'New laboratory-confirmed influenza hospital admissions per 100,000 people per week in CDC FluSurv-NET catchment areas. Near zero all summer; a severe season pushes it past 5.',
});
