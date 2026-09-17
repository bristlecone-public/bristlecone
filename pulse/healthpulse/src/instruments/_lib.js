// Shared helpers for HealthPulse instruments. Not an instrument file — never
// registered in index.js (leading underscore, like _example.js).

const DAY = 86_400_000;

/**
 * MMWR ("epi") week → epoch ms of that week's *end* (Saturday, UTC midnight).
 *
 * MMWR weeks run Sunday–Saturday. Week 1 of a year is the first such week with
 * at least four days in the new year, which is equivalent to: the week whose
 * Wednesday is the first Wednesday of the year. Delphi/CDC both key weekly
 * respiratory data by epiweek (e.g. 202631 = week ending 2026-08-08).
 */
export function mmwrWeekEndMs(epiweek) {
  const ew = Number(epiweek);
  const year = Math.floor(ew / 100);
  const week = ew % 100;
  if (!Number.isFinite(year) || week < 1 || week > 53) return NaN;
  const jan1 = Date.UTC(year, 0, 1);
  const dow = new Date(jan1).getUTCDay(); // 0 = Sunday … 3 = Wednesday
  const firstWed = jan1 + ((3 - dow + 7) % 7) * DAY;
  const week1End = firstWed + 3 * DAY; // Saturday of week 1
  return week1End + (week - 1) * 7 * DAY;
}

/** Inclusive epiweek range string spanning the last `years` calendar years. */
export function epiweekRange(now, years) {
  const y = new Date(now).getUTCFullYear();
  return `${y - years}01-${y}53`;
}

/** Build a Socrata (data.cdc.gov) resource URL with SoQL params. */
export function socrata(dataset, params) {
  const qs = Object.entries(params)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&');
  return `https://data.cdc.gov/resource/${dataset}.json?${qs}`;
}

/** Canonical, always-resolving landing page for a Socrata dataset. */
export const socrataPage = (dataset) => `https://data.cdc.gov/d/${dataset}`;

/** YYYY-MM-DD, `days` before `now` — for SoQL `$where` date comparisons. */
export const isoDaysAgo = (now, days) => new Date(now - days * DAY).toISOString().slice(0, 10);

/**
 * Socrata dates arrive either as a bare date ("2026-08-08") or as a *floating*
 * timestamp with no zone ("2026-08-08T00:00:00.000"). Both mean "this calendar
 * day"; pin them to UTC midnight so the sparkline spacing is exact.
 */
export function socrataDateMs(v) {
  if (!v) return NaN;
  const s = String(v).slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? Date.parse(`${s}T00:00:00Z`) : NaN;
}

/** openFDA dates are packed YYYYMMDD strings. */
export function fdaDateMs(v) {
  const s = String(v || '').trim();
  return /^\d{8}$/.test(s) ? Date.parse(`${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}T00:00:00Z`) : NaN;
}

/** Turn [{t, v}] into the framework's [[epochMs, value]] series shape. */
export const toSeries = (pts) => pts.map((p) => [p.t, p.v]);
