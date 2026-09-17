// Instrument registry for this dashboard. Order here = order on the page.
// One file per feed under ./ ; each exports one or more defineInstrument()s.

import { kpPlanetary } from './swpc-kp.js';
import { goesXrayFlux } from './swpc-goes-xray.js';
import { solarWindSpeed, solarWindBz } from './swpc-solar-wind.js';
import { sunspotNumber } from './swpc-solar-cycle.js';
import { f107Flux } from './swpc-f107.js';
import { solarFlares } from './swpc-flares.js';
import { noaaScales } from './swpc-scales.js';
import { auroraHemisphericPower } from './swpc-aurora-power.js';
import { protonFlux10MeV, electronFlux2MeV } from './swpc-goes-particles.js';
import { issAltitude } from './celestrak-iss.js';
import { neoClosestApproach, neoCloseApproaches } from './jpl-neo.js';
import { swpcAlerts } from './swpc-alerts.js';
import { donkiCme } from './nasa-donki.js';

export const instruments = [
  // Vitals — the four numbers that describe space weather right now.
  kpPlanetary,
  goesXrayFlux,
  solarWindSpeed,
  sunspotNumber,

  // Sun
  f107Flux,
  solarFlares,

  // Solar Wind
  solarWindBz,

  // Geomagnetic & Aurora
  noaaScales,
  auroraHemisphericPower,

  // Radiation
  protonFlux10MeV,
  electronFlux2MeV,

  // Orbit
  issAltitude,

  // Near-Earth Objects
  neoClosestApproach,

  // Events
  swpcAlerts,
  neoCloseApproaches,
  donkiCme,
];
