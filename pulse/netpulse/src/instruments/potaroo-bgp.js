// Global BGP table size, from Geoff Huston's long-running AS65000 route-view
// collector at APNIC (bgp.potaroo.net). These files are the canonical public
// record of "how many routes does a default-free router have to hold".
//
// Format: one "<unix-seconds> <prefix-count>" line per sample, hourly, back to
// 1988 (v4) / 2003 (v6) — the full files are 3-5 MB, so we ask for the tail
// with a Range request (the server answers 206 with accept-ranges: bytes) and
// downsample to one point per UTC day.
//
// Source pages: https://bgp.potaroo.net/index-bgp.html

import { defineInstrument } from '../framework/registry.js';

// ~200 kB of tail is ~450 days of hourly samples for both files.
const TAIL_BYTES = 200_000;

async function dailySeries(http, url) {
  const text = await http.text(url, { headers: { range: `bytes=-${TAIL_BYTES}` }, timeout: 30_000 });
  // A range response almost certainly starts mid-line; drop the first fragment.
  const lines = text.split('\n').slice(1);
  const byDay = new Map(); // last sample of each UTC day wins
  for (const line of lines) {
    const parts = line.trim().split(/\s+/);
    if (parts.length !== 2) continue;
    const t = Number(parts[0]) * 1000;
    const v = Number(parts[1]);
    if (!Number.isFinite(t) || !Number.isFinite(v) || v <= 0) continue;
    byDay.set(new Date(t).toISOString().slice(0, 10), v);
  }
  const series = [...byDay.entries()]
    .map(([d, v]) => [Date.parse(`${d}T00:00:00Z`), v])
    .sort((a, b) => a[0] - b[0]);
  if (series.length < 2) throw new Error(`only ${series.length} usable samples from ${url}`);
  return series;
}

export const bgpTableV4 = defineInstrument({
  id: 'bgp-table-v4',
  section: 'Routing',
  title: 'IPv4 BGP table size',
  unit: 'prefixes',
  decimals: 0,
  cadence: '1d',
  history: 365,
  source: {
    name: 'APNIC / Geoff Huston — AS65000 BGP route view',
    url: 'https://bgp.potaroo.net/index-bgp.html',
    license: 'free to use with attribution',
  },
  higherIsWorse: false,
  describe:
    'Active IPv4 prefixes in the global routing table — the memory every default-free router in the world has to carry, and a slow measure of the internet growing and fragmenting.',
  async fetch({ http }) {
    const series = await dailySeries(http, 'https://bgp.potaroo.net/as2.0/bgp-active.txt');
    const [t, v] = series[series.length - 1];
    return { value: v, at: new Date(t).toISOString(), series };
  },
});

export const bgpTableV6 = defineInstrument({
  id: 'bgp-table-v6',
  section: 'Routing',
  title: 'IPv6 BGP table size',
  unit: 'prefixes',
  decimals: 0,
  cadence: '1d',
  history: 365,
  source: {
    name: 'APNIC / Geoff Huston — AS65000 BGP route view (IPv6)',
    url: 'https://bgp.potaroo.net/index-bgp.html',
    license: 'free to use with attribution',
  },
  higherIsWorse: false,
  describe:
    'Active IPv6 prefixes in the global routing table — still a quarter the size of the IPv4 table, and the clearest measure of IPv6 actually being routed.',
  async fetch({ http }) {
    const series = await dailySeries(http, 'https://bgp.potaroo.net/v6/as2.0/bgp-active.txt');
    const [t, v] = series[series.length - 1];
    return { value: v, at: new Date(t).toISOString(), series };
  },
});
