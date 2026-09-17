// Threshold → status level. Levels are the fixed status palette
// (good / warning / serious / critical) plus 'unknown' when no thresholds.

import { parseCadence } from './registry.js';

export const LEVELS = ['good', 'warning', 'serious', 'critical'];

const HOUR_MS = 3_600_000;

export function evaluateStatus(inst, snap) {
  const t = inst.thresholds;
  if (!t) return 'unknown';
  if (typeof t === 'function') return t(snap.value, snap) || 'good';
  if (snap.value == null) return 'unknown';
  for (const rule of t) {
    if (matches(rule, snap.value)) return rule.level;
  }
  return 'good';
}

function matches(rule, v) {
  if (rule.gte != null && !(v >= rule.gte)) return false;
  if (rule.gt != null && !(v > rule.gt)) return false;
  if (rule.lte != null && !(v <= rule.lte)) return false;
  if (rule.lt != null && !(v < rule.lt)) return false;
  if (rule.eq != null && !(v === rule.eq)) return false;
  return true;
}

// Worst level across a set of snapshots (for section / page headline).
// 'unknown' (no thresholds / no data) is ignored unless nothing else is known,
// so a section of scaled + unscaled instruments still reads by its scaled ones.
export function worstLevel(levels) {
  let worst = -1;
  for (const l of levels) {
    const i = LEVELS.indexOf(l);
    if (i > worst) worst = i;
  }
  return worst < 0 ? 'unknown' : LEVELS[worst];
}

// The stale window for an instrument, computed EXACTLY as the frontend does
// (public/app.js ageEl): the explicit `staleAfter` if set, otherwise
// max(3×cadence, 2h). Data older than this is not a fresh reading.
export function staleWindowMs(inst) {
  return inst.staleAfter ? parseCadence(inst.staleAfter) : Math.max(parseCadence(inst.cadence) * 3, 2 * HOUR_MS);
}

// Is this snapshot STALE — its observation age (now − snap.at) past the stale
// window? (No `at` = never observed; handled elsewhere, not "stale" here.)
export function isStale(inst, snap, now = Date.now()) {
  // Match the frontend (app.js events card): events measure age from fetchedAt
  // (an events `at` tracks item time, legitimately old when nothing recent
  // happened), metrics from the observation time `at`. No timestamp = never
  // observed, not "stale" here (the lastError branch still catches a dead feed).
  const ref = snap && (inst.kind === 'events' ? snap.fetchedAt : snap.at);
  return !!(ref && now - Date.parse(ref) > staleWindowMs(inst));
}

// Effective status for the SECTION / PAGE rollup. Threshold status is honest for
// FRESH data, but a preserved snapshot can read 'good' while its feed is stale or
// its last fetch failed. So degrade the rollup status to at least 'warning' when
// the instrument is (a) STALE or (b) serving a preserved value after a failed
// fetch (`lastError` set). Fresh instruments — including 'unknown' (no
// thresholds) and never-fetched/skipped ones (no `at`, no `lastError`) — are
// returned unchanged, so existing rollup and card behavior is preserved.
// worstLevel([base, 'warning']) keeps an already-worse 'serious'/'critical' and
// lifts 'good'/'unknown' to 'warning'.
export function effectiveStatus(inst, snap, now = Date.now()) {
  const base = (snap && snap.status) || 'unknown';
  const degraded = isStale(inst, snap, now) || !!(snap && snap.lastError);
  return degraded ? worstLevel([base, 'warning']) : base;
}
