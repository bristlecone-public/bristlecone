// NASA/JPL CNEOS close-approach data (keyless).
// One query (next 30 days, inside 0.05 au) feeds both a metric — how close the
// nearest upcoming pass gets, in lunar distances — and the upcoming-approach wall.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

const CAD = 'https://ssd-api.jpl.nasa.gov/cad.api?date-min=now&date-max=%2B30&dist-max=0.05&sort=dist&fullname=true';
const AU_KM = 149597870.7;
const LD_KM = 384400; // mean Earth–Moon distance
const AU_PER_LD = LD_KM / AU_KM;

const SOURCE = {
  name: 'NASA/JPL CNEOS close-approach API',
  url: 'https://ssd-api.jpl.nasa.gov/doc/cad.html',
  license: 'public domain (NASA/JPL-Caltech)',
};

const MONTHS = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 };

// CNEOS calendar dates look like "2026-Aug-23 20:59" and are TDB/UTC to the minute.
function parseCd(cd) {
  const m = /^(\d{4})-([A-Za-z]{3})-(\d{2})\s+(\d{2}):(\d{2})/.exec(String(cd));
  if (!m) return NaN;
  return Date.UTC(+m[1], MONTHS[m[2]], +m[3], +m[4], +m[5]);
}

// Rough diameter from absolute magnitude H at an assumed 0.14 albedo.
const diameterM = (h) => (h == null ? null : Math.round(3550.9 * 10 ** (-h / 5) * 1000));

async function loadApproaches(http) {
  const doc = await http.json(CAD);
  const f = Object.fromEntries((doc.fields || []).map((name, i) => [name, i]));
  return (doc.data || [])
    .map((row) => {
      const distAu = num(row[f.dist]);
      const h = num(row[f.h]);
      return {
        des: row[f.des],
        fullname: String(row[f.fullname] ?? row[f.des]).trim(),
        t: parseCd(row[f.cd]),
        cd: row[f.cd],
        distAu,
        distLd: distAu == null ? null : distAu / AU_PER_LD,
        distKm: distAu == null ? null : distAu * AU_KM,
        vRelKms: num(row[f.v_rel]),
        h,
        diameterM: diameterM(h),
      };
    })
    .filter((r) => Number.isFinite(r.t) && r.distLd != null);
}

const sbdb = (des) => `https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr=${encodeURIComponent(des)}`;

export const neoClosestApproach = defineInstrument({
  id: 'neo-closest-approach',
  section: 'Near-Earth Objects',
  title: 'Closest approach in next 30 days',
  unit: 'LD',
  decimals: 2,
  cadence: '6h',
  history: 240, // 60 days at 6-hourly sampling
  source: SOURCE,
  // No official hazard scale keys off miss distance, but two landmarks are
  // universally used: 1 lunar distance (384,400 km) and the geostationary belt
  // (42,164 km from Earth's centre ≈ 0.11 LD), which is where our satellites live.
  thresholds: [
    { level: 'critical', lte: 0.11 },
    { level: 'serious', lte: 0.5 },
    { level: 'warning', lte: 1 },
  ],
  higherIsWorse: false,
  describe:
    'How close the nearest known asteroid gets to Earth in the next 30 days, measured in lunar distances (1 LD = 384,400 km); anything under 1 LD passes inside the Moon’s orbit.',
  async fetch({ http, now }) {
    const rows = await loadApproaches(http);
    if (!rows.length) throw new Error('no close approaches returned');
    const closest = rows.reduce((a, b) => (b.distLd < a.distLd ? b : a));
    return {
      value: Number(closest.distLd.toFixed(4)),
      at: new Date(now).toISOString(),
      meta: {
        object: closest.fullname,
        designation: closest.des,
        approachUtc: new Date(closest.t).toISOString(),
        distKm: Math.round(closest.distKm),
        relativeSpeedKms: closest.vRelKms,
        absoluteMagnitudeH: closest.h,
        estDiameterM: closest.diameterM,
        approachesWithin0_05au: rows.length,
        insideLunarDistance: rows.filter((r) => r.distLd <= 1).length,
      },
    };
  },
});

export const neoCloseApproaches = defineInstrument({
  id: 'neo-close-approaches',
  section: 'Events',
  kind: 'events',
  title: 'Upcoming asteroid close approaches',
  cadence: '6h',
  history: 80,
  source: SOURCE,
  describe:
    'Every known asteroid due to pass within 0.05 au (about 19 lunar distances) of Earth in the next 30 days, newest predicted pass first.',
  async fetch({ http }) {
    const rows = await loadApproaches(http);
    const items = rows.map((r) => ({
      id: `cad-${r.des}-${r.cd}`,
      at: new Date(r.t).toISOString(),
      // These events are in the *future*; the framework sorts an events wall
      // newest-first and renders relative ages, so the date is spelled out in the
      // title to keep each row readable on its own.
      title: `${r.cd} UTC · ${r.fullname} — ${r.distLd.toFixed(2)} LD (${Math.round(r.distKm).toLocaleString('en-US')} km) at ${r.vRelKms?.toFixed(1) ?? '?'} km/s${r.diameterM ? `, ~${r.diameterM} m` : ''}`,
      severity: r.distLd <= 0.11 ? 'critical' : r.distLd <= 0.5 ? 'serious' : r.distLd <= 1 ? 'warning' : 'info',
      url: sbdb(r.des),
      meta: { distLd: Number(r.distLd.toFixed(4)), distKm: Math.round(r.distKm), vRelKms: r.vRelKms, h: r.h, estDiameterM: r.diameterM },
    }));
    return { items };
  },
});
