// ISS mean orbital altitude, derived from the current CelesTrak GP element set.
//
// The published element set gives mean motion (revolutions/day); inverting Kepler's
// third law gives the mean semi-major axis, and subtracting Earth's equatorial
// radius gives a mean altitude. That is a much cleaner decay/reboost trace than an
// instantaneous altitude, which swings ±5 km every orbit.

import { defineInstrument } from '../framework/registry.js';
import { viaProxy } from './_proxy.js';
import { num } from '../framework/http.js';

const URL = 'https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=json';
const MU = 398600.4418; // km³/s², Earth's gravitational parameter
const R_EARTH = 6378.137; // km, WGS-84 equatorial radius

export const issAltitude = defineInstrument({
  id: 'iss-altitude',
  section: 'Orbit',
  title: 'ISS mean altitude',
  unit: 'km',
  decimals: 1,
  cadence: '6h', // element sets are refreshed a few times a day
  history: 480, // ~4 months at 6-hourly sampling
  source: {
    name: 'CelesTrak GP element sets (Space-Track/USSF data)',
    url: 'https://celestrak.org/NORAD/elements/gp.php?CATNR=25544',
    license: 'US Government orbital data, free redistribution; see celestrak.org/publications',
  },
  // Altitude has no hazard scale; the interesting signal is the sawtooth of
  // atmospheric decay punctuated by reboosts.
  thresholds: null,
  higherIsWorse: false,
  describe:
    'Mean altitude of the International Space Station above Earth’s equator, computed from its latest published orbit; it decays a few hundred metres a week from atmospheric drag until a reboost pushes it back up.',
  async fetch({ http, env }) {
    // CelesTrak 522s this Worker's shared egress IP; a homelab job parks the
    // payload in KV. See _proxy.js. Falls back to a direct fetch when absent.
    const rows = await viaProxy({ env, http, key: 'celestrak-iss', url: URL });
    const gp = Array.isArray(rows) ? rows[0] : rows;
    const meanMotion = num(gp?.MEAN_MOTION); // revolutions per day
    if (!meanMotion) throw new Error('no MEAN_MOTION in GP record');
    const n = (meanMotion * 2 * Math.PI) / 86400; // rad/s
    const a = Math.cbrt(MU / (n * n)); // km, mean semi-major axis
    const e = num(gp.ECCENTRICITY) ?? 0;
    // EPOCH carries microseconds; Date.parse only guarantees milliseconds.
    const epoch = `${String(gp.EPOCH).replace(/(\.\d{3})\d+$/, '$1')}Z`;
    const t = Date.parse(epoch);
    if (!Number.isFinite(t)) throw new Error(`unparseable EPOCH "${gp.EPOCH}"`);
    return {
      value: a - R_EARTH,
      at: new Date(t).toISOString(),
      meta: {
        object: gp.OBJECT_NAME,
        noradId: gp.NORAD_CAT_ID,
        periodMin: Number((1440 / meanMotion).toFixed(2)),
        inclinationDeg: num(gp.INCLINATION),
        eccentricity: e,
        perigeeKm: Number((a * (1 - e) - R_EARTH).toFixed(1)),
        apogeeKm: Number((a * (1 + e) - R_EARTH).toFixed(1)),
        revAtEpoch: gp.REV_AT_EPOCH ?? null,
        note: 'Mean altitude from Kepler inversion of the SGP4 mean motion (±~1 km vs osculating).',
      },
    };
  },
});
