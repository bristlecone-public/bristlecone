// Instrument registry for this dashboard. Order here = order on the page.
// One file per feed under ./ ; each exports one or more defineInstrument()s.
//
// Sections, in page order:
//   Vitals · Texas / ERCOT · Frequency & Reserves · Prices ·
//   Generation Mix · Carbon · Events

import { ercotDemand } from './ercot-supply-demand.js';
import { usNuclearFleet } from './nrc-reactor-status.js';
import { eiaUs48Demand } from './eia-region-data.js';
import { ercotWindSolar } from './ercot-wind-solar.js';
import { ercotStorage } from './ercot-storage.js';
import { ercotPrc } from './ercot-prc.js';
import { gbFrequency } from './elexon-frequency.js';
import { ercotRtPrice } from './ercot-prices.js';
import { gbMarketPrice } from './elexon-market-index.js';
import { ercotFuelMix } from './ercot-fuel-mix.js';
import { nyisoFuelMix } from './nyiso-fuel-mix.js';
import { gbCarbonIntensity } from './carbon-intensity-gb.js';
import { caisoCo2 } from './caiso-co2.js';
import { gridAlerts } from './nws-grid-alerts.js';

export const instruments = [
  // Vitals — the headline reads: Texas now, the US fleet behind it.
  ercotDemand,
  usNuclearFleet,
  eiaUs48Demand,

  // Texas / ERCOT — what is filling the gap between demand and capacity.
  ercotWindSolar,
  ercotStorage,

  // Frequency & Reserves — the two numbers grid operators actually watch.
  ercotPrc,
  gbFrequency,

  // Prices — scarcity shows up here first.
  ercotRtPrice,
  gbMarketPrice,

  // Generation Mix — what the electrons are being made from.
  ercotFuelMix,
  nyisoFuelMix,

  // Carbon — what that mix costs the atmosphere.
  gbCarbonIntensity,
  caisoCo2,

  // Events — the weather that breaks grids.
  gridAlerts,
];
