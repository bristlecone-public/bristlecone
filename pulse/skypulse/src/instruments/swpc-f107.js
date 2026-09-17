// F10.7 cm solar radio flux (Penticton), reported three times a day by SWPC.
// The standard proxy for solar EUV output: it drives thermospheric density and
// therefore satellite drag, and it is the input to most ionospheric models.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

const URL = 'https://services.swpc.noaa.gov/json/f107_cm_flux.json';

// SWPC time_tags in this file carry no timezone suffix; they are UTC.
const utc = (s) => Date.parse(`${String(s).replace(' ', 'T')}Z`);

export const f107Flux = defineInstrument({
  id: 'f107-flux',
  section: 'Sun',
  title: 'F10.7 cm solar radio flux',
  unit: 'sfu',
  decimals: 0,
  cadence: '3h', // Penticton reports at ~17:00, 20:00 and 22:00 UTC
  history: 365,
  // The last daily reading stays valid overnight (~19 h between the 22:00 UTC
  // report and the next afternoon's), so the default max(3×cadence, 2h)=9h
  // window would flag a perfectly current index as stale every night.
  staleAfter: '2d',
  source: {
    name: 'NOAA SWPC (Penticton / NRC Canada)',
    url: 'https://www.swpc.noaa.gov/phenomena/f107-cm-radio-emissions',
    license: 'public domain (US Gov)',
  },
  // No hazard scale — 10.7 cm flux is an activity index, not a warning level.
  thresholds: null,
  higherIsWorse: true,
  describe:
    'Radio brightness of the Sun at 10.7 cm, the standard stand-in for its ultraviolet output; higher values puff up the upper atmosphere and drag low-Earth-orbit satellites down faster.',
  async fetch({ http }) {
    const rows = await http.json(URL);
    const parsed = rows
      .map((r) => ({ t: utc(r.time_tag), flux: num(r.flux), schedule: r.reporting_schedule, mean90: num(r.ninety_day_mean) }))
      .filter((r) => Number.isFinite(r.t) && r.flux != null && r.flux > 0)
      .sort((a, b) => a.t - b.t);
    if (!parsed.length) throw new Error('no F10.7 rows');
    const last = parsed[parsed.length - 1];
    const mean90 = [...parsed].reverse().find((r) => r.mean90 != null)?.mean90 ?? null;
    return {
      value: last.flux,
      at: new Date(last.t).toISOString(),
      series: parsed.map((r) => [r.t, r.flux]),
      meta: { reportingSchedule: last.schedule, ninetyDayMean: mean90, observatory: 'Penticton (DRAO), 2800 MHz' },
    };
  },
});
