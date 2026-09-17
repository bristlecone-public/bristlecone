// IODA (Internet Outage Detection and Analysis) — Georgia Tech / CAIDA.
// Detects country-, region- and AS-level connectivity loss by fusing BGP
// withdrawals, active probing (/24 ping) and darknet telescope traffic.
//
// Keyless JSON API, no documented rate limit (be polite: hourly / half-hourly).
//   /v2/outages/alerts?from=<epoch>&until=<epoch>&limit=N
// Alerts come in pairs: an onset alert (level "critical"/"warning", condition
// like "< 0.25") and a matching recovery alert (level "normal"). We only ever
// count / show the non-normal half.
//
// Docs: https://api.ioda.inetintel.cc.gatech.edu/v2/

import { defineInstrument } from '../framework/registry.js';

const API = 'https://api.ioda.inetintel.cc.gatech.edu/v2/outages/alerts';
const HOUR = 3_600_000;

async function alerts(http, now, windowMs, limit = 1000) {
  const until = Math.floor(now / 1000);
  const from = until - Math.floor(windowMs / 1000);
  const d = await http.json(`${API}?from=${from}&until=${until}&limit=${limit}`);
  if (d?.error) throw new Error(`IODA error: ${JSON.stringify(d.error).slice(0, 200)}`);
  return (d?.data || []).filter((a) => a && a.level && a.level !== 'normal');
}

const label = (a) => a?.entity?.name || `${a?.entity?.type} ${a?.entity?.code}`;

export const iodaOutageAlerts = defineInstrument({
  id: 'ioda-outage-alerts',
  section: 'Outages',
  title: 'Outage alerts (6 h)',
  unit: 'alerts',
  decimals: 0,
  cadence: '1h',
  history: 336,
  source: {
    name: 'IODA — Georgia Tech / CAIDA',
    url: 'https://ioda.inetintel.cc.gatech.edu/',
    license: 'CC BY-NC-SA 4.0 (non-commercial)',
  },
  higherIsWorse: true,
  describe:
    'Connectivity-loss alerts IODA raised worldwide in the last six hours across countries, regions and individual networks — background is roughly 100-250.',
  async fetch({ http, now }) {
    const list = await alerts(http, now, 6 * HOUR);
    const by = { country: 0, region: 0, geoasn: 0, asn: 0 };
    for (const a of list) {
      const t = a?.entity?.type;
      if (t in by) by[t] += 1;
    }
    return {
      value: list.length,
      at: new Date(now).toISOString(),
      meta: {
        windowHours: 6,
        countries: by.country,
        regions: by.region,
        networks: by.asn + by.geoasn,
        worst: list
          .filter((a) => a?.entity?.type === 'country' || a?.entity?.type === 'region')
          .slice(0, 5)
          .map(label),
      },
    };
  },
});

export const iodaAlertWall = defineInstrument({
  id: 'ioda-alerts',
  section: 'Outages',
  kind: 'events',
  title: 'Country & region outages',
  cadence: '1h',
  history: 120,
  source: {
    name: 'IODA — Georgia Tech / CAIDA',
    url: 'https://ioda.inetintel.cc.gatech.edu/dashboard',
    license: 'CC BY-NC-SA 4.0 (non-commercial)',
  },
  describe:
    'Every national or sub-national connectivity drop IODA flagged recently — the wall a country-level shutdown shows up on first.',
  async fetch({ http, now }) {
    // AS-level alerts run to hundreds per day; the wall is for outages with a
    // map footprint, so keep country + region only.
    const list = (await alerts(http, now, 12 * HOUR)).filter(
      (a) => a?.entity?.type === 'country' || a?.entity?.type === 'region',
    );
    const items = list.map((a) => {
      const isCountry = a.entity.type === 'country';
      const ts = Number(a.time) * 1000;
      return {
        id: `ioda:${a.datasource}:${a.entity.type}:${a.entity.code}:${a.time}`,
        at: new Date(ts).toISOString(),
        title: `${label(a)} — ${a.datasource} ${a.condition} of normal`,
        severity: isCountry ? 'critical' : 'serious',
        url: `https://ioda.inetintel.cc.gatech.edu/${a.entity.type}/${a.entity.code}`,
        meta: {
          datasource: a.datasource,
          level: a.level,
          value: a.value,
          expected: a.historyValue,
          entityType: a.entity.type,
        },
      };
    });
    return { items, at: new Date(now).toISOString() };
  },
});
