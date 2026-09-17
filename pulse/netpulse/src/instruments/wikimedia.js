// Wikimedia REST "pageviews" analytics API — a good proxy for how much the
// public web is actually being *read*, independent of any one CDN.
//
// Keyless. Requires a descriptive User-Agent (the framework sets site.userAgent).
// Data lands ~24-48h behind and occasionally has a missing day; we filter gaps.
// Docs: https://wikimedia.org/api/rest_v1/#/Pageviews%20data

import { defineInstrument } from '../framework/registry.js';

const BASE = 'https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate';
const DAY = 86_400_000;

// Wikimedia wants YYYYMMDDHH (hour is always 00 for daily granularity).
const stamp = (ms) => new Date(ms).toISOString().slice(0, 10).replace(/-/g, '') + '00';

export const internetPageviews = defineInstrument({
  id: 'internet-pageviews',
  section: 'Vitals',
  title: 'Wikipedia pageviews (human)',
  unit: 'views/day',
  decimals: 0,
  cadence: '6h',
  history: 400,
  // Pageviews land 24-48h behind, so the observation time is always a couple of
  // days old; without this the default staleAfter (max 3×cadence, 2h = 18h)
  // would flag the card stale even when the feed is perfectly healthy.
  staleAfter: '3d',
  source: {
    name: 'Wikimedia Analytics (pageviews API)',
    url: 'https://wikimedia.org/api/rest_v1/',
    license: 'CC0 1.0',
  },
  higherIsWorse: false,
  describe:
    'Daily human (bot-filtered) pageviews across every Wikimedia project — a vendor-neutral pulse of how much the public web is being read.',
  async fetch({ http, now }) {
    const start = stamp(now - 400 * DAY);
    const end = stamp(now);
    const d = await http.json(
      `${BASE}/all-projects/all-access/user/daily/${start}/${end}`,
    );
    const series = (d.items || [])
      .map((it) => {
        const s = String(it.timestamp || '');
        const t = Date.parse(`${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}T00:00:00Z`);
        return [t, Number(it.views)];
      })
      .filter(([t, v]) => Number.isFinite(t) && Number.isFinite(v) && v > 0)
      .sort((a, b) => a[0] - b[0]);
    if (!series.length) throw new Error('no pageview rows returned');
    const [t, v] = series[series.length - 1];
    return { value: v, at: new Date(t).toISOString(), series, meta: { days: series.length } };
  },
});
