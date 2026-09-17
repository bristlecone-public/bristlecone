// Instrument registry for this dashboard. Order here = order on the page.
// One file per feed under ./ ; each exports one or more defineInstrument()s.

import {
  yieldCurve,
  weeklyEconomicIndex,
  gdpNow,
  treasury10y,
  mortgage30y,
  cpiYoY,
  gasPrice,
  unemploymentRate,
  initialClaims,
  vix,
  highYieldSpread,
} from './fred.js';
import { effectiveFedFunds } from './nyfed.js';
import { federalDebt } from './treasury.js';
import { sp500 } from './yahoo.js';
import { fomcOdds, recessionOdds } from './kalshi.js';
import { dataReleases } from './releases.js';

export const instruments = [
  // Vitals — the three numbers to read first.
  yieldCurve,
  weeklyEconomicIndex,
  gdpNow,

  // Rates — the price of money, from overnight out to thirty years.
  effectiveFedFunds,
  treasury10y,
  mortgage30y,

  // Prices — what inflation feels like.
  cpiYoY,
  gasPrice,

  // Labor — the fastest and the slowest labour indicators.
  unemploymentRate,
  initialClaims,

  // Markets — risk appetite and credit stress.
  sp500,
  vix,
  highYieldSpread,

  // Fiscal
  federalDebt,

  // Prediction markets — what real money expects next.
  fomcOdds,
  recessionOdds,

  // Events
  dataReleases,
];
