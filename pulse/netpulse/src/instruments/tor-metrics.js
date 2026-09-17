// Tor Project metrics — the censorship-circumvention and privacy layer of the
// internet. Both endpoints are keyless CSV with a "#" comment preamble.
//
//   userstats-relay-country.csv?start=&end=&country=all&events=off
//       date,country,users,lower,upper,frac   (country blank = world total)
//   networksize.csv?start=&end=
//       date,relays,bridges
//
// Estimates are published daily and lag ~2 days; ask for a wide window and
// take whatever is there. `frac` is the share of directory authorities that
// reported — low values mean a shaky estimate.
//
// Docs / licence: https://metrics.torproject.org/ (CC0)

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

const DAY = 86_400_000;
const ymd = (ms) => new Date(ms).toISOString().slice(0, 10);

async function torCsv(http, path, now, days) {
  const url = `https://metrics.torproject.org/${path}${path.includes('?') ? '&' : '?'}start=${ymd(now - days * DAY)}&end=${ymd(now)}`;
  return http.csv(url, { csv: { comment: '#' }, timeout: 30_000 });
}

function toSeries(rows, key, keep) {
  const series = rows
    .map((r) => [Date.parse(`${r.date}T00:00:00Z`), num(r[key])])
    .filter(([t, v]) => Number.isFinite(t) && v != null && v > 0)
    .sort((a, b) => a[0] - b[0]);
  if (!series.length) throw new Error(`no usable "${key}" rows`);
  return series.slice(-keep);
}

export const torUsers = defineInstrument({
  id: 'tor-users',
  section: 'Privacy & Tor',
  title: 'Tor users (daily)',
  unit: 'users',
  decimals: 0,
  cadence: '6h',
  history: 365,
  // Estimates publish daily and lag ~2 days, so the observation time is always
  // older than the default staleAfter (18h) — this stops a healthy feed
  // permanently reading as stale.
  staleAfter: '3d',
  source: {
    name: 'Tor Metrics — relay users',
    url: 'https://metrics.torproject.org/userstats-relay-country.html',
    license: 'CC0 1.0',
  },
  higherIsWorse: false,
  describe:
    'Estimated daily users connecting directly to the Tor network worldwide; sharp national spikes usually mean somebody just started blocking something.',
  async fetch({ http, now }) {
    const rows = (await torCsv(http, 'userstats-relay-country.csv?country=all&events=off', now, 400))
      .filter((r) => !r.country); // blank country = world aggregate
    const series = toSeries(rows, 'users', 365);
    const [t, v] = series[series.length - 1];
    const last = rows[rows.length - 1] || {};
    return { value: v, at: new Date(t).toISOString(), series, meta: { reportingFracPct: num(last.frac) } };
  },
});

export const torRelays = defineInstrument({
  id: 'tor-relays',
  section: 'Privacy & Tor',
  title: 'Tor relays',
  unit: 'relays',
  decimals: 0,
  cadence: '6h',
  history: 365,
  // Network-size data lags ~2 days, same as tor-users; without this the default
  // staleAfter (18h) marks a healthy card stale.
  staleAfter: '3d',
  source: {
    name: 'Tor Metrics — network size',
    url: 'https://metrics.torproject.org/networksize.html',
    license: 'CC0 1.0',
  },
  higherIsWorse: false,
  describe:
    'Running relays in the Tor network — the volunteer infrastructure the whole anonymity guarantee rests on; bridges are tracked alongside in the detail.',
  async fetch({ http, now }) {
    const rows = await torCsv(http, 'networksize.csv', now, 400);
    const series = toSeries(rows, 'relays', 365);
    const [t, v] = series[series.length - 1];
    const last = rows[rows.length - 1] || {};
    return { value: v, at: new Date(t).toISOString(), series, meta: { bridges: num(last.bridges) } };
  },
});
