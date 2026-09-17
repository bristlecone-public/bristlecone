// Instrument registry for this dashboard. Order here = order on the page.
// One file per feed under ./ ; each exports one or more defineInstrument()s.

import { ariEdVisits } from './cdc-nssp-ed-daily.js';
import { iliNational } from './delphi-fluview.js';
import { wastewaterCovid, wastewaterInfluenzaA, wastewaterRsv } from './cdc-nwss-wval.js';
import { edVisitsCovid, edVisitsInfluenza } from './delphi-nssp.js';
import { hospRateCovid, hospRateInfluenza } from './cdc-respnet.js';
import { whoOutbreakNews } from './who-don.js';
import { fdaFoodRecalls, drugShortages } from './openfda.js';
import { heatColdAlerts } from './nws-alerts.js';
import { airnowAqi } from './airnow.js';

export const instruments = [
  // Vitals — the headline read on how much illness is out there right now.
  ariEdVisits,
  iliNational,
  wastewaterCovid,

  // Wastewater — testing-independent early warning for the other two viruses.
  wastewaterInfluenzaA,
  wastewaterRsv,

  // Emergency Dept — illness that actually reached a hospital door.
  edVisitsCovid,
  edVisitsInfluenza,

  // Hospitalizations — the severe end of the curve.
  hospRateCovid,
  hospRateInfluenza,

  // Outbreaks — the global events wall.
  whoOutbreakNews,

  // Recalls & Shortages — the supply side of public health.
  fdaFoodRecalls,
  drugShortages,

  // Environment — acute environmental health hazards.
  heatColdAlerts,
  airnowAqi,
];
