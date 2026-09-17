// Instrument registry for this dashboard. Order here = order on the page.
// One file per feed under ./ ; each exports one or more defineInstrument()s.

import { hfNewModels, hfLabReleases, hfDailyPapers } from './huggingface.js';
import { aiProvidersDegraded, aiIncidents } from './aistatus.js';
import { openrouterModels, openrouterLongCtxPrice } from './openrouter.js';
import { arxivAiPapers } from './arxiv.js';
import { epochFrontierModels, epochLargestCluster } from './epoch.js';
import { aaIntelligenceIndex } from './artificialanalysis.js';
import { gpuSpotPrice } from './vastai.js';
import { npmAiSdkDownloads } from './npmdownloads.js';
import { labAnnouncements } from './announcements.js';

export const instruments = [
  // Vitals — the headline numbers.
  hfNewModels,
  aiProvidersDegraded,

  // Models — what is being shipped and what you can actually call.
  openrouterModels,
  hfLabReleases,

  // Research — how much is being published.
  arxivAiPapers,
  hfDailyPapers,

  // Frontier & benchmarks — the compute and capability ceiling.
  epochFrontierModels,
  epochLargestCluster,
  aaIntelligenceIndex,

  // Usage & prices — what compute and tokens cost today.
  gpuSpotPrice,
  openrouterLongCtxPrice,

  // Ecosystem — adoption downstream of the labs.
  npmAiSdkDownloads,

  // Events.
  aiIncidents,
  labAnnouncements,
];
