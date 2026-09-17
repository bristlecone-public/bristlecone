// Instrument registry for this dashboard. Order here = order on the page.
// One file per feed under ./ ; each exports one or more defineInstrument()s.

import { internetPageviews } from './wikimedia.js';
import { providersDegraded, providerIncidents } from './statuspage.js';
import { radarL7Attacks, radarBgpAnomalies, radarHttp3Share } from './cloudflare-radar.js';
import { iodaOutageAlerts, iodaAlertWall } from './ioda.js';
import { bgpTableV4, bgpTableV6 } from './potaroo-bgp.js';
import { ipv6Capable } from './apnic-ipv6.js';
import { npmDownloads } from './npm-registry.js';
import { torUsers, torRelays } from './tor-metrics.js';

export const instruments = [
  // Vitals — is the internet up, and how hostile is it right now?
  internetPageviews,
  providersDegraded,
  radarL7Attacks,

  // Outages — who just fell off the map
  iodaOutageAlerts,
  iodaAlertWall,

  // Routing — the control plane everything else rides on
  bgpTableV4,
  bgpTableV6,
  radarBgpAnomalies,

  // Adoption — the slow protocol migrations
  ipv6Capable,
  radarHttp3Share,

  // Ecosystem — the software supply chain
  npmDownloads,

  // Privacy & Tor
  torUsers,
  torRelays,

  // Incidents — the events wall
  providerIncidents,
];
