// Events wall: "Data releases & Fed".
//
// Three official RSS feeds merged into one stream, newest first:
//   Federal Reserve — monetary policy press releases (FOMC statements, minutes, SEP)
//     https://www.federalreserve.gov/feeds/press_monetary.xml
//     (press_all.xml exists but is dominated by bank enforcement actions and orders,
//      which would bury the macro signal — see docs/INSTRUMENTS.md)
//   Bureau of Economic Analysis — news releases (GDP, PCE, trade)
//     https://apps.bea.gov/rss/rss.xml
//   Census Bureau — Economic Indicators (retail sales, housing starts, durable goods)
//     https://www.census.gov/economic-indicators/indicator.xml
//
// All keyless, all plain RSS 2.0. Feeds are fetched independently: one dead feed
// degrades the wall instead of blanking it. Only if *every* feed fails do we throw,
// so the collector keeps the previous items.
//
// Dedupe key: the Census guid is a stable slug ("retail_sales") that repeats every
// month, so ids are always <source>|<guid-or-link>|<timestamp>.

import { defineInstrument } from '../framework/registry.js';

const FEEDS = [
  { tag: 'Fed', url: 'https://www.federalreserve.gov/feeds/press_monetary.xml' },
  { tag: 'BEA', url: 'https://apps.bea.gov/rss/rss.xml' },
  { tag: 'Census', url: 'https://www.census.gov/economic-indicators/indicator.xml' },
];

const MAX_AGE_MS = 400 * 86_400_000; // drop the long BEA tail of old annual releases

// Rate decisions move markets on the minute; the big monthly prints move them on
// the day; everything else is background.
const MARKET_MOVING = /FOMC statement|federal funds|target range|monetary policy|economic projections|discount rate/i;
const HEADLINE_DATA = /\bGDP\b|Personal Income and Outlays|Retail (and Food Services )?Sales|Advance Monthly Sales|Housing Starts|New Residential (Construction|Sales)|International Trade|Durable Goods|Shipments, Inventories, and Orders/i;

function severityFor(tag, title) {
  if (tag === 'Fed' && MARKET_MOVING.test(title)) return 'serious';
  if (HEADLINE_DATA.test(title)) return 'warning';
  return 'info';
}

export const dataReleases = defineInstrument({
  id: 'data-releases',
  section: 'Events',
  kind: 'events',
  title: 'Data releases & Fed',
  cadence: '6h',
  history: 120,
  source: {
    name: 'Federal Reserve Board · BEA · Census Bureau (RSS)',
    url: 'https://www.federalreserve.gov/feeds/feeds.htm',
    license: 'public domain (U.S. government)',
  },
  describe: 'Every official US macro release and Fed policy announcement as it publishes — the calendar behind every other number on this page. Rate decisions are flagged red, headline prints amber.',
  async fetch({ http, now }) {
    const settled = await Promise.allSettled(
      FEEDS.map(async (f) => ({ tag: f.tag, entries: await http.feed(f.url) })),
    );

    const items = [];
    const sources = {};
    for (let i = 0; i < settled.length; i++) {
      const r = settled[i];
      const { tag, url } = FEEDS[i];
      if (r.status !== 'fulfilled') {
        sources[tag] = `error: ${String(r.reason?.message || r.reason).slice(0, 120)}`;
        continue;
      }
      let kept = 0;
      for (const e of r.value.entries) {
        const t = Date.parse(e.at);
        if (!Number.isFinite(t) || now - t > MAX_AGE_MS) continue;
        const title = (e.title || '').replace(/\s+/g, ' ').trim();
        if (!title) continue;
        items.push({
          id: `${tag}|${e.id || e.link || title}|${t}`,
          at: new Date(t).toISOString(),
          title: `${tag} · ${title}`,
          url: e.link || url,
          severity: severityFor(tag, title),
          meta: { source: tag },
        });
        kept++;
      }
      sources[tag] = `${kept} items`;
    }

    if (!items.length) throw new Error(`no items from any feed: ${JSON.stringify(sources)}`);
    items.sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
    return { items, at: items[0].at, meta: { sources } };
  },
});
