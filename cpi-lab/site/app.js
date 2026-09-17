/* app.js — reads the eleven pipeline JSONs from /data/ and renders every panel.
 *
 * Tolerance rules (the pipelines are still moving):
 *   - P1 discovers its schemes from whatever `*_yoy` keys exist in series[0];
 *     labels come from the JSON's own `labels` map when present.
 *   - Any missing block renders a visible stub rather than throwing.
 *   - Nulls break lines; nothing is interpolated (2025-10 has no CPI).
 */
'use strict';

const DATA = '/data/';
const FILES = {
  p1: 'p1_salience.json',
  p2: 'p2_distribution.json',
  p3: 'p3_persistence.json',
  p4: 'p4_vintages.json',
  p5: 'p5_quality.json',
  p6: 'p6_pipeline.json',
  p7: 'p7_tariff.json',
  p8: 'p8_chained.json',
  p9: 'p9_metro.json',
  p10: 'p10_network.json',
  r1: 'r1_expectations.json'
};
const ORDER = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8', 'p9', 'p10', 'r1'];

/* Bare `NaN` / `Infinity` are not JSON. A pipeline that emits one makes the
 * whole file unparseable and takes its entire section off the page, so the
 * loader repairs them to null and counts them — the count is surfaced in the
 * provenance table rather than swallowed. */
let REPAIRED = {};
function parseTolerant(text, name) {
  try {
    return JSON.parse(text);
  } catch (e) {
    let n = 0;
    const fixed = text.replace(/([:,[]\s*)(NaN|-?Infinity)(?=\s*[,}\]])/g, (m, p) => { n++; return p + 'null'; });
    const out = JSON.parse(fixed);          /* still throws if it was something else */
    if (n) REPAIRED[name] = n;
    return out;
  }
}

/* Colour follows the entity, never its rank or row order. */
const SCHEME_COLOR = {
  published:        'var(--series-1)',
  official_replica: 'var(--series-2)',
  salience:         'var(--series-3)',
  bill_salience:    'var(--series-4)',
  blend50:          'var(--series-5)',
  bill_blend50:     'var(--series-7)'
};
const SPARE_COLORS = ['var(--series-5)', 'var(--series-7)'];
const SCHEME_ORDER = ['published', 'official_replica', 'salience', 'bill_salience', 'blend50', 'bill_blend50'];
const DEFAULT_ON = ['published', 'official_replica', 'salience', 'bill_salience'];
const FALLBACK_LABEL = {
  published: 'Published CPI-U (NSA, all items)',
  official_replica: 'Official (expenditure-weighted) replica',
  salience: 'Frequency-weighted CPI',
  blend50: '50/50 expenditure + frequency',
  bill_salience: 'Bill-adjusted frequency-weighted CPI',
  bill_blend50: '50/50 expenditure + bill-adjusted frequency'
};

const $ = id => document.getElementById(id);
function stub(host, msg) {
  if (!host) return;
  host.appendChild(H('div', { class: 'stub', text: msg }));
}
function pretty(k) { return k.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()); }

/* ---------------- theme toggle ---------------- */
(function theme() {
  const btn = $('themeToggle');
  const saved = (() => { try { return localStorage.getItem('cpilab-theme'); } catch (e) { return null; } })();
  if (saved) document.documentElement.setAttribute('data-theme', saved);
  btn.addEventListener('click', () => {
    const cur = document.documentElement.getAttribute('data-theme');
    const sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const next = cur ? (cur === 'dark' ? 'light' : 'dark') : (sysDark ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('cpilab-theme', next); } catch (e) {}
  });
})();

/* ---------------- boot ---------------- */
(async function boot() {
  const D = {};
  const failed = [];
  await Promise.all(Object.keys(FILES).map(async k => {
    try {
      const r = await fetch(DATA + FILES[k], { cache: 'no-cache' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      D[k] = parseTolerant(await r.text(), FILES[k]);
    } catch (e) {
      failed.push(FILES[k] + ' (' + e.message + ')');
      D[k] = null;
    }
  }));

  if (failed.length) {
    $('loaderr').appendChild(H('div', { class: 'err' },
      [H('strong', { text: 'Could not load: ' }), H('span', { text: failed.join(', ') }),
       H('div', { text: 'Panels reading those files are stubbed below. The server aliases /data/ to the pipeline output directory.' })]));
  }

  renderUpdated(D);
  const schemes = D.p1 ? discoverSchemes(D.p1) : [];
  renderTiles(D, schemes);
  renderP1(D.p1, schemes);
  renderP2(D.p2);
  renderP3(D.p3);
  renderP4(D.p4);
  renderP8(D.p8);
  renderP10(D.p10);
  renderP6(D.p6);
  renderP7(D.p7);
  renderP9(D.p9);
  renderP5(D.p5);
  renderMeta(D);
  redrawAll();
})();

/* =======================================================================
 * Shared: last-updated line
 * ===================================================================== */
function renderUpdated(D) {
  const parts = [];
  const p1m = D.p1 && D.p1.latest_month, p2m = D.p2 && D.p2.latest_month;
  const m = p1m || p2m;
  if (m) parts.push('Data through ' + ymLabel(m));
  const stamps = [];
  for (const k of ORDER) {
    const d = D[k];
    if (!d) continue;
    const g = d.generated_at || d.generated || (d.meta && d.meta.generated_at);
    if (g) stamps.push(new Date(g));
  }
  if (stamps.length) {
    const newest = new Date(Math.max.apply(null, stamps));
    parts.push('pipelines last run ' + newest.toISOString().replace('T', ' ').slice(0, 16) + ' UTC');
  }
  $('updated').textContent = parts.join(' · ') || 'No data loaded.';
}

/* =======================================================================
 * P1 scheme discovery — tolerant of schemes added after this was written
 * ===================================================================== */
function discoverSchemes(p1) {
  const s0 = (p1.series && p1.series[0]) || {};
  const keys = Object.keys(s0).filter(k => /_yoy$/.test(k)).map(k => k.replace(/_yoy$/, ''));
  keys.sort((a, b) => {
    const ia = SCHEME_ORDER.indexOf(a), ib = SCHEME_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  let spare = 0;
  return keys.map(k => ({
    key: k,
    label: (p1.labels && p1.labels[k]) || FALLBACK_LABEL[k] || pretty(k),
    color: SCHEME_COLOR[k] || SPARE_COLORS[spare++] || 'var(--series-1)',
    hasSe: (k + '_se') in s0,
    on: DEFAULT_ON.indexOf(k) >= 0 || (SCHEME_ORDER.indexOf(k) < 0 && keys.length <= 4)
  }));
}

/* =======================================================================
 * HEADLINE STRIP
 * ===================================================================== */
function tile(label, value, unit, month, spark, sparkColor, se) {
  const t = H('div', { class: 'tile' });
  t.appendChild(H('div', { class: 'label', text: label }));
  const v = H('div', { class: 'value' });
  v.appendChild(document.createTextNode(value));
  if (unit) v.appendChild(H('span', { class: 'unit', text: unit }));
  if (se) v.appendChild(H('span', { class: 'se', text: '±' + se }));
  t.appendChild(v);
  t.appendChild(H('div', { class: 'month', text: month }));
  const sh = H('div', { class: 'spark' });
  t.appendChild(sh);
  if (spark && spark.length) sparkline(sh, spark, { color: sparkColor, height: 30 });
  return t;
}

function renderTiles(D, schemes) {
  const host = $('tiles');
  const p1 = D.p1, p2 = D.p2, p5 = D.p5, p4 = D.p4, p9 = D.p9;
  const N = 36;   /* sparkline window */

  if (p1 && p1.series && p1.series.length) {
    const S1 = p1.series, tail = S1.slice(-N);
    const last = S1[S1.length - 1];
    const ml = ymLabel(last.ym);
    const want = ['published', 'salience', 'bill_salience'];
    for (const key of want) {
      const sc = schemes.find(s => s.key === key);
      if (!sc || last[key + '_yoy'] === undefined || last[key + '_yoy'] === null) continue;
      const se = sc.hasSe && last[key + '_se'] != null ? fmt(last[key + '_se'], 3) : null;
      host.appendChild(tile(
        key === 'published' ? 'Published CPI-U, all items (NSA)' : sc.label,
        fmt(last[key + '_yoy'], 2), '%', ml,
        tail.map(r => r[key + '_yoy'] == null ? null : r[key + '_yoy']), sc.color, se
      ));
    }
  } else {
    stub(host, 'P1 not available.');
  }

  if (p2 && p2.stats && p2.stats.all) {
    const A = p2.stats.all, n = A.ym.length;
    const li = lastIdx(A.yoy_median);
    const ml = ymLabel(A.ym[li]);
    const w = i0 => A.ym.slice(Math.max(0, n - N)).map((_, j) => i0[n - Math.min(n, N) + j]);
    host.appendChild(tile('Weighted median item, 12-month', fmt(A.yoy_median[li], 2), '%', ml, w(A.yoy_median), 'var(--series-1)'));
    host.appendChild(tile('16% trimmed mean, 12-month', fmt(A.yoy_trim16[li], 2), '%', ml, w(A.yoy_trim16), 'var(--series-2)'));
    host.appendChild(tile('Share of basket rising more than 4%', fmt(A.yoy_share_gt4[li], 1), '%', ml, w(A.yoy_share_gt4), 'var(--series-3)'));
  } else {
    stub(host, 'P2 not available.');
  }

  /* Spread across cities, next to the three spread-across-items tiles. Chosen
   * over P6's pipeline pressure for the ninth slot: "cities are 0.81 pp apart"
   * is legible on its own, whereas "−4.3 bp of pipeline pressure" needs three
   * sentences of not-a-forecast caveat before it means anything, and at that
   * size the pipeline's own documentation says it barely deserves a sentence.
   * The pressure figure is the lede stat of the P6 section instead. */
  if (p9 && p9.dispersion && p9.dispersion.length) {
    const DS = p9.dispersion.filter(d => d.sd != null);
    const dl = DS[DS.length - 1];
    if (dl) {
      host.appendChild(tile('Spread between cities (sd of metro 12-month rates)',
        fmt(dl.sd, 2), ' pp', ymLabel(dl.ym) + ' · ' + dl.n_metros + ' of 23 metros published',
        p9.dispersion.slice(-N).map(d => d.sd), 'var(--series-5)'));
    }
  } else if (p9) {
    stub(host, 'P9 dispersion not available.');
  }

  if (p5 && p5.latest && p5.latest.stress_composite) {
    const sc = p5.latest.stress_composite;
    const ser = (p5.series && p5.series.stress) || [];
    host.appendChild(tile('Instrument stress vs 2019 (indicator, not inflation)',
      fmtSigned(sc.composite_pp, 1), ' pp', ymLabel(sc.month),
      ser.slice(-N).map(r => r.composite_pp), 'var(--series-4)'));
  } else {
    stub(host, 'P5 not available.');
  }

  /* Revision durability. The share of printed 0.4s that moved reads far more
   * plainly than a p90 in hundredths of a point, so that is the tile; the p90
   * is in the P4 tables. No sparkline — it is a single pooled statistic over
   * the whole history, not a monthly series. */
  const h4 = p4 && p4.summary && p4.summary.headline_CPIAUCSL;
  if (h4 && h4.first_print_0_4) {
    const fp = h4.first_print_0_4;
    host.appendChild(tile('Headline monthly prints of 0.4% that did not stay 0.4%',
      fmt(fp.share_changed * 100, 0), '%', 'n = ' + fp.n + ', 1972–' + (p4.series[0] ? p4.series[0].last_obs_month.slice(0, 4) : ''), null, null, null));
  } else if (p4) {
    stub(host, 'P4 summary not available.');
  }

  $('tileNote').innerHTML = 'The frequency-weighted figures carry ±1 balanced-repeated-replication standard error. ' +
    'The city-spread tile is a cross-section of <strong>whichever metros published that month</strong> — 3 of the 23 ' +
    'publish monthly and the other 20 every other month, so adjacent points in its sparkline hold different cities. ' +
    'The instrument-stress number is <strong>not an inflation rate</strong> — it is percentage points above the 2019 ' +
    'collection baseline, and it says nothing about the direction of any error in the CPI. The last tile is a property ' +
    'of <strong>seasonal adjustment, not of the printed month</strong>: a first print of 0.4 is more likely to end up ' +
    'as 0.3 than to stay put, because the seasonal factors behind it are re-estimated for five more years.';
}
function lastIdx(a) { for (let i = a.length - 1; i >= 0; i--) if (a[i] !== null && isFinite(a[i])) return i; return 0; }

/* =======================================================================
 * P1
 * ===================================================================== */
function renderP1(p1, schemes) {
  if (!p1 || !p1.series || !p1.series.length) {
    stub($('p1Line'), 'p1_salience.json not available — panel stubbed.');
    stub($('p1Weights'), 'p1_salience.json not available — panel stubbed.');
    stub($('p1Gap'), 'p1_salience.json not available — panel stubbed.');
    return;
  }
  p1LineChart(p1, schemes);
  p1Sensitivity(p1);
  p1WeightsChart(p1);
  p1GapChart(p1);
}

function p1LineChart(p1, schemes) {
  const host = $('p1Line'), ctl = $('p1Controls');
  const rows = p1.series;
  const xs = rows.map(r => mkey(r.ym));
  const state = { view: 'level', on: {} };
  schemes.forEach(s => { state.on[s.key] = s.on; });

  /* View toggle — the SE band is sub-pixel against a 0–12% level axis but is
   * legible against the gap axis, so both views exist. Only offered when the
   * official replica is actually present to difference against. */
  const hasReplica = schemes.some(s => s.key === 'official_replica');
  if (hasReplica) {
    ctl.appendChild(H('span', { class: 'ctl-label', text: 'View:' }));
    const seg = H('div', { class: 'seg', role: 'group', 'aria-label': 'View' });
    [['level', 'Level (YoY %)'], ['gap', 'Gap vs official replica (pp)']].forEach(([v, lab], i) => {
      const b = H('button', { type: 'button', text: lab, 'aria-pressed': i === 0 ? 'true' : 'false' });
      b.addEventListener('click', () => {
        state.view = v;
        [...seg.children].forEach(c => c.setAttribute('aria-pressed', c === b ? 'true' : 'false'));
        paint();
      });
      seg.appendChild(b);
    });
    ctl.appendChild(seg);
  }

  ctl.appendChild(H('span', { class: 'ctl-label', text: 'Schemes:' }));
  schemes.forEach(s => {
    const id = 'sch-' + s.key;
    const cb = H('input', { type: 'checkbox', id: id });
    cb.checked = s.on;
    cb.addEventListener('change', () => { state.on[s.key] = cb.checked; paint(); });
    const l = H('label', { class: 'chk', for: id }, [cb,
      H('span', { class: 'sw sw-line', style: 'background:' + s.color }),
      H('span', { text: s.label })]);
    ctl.appendChild(l);
  });

  function paint() {
    clear(host);
    const gap = state.view === 'gap';
    const base = rows.map(r => r.official_replica_yoy);
    const sel = schemes.filter(s => state.on[s.key] && !(gap && s.key === 'official_replica'));
    if (!sel.length) { stub(host, 'Select at least one scheme.'); return; }

    const series = sel.map(s => ({
      key: s.key, label: s.label, color: s.color,
      values: rows.map((r, i) => {
        const v = r[s.key + '_yoy'];
        if (v == null || !isFinite(v)) return null;
        if (!gap) return v;
        const b = base[i];
        return (b == null || !isFinite(b)) ? null : v - b;
      })
    }));
    const bands = sel.filter(s => s.hasSe).map(s => ({
      key: s.key, label: s.label + ' ±1 SE', color: s.color, opacity: 0.24,
      lo: rows.map((r, i) => {
        const v = series.find(q => q.key === s.key).values[i];
        return (v == null || r[s.key + '_se'] == null) ? null : v - r[s.key + '_se'];
      }),
      hi: rows.map((r, i) => {
        const v = series.find(q => q.key === s.key).values[i];
        return (v == null || r[s.key + '_se'] == null) ? null : v + r[s.key + '_se'];
      })
    }));

    lineChart(host, {
      x: xs, series: series, bands: bands,
      yUnit: gap ? ' pp' : '%', yDp: gap ? 2 : 1, height: 340, zeroLine: gap,
      ariaLabel: gap ? 'Gap vs official replica by scheme' : 'Year-over-year inflation by weighting scheme'
    });

    clear($('p1LineTable'));
    const cols = ['Month'].concat(sel.map(s => s.label + (gap ? ' gap (pp)' : ' (%)')));
    const trows = rows.slice().reverse().map(r => [ymLabel(r.ym)].concat(sel.map(s => {
      const v = r[s.key + '_yoy'];
      if (v == null) return '—';
      const val = gap ? (r.official_replica_yoy == null ? null : v - r.official_replica_yoy) : v;
      if (val == null) return '—';
      const se = r[s.key + '_se'];
      return fmt(val, 3) + (se != null ? ' ±' + fmt(se, 3) : '');
    })));
    $('p1LineTable').appendChild(tableView(
      'Index year-over-year rates by weighting scheme, ' + ymLabel(rows[0].ym) + ' – ' + ymLabel(rows[rows.length - 1].ym) +
      '. October 2025 is absent — no CPI was released that month.', cols, trows));
  }
  paint();
}

function p1Sensitivity(p1) {
  const host = $('p1Sens');
  const sr = p1.sensitivity_range, sl = p1.sensitivity_latest;
  const copy = $('sensCopy');
  if (!sl || !sl.length) { if (copy) copy.textContent = 'Sensitivity variants not present in this run.'; return; }

  if (copy && sr) {
    copy.innerHTML = 'Eight specification variants are rebuilt as separate indexes. <strong>The range of the gap vs ' +
      'the official replica across all 8 variants at ' + ymLabel(sr.ym) + ' is ' + fmt(sr.range_pp, 3) + '&nbsp;pp</strong> ' +
      '(' + fmtSigned(sr.min_gap, 3) + ' to ' + fmtSigned(sr.max_gap, 3) + '). Reading that: the <em>specification</em> ' +
      'choices — how to split a UCC that maps to several items, at what level of the item tree to measure frequency — ' +
      'barely matter. <strong>Which CE Diary year you use matters far more</strong>, because the frequency profile itself ' +
      'shifted after 2022. That is the honest uncertainty in this method, and it is roughly 15× the ±' +
      fmt(bootSe(p1), 3) + '&nbsp;pp sampling error.';
  }

  const sorted = sl.slice().sort((a, b) => b.gap - a.gap);
  host.appendChild(H('h4', { style: 'font-size:13px;margin:16px 0 6px;color:var(--text-secondary);font-weight:600',
    text: 'Specification sensitivity — gap vs official replica, ' + (sr ? ymLabel(sr.ym) : 'latest month') }));
  const box = H('div');
  host.appendChild(box);
  barChart(box, {
    rows: sorted.map(v => ({ label: v.variant, title: v.variant + ' — YoY ' + fmt(v.yoy, 3) + '%', values: [v.gap] })),
    series: [{ label: 'Gap vs official replica (pp)', color: 'var(--div-pos)' }],
    diverging: true, unit: ' pp', dp: 3, tickDp: 2, ariaLabel: 'Sensitivity variants'
  });
  host.appendChild(tableView('Sensitivity variants at ' + (sr ? ymLabel(sr.ym) : 'the latest month'),
    ['Variant', 'YoY (%)', 'Gap vs replica (pp)'],
    sorted.map(v => [v.variant, fmt(v.yoy, 3), fmtSigned(v.gap, 3)])));
}
function bootSe(p1) {
  const last = p1.series[p1.series.length - 1];
  return last && last.salience_se != null ? last.salience_se : 0.019;
}

function p1WeightsChart(p1) {
  const host = $('p1Weights');
  const items = p1.items_latest;
  if (!items || !items.length) { stub(host, 'items_latest not present — panel stubbed.'); return; }
  const hasBill = items.some(i => i.w_bill != null);
  const top = items.slice().sort((a, b) =>
    Math.max(b.w_exp || 0, b.w_sal || 0) - Math.max(a.w_exp || 0, a.w_sal || 0)).slice(0, 25);

  const series = [{ label: 'Expenditure weight (official)', color: 'var(--series-2)' },
                  { label: 'Frequency weight', color: 'var(--series-3)' }];
  if (hasBill) series.push({ label: 'Bill-adjusted frequency weight', color: 'var(--series-4)' });

  barChart(host, {
    rows: top.map(i => ({
      label: i.name.length > 34 ? i.name.slice(0, 33) + '…' : i.name,
      title: i.name + ' (' + i.item_code + ')',
      values: hasBill ? [i.w_exp, i.w_sal, i.w_bill] : [i.w_exp, i.w_sal]
    })),
    series: series, unit: '%', dp: 2, tickDp: 0, barMax: 8,
    ariaLabel: 'Expenditure vs frequency weight, top 25 items'
  });
  $('p1WeightsTable').appendChild(tableView(
    'Basket share by weighting scheme, ' + ymLabel(p1.latest_month) + ' (percent of the basket)',
    ['Item', 'Code', 'Expenditure %', 'Frequency %'].concat(hasBill ? ['Bill-adjusted %'] : []).concat(['Item YoY %']),
    top.map(i => [i.name, i.item_code, fmt(i.w_exp, 3), fmt(i.w_sal, 3)]
      .concat(hasBill ? [fmt(i.w_bill, 3)] : []).concat([fmt(i.yoy, 2)]))));
}

function p1GapChart(p1) {
  const host = $('p1Gap');
  const items = (p1.items_latest || []).filter(i => i.gap_driver != null && isFinite(i.gap_driver));
  if (!items.length) { stub(host, 'gap_driver not present — panel stubbed.'); return; }
  const sorted = items.slice().sort((a, b) => b.gap_driver - a.gap_driver);
  const pick = sorted.slice(0, 12).concat(sorted.slice(-12)).sort((a, b) => b.gap_driver - a.gap_driver);
  barChart(host, {
    rows: pick.map(i => ({
      label: i.name.length > 34 ? i.name.slice(0, 33) + '…' : i.name,
      title: i.name + ' — YoY ' + fmt(i.yoy, 2) + '%, expenditure weight ' + fmt(i.w_exp, 2) + '%, frequency weight ' + fmt(i.w_sal, 2) + '%',
      values: [i.gap_driver]
    })),
    series: [{ label: 'contrib_sal − contrib_exp (pp)', color: 'var(--div-pos)' }],
    diverging: true, unit: ' pp', dp: 3, tickDp: 2, barMax: 12,
    ariaLabel: 'Gap drivers, latest month'
  });
  $('p1GapTable').appendChild(tableView(
    'Contribution gap by item, ' + ymLabel(p1.latest_month) + ' — all items with a value, largest first',
    ['Item', 'Code', 'YoY %', 'Exp weight %', 'Freq weight %', 'Exp contrib pp', 'Freq contrib pp', 'Gap pp'],
    sorted.map(i => [i.name, i.item_code, fmt(i.yoy, 2), fmt(i.w_exp, 3), fmt(i.w_sal, 3),
      fmt(i.contrib_exp, 4), fmt(i.contrib_sal, 4), fmtSigned(i.gap_driver, 4)])));
}

/* =======================================================================
 * P2
 * ===================================================================== */
function renderP2(p2) {
  if (!p2) {
    ['p2Ridge', 'p2Stats', 'p2Var', 'p2Level'].forEach(id => stub($(id), 'p2_distribution.json not available — panel stubbed.'));
    return;
  }
  p2RangeCopy(p2);
  p2Ridge(p2);
  p2Stats(p2);
  p2Var(p2);
}

function p2RangeCopy(p2) {
  const r = (p2.ridgeline || [])[p2.ridgeline.length - 1];
  const el = $('p2Range');
  if (!r || !el) return;
  let lo = Infinity, hi = -Infinity, loi = 0, hii = 0;
  r.yoy.forEach((v, i) => { if (v < lo) { lo = v; loi = i; } if (v > hi) { hi = v; hii = i; } });
  el.textContent = fmt(lo, 1) + '% to +' + fmt(hi, 1) + '%';
}

function p2Ridge(p2) {
  const host = $('p2Ridge');
  const rl = p2.ridgeline || [];
  if (!rl.length) { stub(host, 'ridgeline not present — panel stubbed.'); return; }
  const last24 = rl.slice(-24).reverse();          /* newest at top */
  const A = p2.stats.all;
  const at = {};
  A.ym.forEach((y, i) => { at[y] = i; });
  const months = last24.map(m => {
    const i = at[m.ym];
    return {
      ym: m.ym, yoy: m.yoy, w: m.w,
      stats: i === undefined ? {} : {
        median: A.yoy_median[i], p10: A.yoy_p10[i], p90: A.yoy_p90[i], lt0: A.yoy_share_lt0[i]
      }
    };
  });
  ridgeline(host, months, { ariaLabel: 'Weight-scaled distribution of item 12-month rates, last 24 months' });

  const cols = ['Month', 'Items', 'p10 %', 'Median %', 'p90 %', 'Share falling %', 'Share > 4% '];
  const rowsT = last24.map(m => {
    const i = at[m.ym];
    return [ymLabel(m.ym), String(m.yoy.length),
      i === undefined ? '—' : fmt(A.yoy_p10[i], 2),
      i === undefined ? '—' : fmt(A.yoy_median[i], 2),
      i === undefined ? '—' : fmt(A.yoy_p90[i], 2),
      i === undefined ? '—' : fmt(A.yoy_share_lt0[i], 1),
      i === undefined ? '—' : fmt(A.yoy_share_gt4[i], 1)];
  });
  host.appendChild(tableView('Cross-section summary, last 24 months (all items, weighted)', cols, rowsT));
}

function p2Stats(p2) {
  const host = $('p2Stats');
  const state = { u: 'all' };
  const seg = $('p2Controls').querySelector('.seg');
  [...seg.children].forEach(b => b.addEventListener('click', () => {
    state.u = b.dataset.u;
    [...seg.children].forEach(c => c.setAttribute('aria-pressed', c === b ? 'true' : 'false'));
    paint();
  }));

  function paint() {
    clear(host); clear($('p2StatsTable'));
    const A = p2.stats[state.u];
    if (!A) { stub(host, 'universe not present'); return; }
    const from = Math.max(0, A.ym.indexOf('2015-01'));
    const ym = A.ym.slice(from);
    const xs = ym.map(mkey);
    const cut = a => a.slice(from).map(v => (v === null || !isFinite(v)) ? null : v);

    lineChart(host, {
      x: xs,
      bands: [{ key: 'spread', label: '10th–90th percentile of items', color: 'var(--series-1)', opacity: 0.14,
                lo: cut(A.yoy_p10), hi: cut(A.yoy_p90) }],
      series: [
        { key: 'median', label: 'Weighted median item', color: 'var(--series-1)', values: cut(A.yoy_median) },
        { key: 'trim16', label: '16% trimmed mean', color: 'var(--series-2)', values: cut(A.yoy_trim16) }
      ],
      yUnit: '%', yDp: 1, height: 320, zeroLine: true,
      ariaLabel: 'Median, trimmed mean and percentile spread of item 12-month rates'
    });

    const cols = ['Month', 'p10 %', 'Median %', '16% trim %', 'p90 %', 'Weighted mean %', 'Share < 0 %', 'Share > 4 %'];
    const rowsT = [];
    for (let i = A.ym.length - 1; i >= from; i--) {
      rowsT.push([ymLabel(A.ym[i]), fmt(A.yoy_p10[i], 2), fmt(A.yoy_median[i], 2), fmt(A.yoy_trim16[i], 2),
        fmt(A.yoy_p90[i], 2), fmt(A.yoy_wmean[i], 2), fmt(A.yoy_share_lt0[i], 1), fmt(A.yoy_share_gt4[i], 1)]);
    }
    $('p2StatsTable').appendChild(tableView(
      'Weighted cross-section statistics, 12-month rates, ' + (state.u === 'all' ? 'all items' : 'ex-shelter') +
      ', from January 2015', cols, rowsT));
  }
  paint();
}

function p2Var(p2) {
  const vs = p2.varshare;
  if (!vs || !vs['24']) { stub($('p2Var'), 'varshare not present — panel stubbed.'); return; }
  const l24 = vs['24'], l60 = vs['60'] || [];
  const by60 = {}; l60.forEach(r => { by60[r.item_code] = r.share; });
  const top = l24.slice(0, 12);

  barChart($('p2Var'), {
    rows: top.map(r => ({
      label: r.item_name.length > 28 ? r.item_name.slice(0, 27) + '…' : r.item_name,
      title: r.item_name + ' (' + r.item_code + ')',
      values: [r.share * 100, by60[r.item_code] == null ? null : by60[r.item_code] * 100]
    })),
    series: [{ label: 'Last 24 months', color: 'var(--series-1)' }, { label: 'Last 60 months', color: 'var(--series-2)' }],
    unit: '%', dp: 1, tickDp: 0, barMax: 9, ariaLabel: 'Share of headline variance by item'
  });

  barChart($('p2Level'), {
    rows: top.map(r => ({
      label: r.item_name.length > 28 ? r.item_name.slice(0, 27) + '…' : r.item_name,
      title: r.item_name + ' (' + r.item_code + ')',
      values: [r.level_contrib]
    })),
    series: [{ label: 'Contribution to level (pp)', color: 'var(--div-pos)' }],
    diverging: true, unit: ' pp', dp: 3, tickDp: 2, barMax: 12,
    ariaLabel: 'Contribution to the level of headline'
  });

  $('p2VarTable').appendChild(tableView(
    'Share of headline SA month-on-month variance, windows ending ' + ymLabel(vs.month),
    ['Item', 'Code', '24-month share %', '60-month share %', 'Level contribution pp'],
    l24.map(r => [r.item_name, r.item_code, fmt(r.share * 100, 2),
      by60[r.item_code] == null ? '—' : fmt(by60[r.item_code] * 100, 2), fmtSigned(r.level_contrib, 4)])));

  const g = l24[0];
  if (g) {
    $('p2VarNote').innerHTML = '<strong>' + g.item_name + ' alone accounts for ' + fmt(g.share * 100, 0) +
      '% of the month-to-month variance</strong> of headline seasonally adjusted inflation over the 24 months to ' +
      ymLabel(vs.month) + ', while its contribution to the <em>level</em> of the latest month is ' +
      fmtSigned(g.level_contrib, 3) + '&nbsp;pp. That is the single most useful fact here: the item that determines ' +
      'the <em>level</em> of inflation is almost never the item that determines the monthly headline surprise.';
  }
}

/* =======================================================================
 * P5
 * ===================================================================== */
function renderP5(p5) {
  if (!p5) {
    ['p5Lines', 'p5Stress', 'p5Se', 'p5Events'].forEach(id => stub($(id), 'p5_quality.json not available — panel stubbed.'));
    return;
  }
  const bad = (p5.sources || []).filter(s => !s.parsed);
  if (bad.length) {
    const w = $('p5Warn');
    w.style.display = '';
    w.innerHTML = '<strong>Some P5 sources did not parse on the last run:</strong> ' +
      bad.map(s => s.name).join(', ') + '. The affected series stop at their last good month.';
  }
  p5Defs(p5);
  p5Lines(p5);
  p5Stress(p5);
  p5Se(p5);
  p5Events(p5);
}

function p5Defs(p5) {
  const dl = $('p5Defs');
  const want = ['imputation_source_distribution', 'cs_imputed_share', 'cs_quote_collection_rate',
    'cs_outlet_collection_rate', 'housing_imputed_share', 'cs_quote_estimation_rate'];
  const defs = p5.definitions || {};
  for (const k of want) {
    const d = defs[k];
    if (!d) continue;
    dl.appendChild(H('dt', { text: d.label || pretty(k) }));
    const dd = H('dd');
    dd.appendChild(H('span', { text: d.definition }));
    if (d.not) {
      const w = H('div', { class: 'warn' });
      w.appendChild(H('strong', { text: 'Does not mean: ' }));
      w.appendChild(document.createTextNode(d.not));
      dd.appendChild(w);
    }
    if (d.source) dd.appendChild(H('div', null, [H('a', { href: d.source, rel: 'noopener', text: d.source })]));
    dl.appendChild(dd);
  }
  const sd = (p5.definitions || {}).stress_composite;
  if (sd && $('p5StressDef')) {
    $('p5StressDef').innerHTML = '<strong>' + sd.label + '.</strong> ' + sd.definition +
      ' <em>Baseline ' + (p5.baseline || '2019-01..2019-12') + '.</em>';
  }
}

/* four monthly components, level or pp-vs-2019 */
function p5Lines(p5) {
  const host = $('p5Lines');
  const R = (p5.series && p5.series.response) || {};
  const impCs = (p5.series && p5.series.imputation_cs) || [];
  const impHo = (p5.series && p5.series.imputation_housing) || [];
  const bs = p5.stress_baseline_stats || {};

  /* build a month-keyed frame */
  const months = [];
  const seen = {};
  const push = ym => { if (ym && !seen[ym]) { seen[ym] = 1; months.push(ym); } };
  impCs.forEach(r => push(r.month));
  (R.cs_imputed_share || []).forEach(r => push(r.month));
  months.sort();
  const idx = {}; months.forEach((m, i) => { idx[m] = i; });
  const blank = () => new Array(months.length).fill(null);

  const comp = [
    { key: 'cs_different_cell', label: 'C&S imputations using a different cell', color: 'var(--series-1)',
      vals: (() => { const a = blank(); impCs.forEach(r => { if (idx[r.month] != null) a[idx[r.month]] = r.different_cell; }); return a; })() },
    { key: 'cs_imputed_share', label: 'C&S targeted quotes not collected', color: 'var(--series-2)',
      vals: (() => { const a = blank(); (R.cs_imputed_share || []).forEach(r => { if (idx[r.month] != null) a[idx[r.month]] = r.value; }); return a; })() },
    { key: 'housing_imputed_share', label: 'Rent units with imputed rent', color: 'var(--series-3)',
      vals: (() => { const a = blank(); (R.housing_imputed_share || []).forEach(r => { if (idx[r.month] != null) a[idx[r.month]] = r.value; }); return a; })() },
    { key: 'housing_noninterview', label: 'Housing imputations that were non-interviews', color: 'var(--series-4)',
      vals: (() => { const a = blank(); impHo.forEach(r => { if (idx[r.month] != null) a[idx[r.month]] = r.non_interview; }); return a; })() }
  ];

  const state = { m: 'pp' };
  const seg = $('p5Controls').querySelector('.seg');
  [...seg.children].forEach(b => b.addEventListener('click', () => {
    state.m = b.dataset.m;
    [...seg.children].forEach(c => c.setAttribute('aria-pressed', c === b ? 'true' : 'false'));
    paint();
  }));

  function paint() {
    clear(host); clear($('p5LinesTable'));
    const pp = state.m === 'pp';
    lineChart(host, {
      x: months.map(mkey),
      series: comp.map(c => ({
        key: c.key, label: c.label, color: c.color,
        values: c.vals.map(v => v == null ? null : (pp ? v - ((bs[c.key] || {}).mean_2019 || 0) : v))
      })),
      yUnit: pp ? ' pp' : '%', yDp: pp ? 1 : 0, height: 320, zeroLine: pp,
      ariaLabel: 'CPI collection statistics vs the 2019 baseline'
    });
    if (pp) host.appendChild(H('p', { class: 'note', text: 'Zero is each series’ own January–December 2019 mean, so the four are directly comparable in percentage points. Switch to "Published level" to read the raw BLS percentages.' }));

    const cols = ['Month'].concat(comp.map(c => c.label + (pp ? ' (pp vs 2019)' : ' (%)')));
    const rowsT = [];
    for (let i = months.length - 1; i >= 0; i--) {
      rowsT.push([ymLabel(months[i])].concat(comp.map(c => {
        const v = c.vals[i];
        return v == null ? '—' : (pp ? fmtSigned(v - ((bs[c.key] || {}).mean_2019 || 0), 2) : fmt(v, 1));
      })));
    }
    $('p5LinesTable').appendChild(tableView('Monthly CPI collection statistics. 2019 means: ' +
      comp.map(c => c.label + ' ' + fmt((bs[c.key] || {}).mean_2019, 2) + '%').join('; ') + '.', cols, rowsT));
  }
  paint();
}

function p5Stress(p5) {
  const host = $('p5Stress');
  const ser = (p5.series && p5.series.stress) || [];
  if (!ser.length) { stub(host, 'stress series not present — panel stubbed.'); return; }
  const CATLAB = { collection: 'Collection', shutdown: 'Shutdown', covid: 'COVID', data_quality: 'Data quality', methodology: 'Methodology' };
  const ann = (p5.events || []).filter(e => e.impact === 1).map(e => ({
    x: mkey(e.date.slice(0, 7)),
    label: (CATLAB[e.category] || pretty(e.category)) + ' · ' + e.date,
    title: e.title
  }));

  lineChart(host, {
    x: ser.map(r => mkey(r.month)),
    series: [{ key: 'c', label: 'Instrument stress (pp above 2019)', color: 'var(--series-1)', values: ser.map(r => r.composite_pp) }],
    yUnit: ' pp', yDp: 1, height: 300, zeroLine: true, annotations: ann,
    ariaLabel: 'Instrument stress composite, percentage points above the 2019 baseline'
  });

  $('p5StressTable').appendChild(tableView(
    'Instrument stress composite by month. composite_pp is the domain-balanced average in percentage points above 2019 — the number to quote. The z column is shown for completeness and is not a probability sigma.',
    ['Month', 'Composite (pp above 2019)', 'Composite (z)'],
    ser.slice().reverse().map(r => [ymLabel(r.month), fmtSigned(r.composite_pp, 2), fmt(r.composite, 1)])));
}

function p5Se(p5) {
  const host = $('p5Se');
  const se = p5.se;
  if (!se || !se.items) { stub(host, 'variance estimates not present — panel stubbed.'); return; }
  const want = ['all items', 'all items less food and energy', 'housing', 'energy', 'food and beverages', 'medical care', 'transportation'];
  const rows = se.items.filter(i => i.horizon === '12 Month' && want.indexOf(i.item) >= 0)
    .sort((a, b) => want.indexOf(a.item) - want.indexOf(b.item));
  if (!rows.length) { stub(host, 'no 12-month variance rows — panel stubbed.'); return; }
  const years = Object.keys(rows[0].by_year).sort();

  const t = H('table');
  t.appendChild(H('caption', { text: 'Median standard error of the published 12-month price change, U.S. city average, by year (percentage points). Sampling error only.' }));
  t.appendChild(H('thead', null, [H('tr', null,
    [H('th', { text: 'Item', scope: 'col' })].concat(years.map(y => H('th', { text: y, scope: 'col' })))
      .concat([H('th', { text: 'vs ' + (se.baseline_year || 2019), scope: 'col' })]))]));
  const tb = H('tbody');
  for (const r of rows) {
    tb.appendChild(H('tr', null, [H('th', { text: r.item, scope: 'row' })]
      .concat(years.map(y => H('td', { text: r.by_year[y] == null ? '—' : fmt(r.by_year[y], 2) })))
      .concat([H('td', { text: r.ratio_vs_2019 == null ? '—' : fmt(r.ratio_vs_2019, 2) + '×' })])));
  }
  t.appendChild(tb);
  host.appendChild(H('div', { class: 'tablewrap' }, [t]));
}

function p5Events(p5) {
  const host = $('p5Events');
  const ev = (p5.events || []).filter(e => e.impact === 1);
  if (!ev.length) { stub(host, 'no flagged notices.'); return; }
  const CATLAB = { collection: 'Collection', shutdown: 'Shutdown', covid: 'COVID', data_quality: 'Data quality', methodology: 'Methodology' };
  const t = H('table');
  t.appendChild(H('caption', { text: ev.length + ' of ' + (p5.events || []).length + ' scraped notices are flagged as collection, shutdown, COVID or data-quality events.' }));
  t.appendChild(H('thead', null, [H('tr', null,
    ['Date', 'Category', 'Notice'].map(c => H('th', { text: c, scope: 'col' })))]));
  const tb = H('tbody');
  for (const e of ev) {
    tb.appendChild(H('tr', null, [
      H('th', { text: e.date, scope: 'row' }),
      H('td', { text: CATLAB[e.category] || pretty(e.category) }),
      H('td', { style: 'white-space:normal' }, [H('a', { href: e.url, rel: 'noopener', text: e.title })])
    ]));
  }
  t.appendChild(tb);
  host.appendChild(H('div', { class: 'tablewrap' }, [t]));
}

/* =======================================================================
 * Shared controls
 * ===================================================================== */

/* a native select, for a picker with more options than a segmented control
 * can carry without wrapping into an unreadable row */
function selectControl(host, labelText, options, initial, onChange) {
  const id = 'sel-' + Math.random().toString(36).slice(2, 8);
  host.appendChild(H('label', { class: 'ctl-label', for: id, text: labelText }));
  const s = H('select', { class: 'sel', id: id });
  for (const o of options) {
    const op = H('option', { value: o.value, text: o.label });
    if (o.value === initial) op.selected = true;
    s.appendChild(op);
  }
  s.addEventListener('change', () => onChange(s.value));
  host.appendChild(s);
  return s;
}

/* a segmented control bound to an existing .seg in the HTML */
function segControl(host, attr, onChange) {
  const seg = host && host.querySelector('.seg');
  if (!seg) return;
  [...seg.children].forEach(b => b.addEventListener('click', () => {
    [...seg.children].forEach(c => c.setAttribute('aria-pressed', c === b ? 'true' : 'false'));
    onChange(b.dataset[attr]);
  }));
}

/* =======================================================================
 * P3 — persistence
 * ===================================================================== */

/* Colour follows the entity: a construction, not its position in the list. */
const P3_COLOR = {
  official_replica: 'var(--series-2)',
  sticky: 'var(--series-3)',
  flexible: 'var(--series-4)',
  af_sticky: 'var(--series-5)',
  af_flexible: 'var(--series-7)'
};
/* half-life bins, months — shared by both source facets so the nsa12
 * artefact is visible as colour, not hidden by a rescale */
const HL_CUTS = [0.5, 1.5, 3, 6];
const HL_LABELS = ['0 – 0.5', '0.5 – 1.5', '1.5 – 3', '3 – 6', '6 +'];

function renderP3(p3) {
  if (!p3 || !p3.treemap) {
    ['p3Tree', 'p3Series', 'p3Buckets'].forEach(id => stub($(id), 'p3_persistence.json not available — panel stubbed.'));
    return;
  }
  const comp = (p3.summary && p3.summary.scheme_composition && p3.summary.scheme_composition.sticky_cpi) || [];
  if (comp.length && $('p3OerShare')) $('p3OerShare').textContent = fmt(comp[0].share_of_scheme_weight, 1);
  p3Treemap(p3);
  p3Series(p3);
  p3Buckets(p3);
}

function p3Treemap(p3) {
  const host = $('p3Tree'), tblHost = $('p3TreeTable');
  const sp = p3.summary && p3.summary.spearman_raw_vs_relative;
  if (sp && $('p3Spear')) {
    $('p3Spear').textContent = fmt(sp.rho, 3) + ' over ' + sp.n + ' items (' + fmt(sp.sa_only_rho, 3) +
      ' over the ' + sp.sa_only_n + ' seasonally adjusted ones)';
  }

  const state = { u: 'raw' };
  segControl($('p3Controls'), 'u', v => { state.u = v; paint(); });

  const shares = (p3.summary && p3.summary.source_shares) || {};
  const NULLNOTE = p3.summary && p3.summary.nsa12_null;

  const FACETS = [
    { src: 'sa', title: 'Seasonally adjusted items', height: 320, hatch: false,
      sub: '142 items · ' + fmt(shares.sa, 1) + '% of CPI-U · rate = published SA month-over-month change',
      note: null },
    { src: 'nsa12', title: 'NSA-derived items — a different measurement, never ranked against the block above', height: 190, hatch: true,
      sub: '32 items · ' + fmt(shares.nsa12, 1) + '% of CPI-U · rate = 12-month log change ÷ 12',
      note: 'The 12-month moving average in this rate manufactures persistence: applied to pure noise it produces ' +
            'rho ≈ ' + fmt(NULLNOTE ? NULLNOTE.analytic_rho : 0.917, 3) + ' and a half-life of about ' +
            fmt(NULLNOTE ? NULLNOTE.analytic_halflife : 7.97, 1) + ' months on its own (' +
            fmt(NULLNOTE ? NULLNOTE.halflife_mean : 6.31, 1) + ' months when re-derived by simulation on 120-month ' +
            'windows). Any item here at or below that is indistinguishable from white noise. Read the shape within ' +
            'this block; do not compare a colour here with a colour above.' }
  ];

  function paint() {
    clear(host); clear(tblHost);
    const rel = state.u === 'relative';
    const key = rel ? 'halflife_relative' : 'halflife_raw';
    const rkey = rel ? 'rho_relative' : 'rho_raw';

    $('p3UnivNote').innerHTML = rel
      ? '<strong>Relative universe:</strong> each item’s rate minus the headline rate put through the same filter, ' +
        'so a slowly-fading common shock is differenced out. Half-lives collapse — owners’ equivalent rent falls ' +
        'from 4.4 months to 1.0 — but the <em>ordering</em> barely moves. Beware the mechanical part: OER is a quarter ' +
        'of the headline, so subtracting the headline subtracts a quarter of OER from itself, and this universe is ' +
        'biased toward finding low persistence for high-weight items. For small items it is the clean measure.'
      : '<strong>Raw universe:</strong> the item’s own published rate. Univariate persistence is not own ' +
        'persistence — a slowly-fading shock hitting every item at once makes every item look sticky. Switch to ' +
        '"item minus headline" for the check; both are published and neither should be quoted alone.';

    host.appendChild(scaleLegend('Half-life (months), colour:',
      HL_LABELS.map((l, i) => ({ color: 'var(--seq-' + (i + 1) + ')', label: l })),
      [{ color: 'var(--null-cell)', label: 'no estimate' }]));

    for (const f of FACETS) {
      const items = p3.treemap.filter(t => t.source === f.src);
      const wsum = items.reduce((s, t) => s + t.weight, 0);
      const box = H('div', { class: 'facet' });
      const head = H('div', { class: 'facet-head' });
      head.appendChild(H('h4', { text: f.title }));
      head.appendChild(H('span', { class: 'facet-sub', text: f.sub }));
      box.appendChild(head);
      if (f.note) box.appendChild(H('p', { class: 'facet-note', text: f.note }));
      const plot = H('div');
      box.appendChild(plot);
      host.appendChild(box);

      treemap(plot, {
        height: f.height, hatch: f.hatch,
        ariaLabel: f.title + ' — area is basket weight, fill is half-life',
        items: items.map(t => ({
          label: t.item_name,
          sub: fmt(t[key], 1) + ' m · ' + fmt(t.weight, 2) + '%',
          value: t.weight,
          fill: seqColor(t[key], HL_CUTS),
          ink: (t[key] !== null && t[key] >= HL_CUTS[2]) ? 'var(--surface-1)' : 'var(--text-primary)',
          title: t.item_name + ' (' + t.item_code + ')',
          rows: [
            ['Basket weight', fmt(t.weight, 3) + '%'],
            ['Half-life', fmt(t[key], 2) + ' months'],
            ['rho', fmt(t[rkey], 3)],
            ['12-month rate', fmt(t.yoy, 2) + '%'],
            ['Share of this facet', fmt(100 * t.weight / wsum, 2) + '%']
          ]
        }))
      });
    }

    host.appendChild(H('p', { class: 'note', text:
      'Each facet fills its own box, so area is the item’s share of that facet, not of the whole basket — the ' +
      'facet headings carry the shares of CPI-U. Labels are drawn only where they fit without being clipped; every ' +
      'value is in the tooltip and in the data table.' }));

    const sorted = p3.treemap.slice().sort((a, b) =>
      (a.source < b.source ? -1 : a.source > b.source ? 1 : 0) || (b.weight - a.weight));
    tblHost.appendChild(tableView(
      'Item persistence at ' + ymLabel(p3.latest_month) + ', ' + (rel ? 'relative' : 'raw') + ' universe. ' +
      'Sorted within source group; sa and nsa12 rows are not comparable with each other.',
      ['Item', 'Code', 'Source', 'Weight %', 'Half-life (m)', 'rho', 'lp12', 'lp12 SE', 'Own-history pct', '12-month %'],
      sorted.map(t => [t.item_name, t.item_code, t.source, fmt(t.weight, 3), fmt(t[key], 2), fmt(t[rkey], 3),
        fmt(rel ? null : t.lp12_raw, 3), fmt(rel ? null : t.lp12_se_raw, 3),
        fmt(rel ? t.pctile_relative : t.pctile_raw, 0), fmt(t.yoy, 2)])));
  }
  paint();
}

function p3Series(p3) {
  const host = $('p3Series'), ctl = $('p3SeriesControls'), tbl = $('p3SeriesTable');
  const SER = p3.series || {};
  if (!SER.official_replica) { stub(host, 'series not present — panel stubbed.'); return; }

  const ym = SER.official_replica.ym;
  const xs = ym.map(mkey);
  const af = (p3.atlanta_fed && p3.atlanta_fed.series) || {};
  const afAt = k => {
    const s = af[k];
    if (!s) return null;
    const m = {}; s.ym.forEach((y, i) => { m[y] = s.v[i]; });
    return ym.map(y => (m[y] === undefined ? null : m[y]));
  };

  const state = { variant: 'continuous', on: { official_replica: true, sticky: true, flexible: true, af_sticky: true, af_flexible: true } };
  const SUFFIX = { continuous: '', binary: '_binary', pooled: '_pooled' };

  ctl.appendChild(H('span', { class: 'ctl-label', text: 'Weighting:' }));
  const seg = H('div', { class: 'seg', role: 'group', 'aria-label': 'Weighting' });
  [['continuous', 'Continuous rank tilt'], ['binary', 'Hard split at the median'], ['pooled', 'Pooled (artefact demo)']]
    .forEach(([v, lab], i) => {
      const b = H('button', { type: 'button', text: lab, 'aria-pressed': i === 0 ? 'true' : 'false' });
      b.addEventListener('click', () => {
        state.variant = v;
        [...seg.children].forEach(c => c.setAttribute('aria-pressed', c === b ? 'true' : 'false'));
        paint();
      });
      seg.appendChild(b);
    });
  ctl.appendChild(seg);

  const TOGGLES = [
    { key: 'official_replica', label: 'Official (expenditure-weighted) replica' },
    { key: 'sticky', label: 'Sticky CPI (ours)' },
    { key: 'flexible', label: 'Flexible CPI (ours)' },
    { key: 'af_sticky', label: 'Atlanta Fed sticky CPI' },
    { key: 'af_flexible', label: 'Atlanta Fed flexible CPI' }
  ];
  ctl.appendChild(H('span', { class: 'ctl-label', text: 'Series:' }));
  for (const t of TOGGLES) {
    const id = 'p3s-' + t.key;
    const cb = H('input', { type: 'checkbox', id: id });
    cb.checked = state.on[t.key];
    cb.addEventListener('change', () => { state.on[t.key] = cb.checked; paint(); });
    ctl.appendChild(H('label', { class: 'chk', for: id }, [cb,
      H('span', { class: 'sw sw-line', style: 'background:' + P3_COLOR[t.key] }),
      H('span', { text: t.label })]));
  }

  function paint() {
    clear(host); clear(tbl);
    const sfx = SUFFIX[state.variant];
    const ours = k => {
      const s = SER[k + '_cpi' + sfx];
      return s ? s.yoy.map(v => (v === null || !isFinite(v)) ? null : v) : null;
    };
    const avail = {
      official_replica: SER.official_replica.yoy,
      sticky: ours('sticky'),
      flexible: ours('flexible'),
      af_sticky: afAt('sticky_yoy'),
      af_flexible: afAt('flexible_yoy')
    };
    const LAB = {
      official_replica: 'Official (expenditure-weighted) replica',
      sticky: 'Sticky CPI — ' + state.variant + ' tilt',
      flexible: 'Flexible CPI — ' + state.variant + ' tilt',
      af_sticky: 'Atlanta Fed sticky CPI',
      af_flexible: 'Atlanta Fed flexible CPI'
    };
    const sel = TOGGLES.filter(t => state.on[t.key] && avail[t.key]);
    if (!sel.length) { stub(host, 'Select at least one series.'); return; }

    lineChart(host, {
      x: xs,
      series: sel.map(t => ({ key: t.key, label: LAB[t.key], color: P3_COLOR[t.key], values: avail[t.key] })),
      yUnit: '%', yDp: 1, height: 340, zeroLine: false,
      ariaLabel: 'Sticky and flexible CPI, 12-month rates'
    });

    const corr = (p3.atlanta_fed && p3.atlanta_fed.corr) || {};
    const last = i => { for (let k = i.length - 1; k >= 0; k--) if (i[k] != null && isFinite(i[k])) return i[k]; return null; };
    const st = last(avail.sticky), fl = last(avail.flexible);
    $('p3SeriesNote').innerHTML =
      (st != null && fl != null
        ? 'Latest month: sticky <strong>' + fmt(st, 2) + '%</strong>, flexible <strong>' + fmt(fl, 2) + '%</strong>, ' +
          'spread <strong>' + fmtSigned(st - fl, 2) + '&nbsp;pp</strong>. '
        : '') +
      'Over the ' + (corr.sticky ? corr.sticky.n : 0) + ' overlapping months the two sticky series correlate ' +
      fmt(corr.sticky ? corr.sticky.corr : null, 2) + ' (mean difference ' + fmtSigned(corr.sticky ? corr.sticky.mean_diff : null, 2) +
      '&nbsp;pp, MAE ' + fmt(corr.sticky ? corr.sticky.mae : null, 2) + '&nbsp;pp) and the two flexible series correlate ' +
      fmt(corr.flexible ? corr.flexible.corr : null, 2) + ' (mean difference ' + fmtSigned(corr.flexible ? corr.flexible.mean_diff : null, 2) +
      '&nbsp;pp, MAE ' + fmt(corr.flexible ? corr.flexible.mae : null, 2) + '&nbsp;pp). <strong>That is a sanity band, ' +
      'not a validation</strong> — see the method note on vehicles for why the two constructions disagree by design.';

    const cols = ['Month'].concat(sel.map(t => LAB[t.key] + ' (%)'));
    const rowsT = [];
    for (let i = ym.length - 1; i >= 0; i--) rowsT.push([ymLabel(ym[i])].concat(sel.map(t => fmt(avail[t.key][i], 2))));
    tbl.appendChild(tableView(
      '12-month rates, ' + ymLabel(ym[0]) + ' – ' + ymLabel(ym[ym.length - 1]) +
      '. October 2025 is absent — no CPI was released that month.', cols, rowsT));
  }
  paint();
}

function p3Buckets(p3) {
  const host = $('p3Buckets'), tbl = $('p3BucketsTable');
  const b = p3.summary && p3.summary.buckets;
  if (!b || !b.by_source) { stub(host, 'buckets not present — panel stubbed.'); return; }
  const sa = b.by_source.sa, ns = b.by_source.nsa12, all = b.all;

  barChart(host, {
    rows: [
      { label: 'Under 3 months', title: 'Half-life under 3 months', values: [sa.lt3, ns.lt3, all.lt3] },
      { label: '3 to 12 months', title: 'Half-life between 3 and 12 months', values: [sa['3to12'], ns['3to12'], all['3to12']] },
      { label: 'Over 12 months', title: 'Half-life above 12 months', values: [sa.gt12, ns.gt12, all.gt12] }
    ],
    series: [
      { label: 'Seasonally adjusted items (' + fmt(sa.covered_weight, 1) + '% of CPI-U)', color: 'var(--series-3)' },
      { label: 'NSA-derived items (' + fmt(ns.covered_weight, 1) + '%)', color: 'var(--series-4)' },
      { label: 'Pooled — shown to expose the artefact, not to quote', color: 'var(--series-2)' }
    ],
    unit: '% of that group’s weight', dp: 1, tickDp: 0, barMax: 14,
    ariaLabel: 'Share of weight by half-life bucket, by source group'
  });

  tbl.appendChild(tableView(
    'Share of covered leaf weight by half-life bucket, raw universe, ' + ymLabel(p3.latest_month) +
    '. Percentages are of each group’s own covered weight.',
    ['Bucket', 'Seasonally adjusted %', 'NSA-derived %', 'Pooled %'],
    [['Under 3 months', fmt(sa.lt3, 2), fmt(ns.lt3, 2), fmt(all.lt3, 2)],
     ['3 to 12 months', fmt(sa['3to12'], 2), fmt(ns['3to12'], 2), fmt(all['3to12'], 2)],
     ['Over 12 months', fmt(sa.gt12, 2), fmt(ns.gt12, 2), fmt(all.gt12, 2)],
     ['— of which capped at 60 months', fmt(sa.capped60, 2), fmt(ns.capped60, 2), fmt(all.capped60, 2)],
     ['Covered weight (% of CPI-U)', fmt(sa.covered_weight, 2), fmt(ns.covered_weight, 2), fmt(all.covered_weight, 2)],
     ['Items', String(sa.n_items), String(ns.n_items), String(all.n_items)]]));

  $('p3BucketNote').innerHTML =
    '<strong>' + fmt(sa.lt3, 1) + '% of the seasonally adjusted basket sits in items whose half-life is under three ' +
    'months</strong>, and <strong>no seasonally adjusted item has a half-life above twelve</strong>. Against that, ' +
    fmt(ns.gt12, 1) + '% of the NSA-derived weight lands in the "over 12 months" bucket — <strong>that gap is the ' +
    'filter, not a finding</strong>. The pooled column mixes the two and is printed only so the size of the artefact ' +
    'is visible; the by-source columns are the ones to read.';
}

/* =======================================================================
 * P4 — revisions
 * ===================================================================== */
function renderP4(p4) {
  if (!p4 || !p4.series) {
    ['p4Fan', 'p4Moy', 'p4Trans', 'p4Se'].forEach(id => stub($(id), 'p4_vintages.json not available — panel stubbed.'));
    return;
  }
  const opts = p4.series.map(s => ({ value: s.series_id, label: s.label }));
  const byId = {};
  p4.series.forEach(s => { byId[s.series_id] = s; });
  p4Fan(p4, opts, byId);
  p4Moy(p4, opts, byId);
  p4Trans(p4);
  p4Se(p4, opts, byId);
}

function p4Fan(p4, opts, byId) {
  const host = $('p4Fan'), tbl = $('p4FanTable');
  let cur = 'CPIAUCSL';
  selectControl($('p4FanControls'), 'Series:', opts, cur, v => { cur = v; paint(); });

  function paint() {
    clear(host); clear(tbl);
    const f = (p4.fan || {})[cur], s = byId[cur];
    if (!f) { stub(host, 'no vintage fan for this series.'); return; }
    const xs = f.obs_months.map(mkey);
    /* first print = the earliest vintage that carries each obs month */
    const first = f.obs_months.map((_, ci) => {
      for (let vi = 0; vi < f.mom.length; vi++) {
        const v = f.mom[vi][ci];
        if (v !== null && v !== undefined && isFinite(v)) return v;
      }
      return null;
    });
    fanChart(host, {
      x: xs, lines: f.mom, labels: f.vintages, firstPrint: first,
      yUnit: '%', yDp: 2, height: 330,
      ariaLabel: s.label + ' seasonally adjusted month-over-month change, every archived vintage'
    });

    const st = s.stats && (s.stats['2011+'] || s.stats.full);
    $('p4FanNote').innerHTML =
      '<strong>' + s.label + '</strong> — ' + s.n_vintages + ' archived vintages, ' + s.first_vintage + ' to ' +
      s.last_vintage + '; the fan shows the last ' + f.obs_months.length + ' observation months. Over the 2011-onward ' +
      'window the average size of the eventual revision is <strong>' + fmt(st.mean_abs_rev, 3) + '&nbsp;pp</strong>, ' +
      'the 90th percentile <strong>' + fmt(st.p90_abs, 3) + '&nbsp;pp</strong>, and <strong>' +
      fmt(st.share_abs_ge_0_1 * 100, 1) + '%</strong> of months move by a tenth or more (' +
      fmt(st.share_sign_flip * 100, 1) + '% change sign). Most of the movement happens fast — mean |revision| one year ' +
      'on is already ' + fmt(st.mean_abs_rev_1y, 3) + '&nbsp;pp — and seasonally adjusted history is frozen after ' +
      'about seven years.';

    const latest = f.mom[f.mom.length - 1];
    tbl.appendChild(tableView(
      s.label + ' — SA month-over-month change by observation month: as first printed, as it stands now, and the ' +
      'spread across every stored vintage.',
      ['Observation month', 'First print %', 'Latest %', 'Revision pp', 'Min across vintages', 'Max across vintages'],
      f.obs_months.map((m, ci) => {
        const vals = f.mom.map(l => l[ci]).filter(v => v !== null && v !== undefined && isFinite(v));
        return [ymLabel(m), fmt(first[ci], 3), fmt(latest[ci], 3),
          (first[ci] != null && latest[ci] != null) ? fmtSigned(latest[ci] - first[ci], 3) : '—',
          vals.length ? fmt(Math.min.apply(null, vals), 3) : '—',
          vals.length ? fmt(Math.max.apply(null, vals), 3) : '—'];
      }).reverse()));
  }
  paint();
}

function p4Moy(p4, opts, byId) {
  const host = $('p4Moy'), tbl = $('p4MoyTable');
  let cur = 'CPIAUCSL';
  selectControl($('p4MoyControls'), 'Series:', opts, cur, v => { cur = v; paint(); });
  const MON = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

  function paint() {
    clear(host); clear(tbl);
    const s = byId[cur];
    const rows = (s && s.by_month_of_year) || [];
    if (!rows.length) { stub(host, 'no month-of-year table for this series.'); return; }
    barChart(host, {
      rows: rows.map(r => ({
        label: MON[r.m - 1],
        title: MON[r.m - 1] + ' — ' + r.n + ' prints, mean |revision| ' + fmt(r.mean_abs_rev, 3) + ' pp',
        values: [r.mean_rev]
      })),
      series: [{ label: 'Mean signed revision, latest − first print (pp)', color: 'var(--div-pos)' }],
      diverging: true, unit: ' pp', dp: 3, tickDp: 2, barMax: 14,
      ariaLabel: 'Mean signed revision by calendar month'
    });
    const early = rows.slice(0, 5).reduce((a, r) => a + r.mean_rev, 0) / 5;
    const late = rows.slice(7).reduce((a, r) => a + r.mean_rev, 0) / 5;
    $('p4MoyNote').innerHTML =
      '<strong>' + s.label + '.</strong> January to May average <strong>' + fmtSigned(early, 3) + '&nbsp;pp</strong>; ' +
      'August to December average <strong>' + fmtSigned(late, 3) + '&nbsp;pp</strong>. Early-year prints are ' +
      'systematically revised <strong>down</strong> and late-year prints <strong>up</strong>, which is exactly what ' +
      're-estimated seasonal factors do — they redistribute a fixed annual total across twelve months, so the ' +
      'revisions roughly cancel over the year. Practical reading: <strong>a hot February or March print is more likely ' +
      'to be revised down later than a hot November print is.</strong> That is a property of the adjustment, not a ' +
      'claim about inflation.';
    tbl.appendChild(tableView(
      s.label + ' — revision from first print to latest value, by calendar month, pooled over the series’ whole history.',
      ['Calendar month', 'Prints', 'Mean signed revision pp', 'Mean |revision| pp', 'p90 |revision| pp'],
      rows.map(r => [MON[r.m - 1], String(r.n), fmtSigned(r.mean_rev, 4), fmt(r.mean_abs_rev, 4), fmt(r.p90_abs, 4)])));
  }
  paint();
}

function p4Trans(p4) {
  const host = $('p4Trans');
  const sm = p4.summary || {};
  const H4 = sm.headline_CPIAUCSL, C4 = sm.core_CPILFESL;
  if (!H4 || !H4.first_print_0_4) { stub(host, 'transition summary not present — panel stubbed.'); return; }
  const keys = {};
  for (const k of Object.keys(H4.first_print_0_4.to)) keys[k] = 1;
  for (const k of Object.keys((C4 && C4.first_print_0_4 && C4.first_print_0_4.to) || {})) keys[k] = 1;
  const order = Object.keys(keys).sort((a, b) => parseFloat(a) - parseFloat(b));

  const t = H('table');
  t.appendChild(H('caption', { text:
    'Every first print that printed as 0.4%, and the tenth it eventually rounded to. Headline n = ' +
    H4.first_print_0_4.n + ', core n = ' + (C4 ? C4.first_print_0_4.n : 0) + '. Rounding is half away from zero.' }));
  t.appendChild(H('thead', null, [H('tr', null,
    ['The 0.4 eventually became', 'Headline months', 'Headline share', 'Core months', 'Core share']
      .map(c => H('th', { text: c, scope: 'col' })))]));
  const tb = H('tbody');
  for (const k of order) {
    const hn = H4.first_print_0_4.to[k] || 0;
    const cn = (C4 && C4.first_print_0_4.to[k]) || 0;
    const isStay = parseFloat(k) === 0.4;
    const style = isStay ? 'font-weight:700' : null;
    tb.appendChild(H('tr', null, [
      H('th', { scope: 'row', text: k + '%' + (isStay ? '  (unchanged)' : ''), style: style }),
      H('td', { text: hn ? String(hn) : '—', style: style }),
      H('td', { text: hn ? fmt(100 * hn / H4.first_print_0_4.n, 1) + '%' : '—', style: style }),
      H('td', { text: cn ? String(cn) : '—', style: style }),
      H('td', { text: cn && C4 ? fmt(100 * cn / C4.first_print_0_4.n, 1) + '%' : '—', style: style })
    ]));
  }
  t.appendChild(tb);
  host.appendChild(H('div', { class: 'tablewrap' }, [t]));

  const trH = (p4.transitions || {}).CPIAUCSL, trC = (p4.transitions || {}).CPILFESL;
  $('p4TransNote').innerHTML =
    '<strong>A headline 0.4 stays a 0.4 only ' + fmt(100 * (1 - H4.first_print_0_4.share_changed), 0) + '% of the ' +
    'time.</strong> It is more likely to end up as a 0.3 than to stay put, and ' +
    fmt(H4.first_print_0_4.share_changed * 100, 0) + '% of the time it becomes something else. Across <em>all</em> ' +
    'headline first prints, ' + (trH ? fmt(trH.share_changed * 100, 1) : '—') + '% eventually round to a different ' +
    'tenth. Core is much stickier: ' + fmt((1 - (C4 ? C4.first_print_0_4.share_changed : 0)) * 100, 0) + '% of core ' +
    '0.4s stay, and only ' + (trC ? fmt(trC.share_changed * 100, 1) : '—') + '% of all core first prints change tenth. ' +
    'This says nothing about BLS being wrong — it says the tenths place of a single monthly print is not durable.';
}

function p4Se(p4, opts, byId) {
  const host = $('p4Se'), tbl = $('p4SeTable');
  let cur = 'CPIAUCSL';
  selectControl($('p4SeControls'), 'Series:', opts, cur, v => { cur = v; paint(); });

  function paint() {
    clear(host); clear(tbl);
    const rows = (p4.se_series || {})[cur] || [];
    const s = byId[cur];
    if (!rows.length) { stub(host, 'no first-print series for this series.'); return; }
    const xs = rows.map(r => mkey(r.obs_month));
    const trail = rows.map(r => r.trail12);
    const lo = rows.map(r => (r.trail12 == null || r.se == null) ? null : r.trail12 - 1.5 * r.se);
    const hi = rows.map(r => (r.trail12 == null || r.se == null) ? null : r.trail12 + 1.5 * r.se);

    lineChart(host, {
      x: xs,
      bands: [{ key: 'trail', label: '±1.5 sampling SE around the trailing 12-month mean', color: 'var(--series-2)', opacity: 0.22, lo: lo, hi: hi }],
      series: [
        { key: 'fp', label: 'First print', color: 'var(--series-1)', values: rows.map(r => r.first_print) },
        { key: 'trail', label: 'Real-time trailing 12-month mean', color: 'var(--series-2)', values: trail }
      ],
      overlayDots: rows.map((r, i) => r.within ? { x: xs[i], y: r.first_print, r: 4, fill: 'var(--series-3)', stroke: 'var(--surface-1)', strokeWidth: 1.5, title: ymLabel(r.obs_month) + ': not distinguishable from trend' } : null).filter(Boolean),
      yUnit: '%', yDp: 2, height: 320, zeroLine: true, endLabels: false,
      ariaLabel: s.label + ' first prints against their trailing trend'
    });
    host.appendChild(legend([{ label: 'Filled marker — inside the band, i.e. not distinguishable from trend', color: 'var(--series-3)' }]));

    const fl = s.se_flag || {};
    $('p4SeNote').innerHTML =
      '<strong>' + s.label + ':</strong> ' + (fl.n_within || 0) + ' of ' + (fl.n || 0) + ' months since ' +
      (fl.since ? ymLabel(fl.since) : '—') + ' — <strong>' + fmt((fl.share_within || 0) * 100, 1) + '%</strong> — sit ' +
      'within 1.5 sampling standard errors of their own real-time trailing average. Sampling SE for this series is ' +
      fmt(fl.se_1m, 2) + '&nbsp;pp' + (fl.se_exact ? '' : ', taken from the broader "' + fl.se_item + '" group, so it is a ' +
      '<strong>lower bound</strong> and this share is conservative') + '. For headline the honest reading cuts both ways: ' +
      'roughly 80% of headline prints genuinely do differ from the recent trend by more than sampling error, but nearly ' +
      'half of <em>core</em> prints do not — and core is the series read as "the signal". <strong>Sampling error is ' +
      'also the smaller half of the problem: for headline, seasonal-adjustment revision is about twice as large.</strong>';

    const all = p4.series.map(x => x.se_flag).filter(Boolean);
    tbl.appendChild(tableView(
      'Share of first prints not distinguishable from their own real-time trailing 12-month mean, since ' +
      (all[0] ? ymLabel(all[0].since) : '2019-01') + '. An asterisk marks a series matched to a broader published ' +
      'group, where the SE is a lower bound and the share is therefore too low.',
      ['Series', 'Months', 'Within 1.5 SE', 'Share %', 'SE of a 1-month change pp', 'SE group'],
      p4.series.map(x => {
        const f = x.se_flag || {};
        return [x.label + (f.se_exact ? '' : ' *'), String(f.n || 0), String(f.n_within || 0),
          fmt((f.share_within || 0) * 100, 1), fmt(f.se_1m, 2), f.se_item || '—'];
      })));
  }
  paint();
}

/* =======================================================================
 * P8 — the chained-CPI substitution gap
 * ===================================================================== */
const GAP_CUTS = [0.05, 0.15, 0.30, 0.60, 1.20];      /* percentage points */
const STAGE_COLOR = { final: 'var(--series-3)', interim: 'var(--series-4)', initial: 'var(--series-2)' };
const GROUP_SLOT = { SAF: 1, SAH: 2, SAA: 3, SAT: 4, SAM: 5, SAR: 6, SAE: 7, SAG: 8 };

function renderP8(p8) {
  if (!p8 || !p8.heatmap) {
    ['p8Heat', 'p8Groups', 'p8Rank', 'p8Rev'].forEach(id => stub($(id), 'p8_chained.json not available — panel stubbed.'));
    return;
  }
  const v = p8.validation || {};
  const lr = v.longrun || {};
  if ($('p8LongRun')) $('p8LongRun').textContent = fmt(lr.gap_pp_per_year, 2);
  if ($('p8Cum')) $('p8Cum').textContent = fmt(lr.cum_gap_pct, 1);
  p8Heat(p8);
  p8Groups(p8);
  p8Rank(p8);
  p8Rev(p8);
}

function p8Heat(p8) {
  const host = $('p8Heat'), tbl = $('p8HeatTable');
  const hm = p8.heatmap;
  const byCode = {};
  (p8.items || []).forEach(i => { byCode[i.item_code] = i; });
  const stageOf = {};
  if (p8.all_items) p8.all_items.months.forEach((m, i) => { stageOf[m] = p8.all_items.stage[i]; });

  const state = { s: 'expenditure' };
  segControl($('p8HeatControls'), 's', v => { state.s = v; paint(); });

  /* stage chips + the band beneath the month axis */
  const chips = $('p8Stages');
  clear(chips);
  chips.appendChild(H('span', { class: 'chip' }, [H('span', { class: 'dot', style: 'background:var(--series-3)' }), H('span', { text: 'final — actual expenditure data in' })]));
  chips.appendChild(H('span', { class: 'chip' }, [H('span', { class: 'dot', style: 'background:var(--series-4)' }), H('span', { text: 'interim — revised each quarter' })]));
  chips.appendChild(H('span', { class: 'chip' }, [H('span', { class: 'dot', style: 'background:var(--series-2)' }), H('span', { text: 'initial — published with the month, least reliable' })]));

  function paint() {
    clear(host); clear(tbl);
    const keep = [];
    hm.items.forEach((code, ri) => {
      const it = byCode[code];
      if (!it) return;
      if (state.s === 'expenditure' && it.section !== 'expenditure') return;
      keep.push({ ri: ri, it: it });
    });

    host.appendChild(scaleLegend('CPI-U minus C-CPI-U, 12-month change (pp):', divLegendEntries(GAP_CUTS, ' pp', 2),
      [{ color: 'var(--null-cell)', label: 'no data' }]));

    /* contiguous stage runs for the band */
    const band = [];
    let run = null;
    hm.months.forEach((m, ci) => {
      const s = stageOf[m] || null;
      if (!run || run.stage !== s) { run = { ci: ci, n: 1, stage: s, color: STAGE_COLOR[s] || 'var(--null-cell)' }; band.push(run); }
      else run.n++;
    });

    heatmap(host, {
      cols: hm.months,
      rows: keep.map(k => ({
        label: k.it.item_name.length > 30 ? k.it.item_name.slice(0, 29) + '…' : k.it.item_name,
        title: k.it.item_name + ' (' + k.it.item_code + ')',
        group: k.it.section === 'special' ? 'special' : (k.it.group_code || 'SA0')
      })),
      z: keep.map(k => hm.z[k.ri]),
      rowH: 15, labW: 190,
      fill: v => divColor(v, GAP_CUTS),
      colBand: band,
      colTick: ci => (hm.months[ci].slice(5) === '01' ? hm.months[ci].slice(0, 4) : null),
      tip: (ri, ci, v) => {
        const it = keep[ri].it;
        const m = hm.months[ci];
        return '<b>' + it.item_name + '</b><table class="tiptab">' +
          '<tr><td>Month</td><td>' + ymLabel(m) + '</td></tr>' +
          '<tr><td>Gap (CPI-U − C-CPI-U)</td><td>' + (v == null ? 'no data' : fmtSigned(v, 3) + ' pp') + '</td></tr>' +
          '<tr><td>Stage</td><td>' + (stageOf[m] || 'unknown') + '</td></tr>' +
          '<tr><td>Basket weight</td><td>' + fmt(it.weight, 2) + '%</td></tr>' +
          '<tr><td>Cumulative gap since 1999-12</td><td>' + fmtSigned(it.gap_cum, 2) + '%</td></tr></table>';
      },
      ariaLabel: 'Substitution gap by category and month'
    });

    const last12 = hm.months.slice(-12);
    tbl.appendChild(tableView(
      'Substitution gap (pp) by category, last 12 months. Rows nest — All items ⊃ Housing ⊃ Shelter — and are not ' +
      'independent measurements.',
      ['Item'].concat(last12.map(m => ymLabel(m))),
      keep.map(k => [k.it.item_name].concat(last12.map((m, j) => {
        const ci = hm.months.length - 12 + j;
        const v = hm.z[k.ri][ci];
        return v == null ? '—' : fmtSigned(v, 2);
      })))));

    const v8 = p8.validation || {};
    $('p8HeatNote').innerHTML =
      'Showing ' + keep.length + ' rows over ' + hm.months.length + ' months. Latest month <strong>' +
      ymLabel(v8.latest_ym) + '</strong> is <strong>' + v8.latest_stage + '</strong> stage; the newest month whose ' +
      'chained values are final is <strong>' + ymLabel(v8.latest_final_ym) + '</strong>. Anything after that is ' +
      'provisional. The commodity-and-service-group rows behind the toggle re-cover the same total a second way, which ' +
      'is why they are off by default.';
  }
  paint();
}

function p8Groups(p8) {
  const host = $('p8Groups'), ctl = $('p8GroupControls'), tbl = $('p8GroupsTable');
  const gc = p8.group_cum || {};
  const codes = Object.keys(gc);
  if (!codes.length) { stub(host, 'group_cum not present — panel stubbed.'); return; }

  const lastOf = a => { for (let i = a.length - 1; i >= 0; i--) if (a[i] != null && isFinite(a[i])) return a[i]; return 0; };
  const ranked = codes.slice().sort((a, b) => Math.abs(lastOf(gc[b].gap_cum)) - Math.abs(lastOf(gc[a].gap_cum)));
  const state = { on: {} };
  codes.forEach(c => { state.on[c] = ranked.indexOf(c) < 4; });   /* four on by default keeps direct end-labels */

  for (const c of codes) {
    const id = 'p8g-' + c;
    const cb = H('input', { type: 'checkbox', id: id });
    cb.checked = state.on[c];
    cb.addEventListener('change', () => { state.on[c] = cb.checked; paint(); });
    ctl.appendChild(H('label', { class: 'chk', for: id }, [cb,
      H('span', { class: 'sw sw-line', style: 'background:var(--series-' + GROUP_SLOT[c] + ')' }),
      H('span', { text: gc[c].name })]));
  }

  const months = gc[codes[0]].months;
  const xs = months.map(mkey);

  function paint() {
    clear(host); clear(tbl);
    const sel = codes.filter(c => state.on[c]);
    if (!sel.length) { stub(host, 'Select at least one group.'); return; }
    lineChart(host, {
      x: xs,
      series: sel.map(c => ({
        key: c, label: gc[c].name + ' (' + fmt(gc[c].weight, 1) + '% of basket)',
        color: 'var(--series-' + GROUP_SLOT[c] + ')',
        values: gc[c].gap_cum.map(v => (v == null || !isFinite(v)) ? null : v)
      })),
      yUnit: '%', yDp: 1, height: 330, zeroLine: true,
      ariaLabel: 'Cumulative substitution gap by major group since December 1999'
    });
    $('p8GroupNote').innerHTML =
      'Cumulative percent by which each group’s fixed-weight index has outrun its chained counterpart since ' +
      'December 1999. The top of the ranking is the falling-price technology complex — communication, durables, ' +
      'recreation, household furnishings — which is exactly where a fixed basket is most misleading: when a category’s ' +
      'price is falling relative to everything else, households buy more of it, the chained index gives it a growing ' +
      'weight, and the two measures separate fast. <strong>The pattern is descriptive; nothing here attributes it to a ' +
      'particular consumer decision.</strong>';
    const cols = ['Month'].concat(sel.map(c => gc[c].name + ' cumulative %'));
    const rowsT = [];
    for (let i = months.length - 1; i >= 0; i--) rowsT.push([ymLabel(months[i])].concat(sel.map(c => fmt(gc[c].gap_cum[i], 2))));
    tbl.appendChild(tableView('Cumulative gap by major group, ' + ymLabel(months[0]) + ' – ' + ymLabel(months[months.length - 1]) + '.', cols, rowsT));
  }
  paint();
}

function p8Rank(p8) {
  const host = $('p8Rank'), tbl = $('p8RankTable');
  const r = p8.ranking;
  if (!r || !r.all) { stub(host, 'ranking not present — panel stubbed.'); return; }
  const all = r.all.slice().sort((a, b) => b.latest_gap_yoy - a.latest_gap_yoy);
  const pick = all.slice(0, 10).concat(all.slice(-10)).filter((v, i, a2) => a2.indexOf(v) === i);

  barChart(host, {
    rows: pick.map(i => ({
      label: i.item_name.length > 30 ? i.item_name.slice(0, 29) + '…' : i.item_name,
      title: i.item_name + ' (' + i.item_code + ') — ' + fmt(i.weight, 2) + '% of the basket, cumulative gap since 1999-12 ' + fmtSigned(i.gap_cum, 1) + '%',
      values: [i.latest_gap_yoy]
    })),
    series: [{ label: '12-month gap (pp)', color: 'var(--div-pos)' }],
    diverging: true, unit: ' pp', dp: 2, tickDp: 1, barMax: 13,
    ariaLabel: '12-month substitution gap by category at the latest final month'
  });

  tbl.appendChild(tableView(
    'All 29 categories at ' + ymLabel(r.as_of) + ' (' + r.stage + ' stage), by 12-month gap.',
    ['Item', 'Code', 'Section', 'Weight %', '12-month gap pp', 'Cumulative gap since 1999-12 %'],
    all.map(i => [i.item_name, i.item_code, i.section, fmt(i.weight, 2), fmtSigned(i.latest_gap_yoy, 3), fmtSigned(i.gap_cum, 2)])));

  $('p8RankNote').innerHTML =
    'As of <strong>' + ymLabel(r.as_of) + '</strong>, the last month with final chained values. <strong>A negative bar ' +
    'means the chained index rose faster than the fixed-weight one</strong> for that category over those 12 months — ' +
    'routine at category level, and not a contradiction: the aggregate gap is the weighted net. Category-level gaps are ' +
    'noisier than the aggregate and flip sign regularly; only the all-items series has a long-run interpretation with ' +
    'external support.';
}

function p8Rev(p8) {
  const host = $('p8Rev'), tbl = $('p8RevTable');
  const rv = p8.revisions;
  if (!rv || !rv.all_items) { stub(host, 'revisions not present — panel stubbed.'); return; }
  const rows = rv.all_items.filter(r => r.rev_yoy_pp !== null && r.rev_yoy_pp !== undefined);
  if (!rows.length) { stub(host, 'no revision rows — panel stubbed.'); return; }
  const gapAt = {};
  if (p8.all_items) p8.all_items.months.forEach((m, i) => { gapAt[m] = p8.all_items.gap_yoy[i]; });
  const xs = rows.map(r => mkey(r.ym));

  lineChart(host, {
    x: xs,
    series: [
      { key: 'rev', label: 'Revision to the 12-month change, latest − initial (pp)', color: 'var(--series-2)', values: rows.map(r => r.rev_yoy_pp) },
      { key: 'gap', label: 'The all-items gap being measured (pp)', color: 'var(--series-1)', values: rows.map(r => (gapAt[r.ym] == null ? null : gapAt[r.ym])) }
    ],
    yUnit: ' pp', yDp: 2, height: 300, zeroLine: true,
    ariaLabel: 'Revision to the chained 12-month change against the gap itself'
  });

  const s = rv.summary || {};
  $('p8RevCaveat').innerHTML =
    '<strong>A single initial-stage month carries no information.</strong> Across the ' + s.n_final + ' all-items ' +
    'months whose initial print we recovered and which are now final, the mean absolute revision to the 12-month ' +
    'change is <strong>' + fmt(s.mean_abs_rev_yoy_pp, 3) + '&nbsp;pp</strong> (largest ' +
    fmt(s.max_abs_rev_yoy_pp, 3) + '&nbsp;pp) — <strong>larger than the average gap itself</strong>, which runs about ' +
    '0.27&nbsp;pp a year. ' + fmt(100 - s.pct_revised_up, 0) + '% of months are revised down, mean level revision ' +
    fmtSigned(s.mean_rev_pct, 3) + '%. The long-run average is solid; this month’s reading is not. Anyone quoting ' +
    '"the chained CPI says inflation was X" off a fresh release is quoting a number that will move.';

  tbl.appendChild(tableView(
    'All-items chained index: as first published against its value today, publications ' + rv.first_pub + ' – ' + rv.last_pub + '.',
    ['Month', 'Stage now', 'Initial level', 'Latest level', 'Level revision %', 'Revision to 12-month change pp', 'Gap for that month pp'],
    rv.all_items.slice().reverse().map(r => [ymLabel(r.ym), r.stage, fmt(r.initial, 3), fmt(r.latest, 3),
      fmtSigned(r.rev_pct, 3), r.rev_yoy_pp == null ? '—' : fmtSigned(r.rev_yoy_pp, 3),
      gapAt[r.ym] == null ? '—' : fmtSigned(gapAt[r.ym], 3)])));
}

/* =======================================================================
 * P10 — the lead-lag map
 * ===================================================================== */
function renderP10(p10) {
  if (!p10 || !p10.variants) {
    ['p10Net', 'p10Funnel', 'p10Sanity'].forEach(id => stub($(id), 'p10_network.json not available — panel stubbed.'));
    return;
  }
  p10Net(p10);
  p10Funnel(p10);
  p10Sanity(p10);
}

function p10Net(p10) {
  const host = $('p10Net'), tbl = $('p10NetTable'), casHost = $('p10Cascade'), legHost = $('p10Legend');
  const groupOrder = Object.keys(p10.groups || {});
  const state = { v: 'common_removed' };
  segControl($('p10Controls'), 'v', v => { state.v = v; paint(); });

  clear(legHost);
  legHost.appendChild(scaleLegend('Major group (also the ring position):',
    groupOrder.map((g, i) => ({ color: 'var(--series-' + (i + 1) + ')', label: p10.groups[g].name }))));
  const arrowLeg = document.createElement('div');
  legHost.appendChild(arrowLeg);

  function paint() {
    clear(host); clear(tbl); clear(casHost);
    const V = p10.variants[state.v];
    if (!V) { stub(host, 'variant not present.'); return; }
    // Hollow-node count is per-variant and shifts month to month, so derive it
    // from the data rather than hardcoding (raw and common_removed differ).
    clear(arrowLeg);
    const hollow = V.nodes.filter(n => ((n.in_deg || 0) + (n.out_deg || 0)) === 0).length;
    arrowLeg.appendChild(scaleLegend('Arrow:', [
      { color: 'var(--div-pos)', label: 'positive ρ — they move the same way' },
      { color: 'var(--div-neg)', label: 'negative ρ — opposite ways' }
    ], [{ color: 'var(--surface-1)', label: 'hollow node — no stable edge (' + hollow + ' of ' + V.nodes.length + ')' }]));
    const nodeBy = {};
    V.nodes.forEach(n => { nodeBy[n.code] = n; });

    const nodes = V.nodes.map(n => ({
      code: n.code, name: n.name, group: n.major, groupName: n.major_name,
      weight: n.weight, deg: (n.in_deg || 0) + (n.out_deg || 0),
      in_deg: n.in_deg, out_deg: n.out_deg, upstreamness: n.upstreamness
    }));
    const nodeMap = {};
    nodes.forEach(n => { nodeMap[n.code] = n; });

    networkChart(host, {
      nodes: nodes, nodeBy: nodeMap, edges: V.edges, cascade: V.cascade,
      groupOrder: groupOrder, maxHeight: 760,
      ariaLabel: 'Lead-lag map, ' + (state.v === 'raw' ? 'raw' : 'common factor removed') + ' variant',
      nodeTip: n => '<b>' + n.name + '</b><table class="tiptab">' +
        '<tr><td>Major group</td><td>' + n.groupName + '</td></tr>' +
        '<tr><td>Share of basket</td><td>' + fmt(n.weight, 2) + '%</td></tr>' +
        '<tr><td>Leads (out)</td><td>' + n.out_deg + '</td></tr>' +
        '<tr><td>Follows (in)</td><td>' + n.in_deg + '</td></tr>' +
        '<tr><td>Upstreamness</td><td>' + fmtSigned(n.upstreamness, 2) + '</td></tr></table>',
      edgeTip: e => '<b>' + nodeMap[e.src].name + ' → ' + nodeMap[e.dst].name + '</b><table class="tiptab">' +
        '<tr><td>Best lag</td><td>' + e.lag + ' month' + (e.lag === 1 ? '' : 's') + '</td></tr>' +
        '<tr><td>ρ</td><td>' + fmtSigned(e.rho, 3) + '</td></tr>' +
        '<tr><td>ρ in the other variant</td><td>' + fmtSigned(e.rho_other, 3) + '</td></tr>' +
        '<tr><td>FDR q</td><td>' + fmt(e.q, 3) + '</td></tr>' +
        '<tr><td>Windows passed</td><td>' + e.n_windows_pass + ' of 4</td></tr></table>',
      onSelect: n => renderCascade(V, nodeMap, n)
    });

    function renderCascade(V2, nm, n) {
      clear(casHost);
      if (!n) return;
      const c = (V2.cascade || {})[n.code];
      if (!c || (!(c.l1 || []).length && !(c.l2 || []).length)) {
        casHost.appendChild(H('p', { class: 'note', text: n.name + ' has no stable downstream edge in this variant.' }));
        return;
      }
      const rows = (c.l1 || []).map(d => ['1', nm[d.dst] ? nm[d.dst].name : d.dst, '—', String(d.lag), String(d.lag), fmtSigned(d.rho, 3)])
        .concat((c.l2 || []).map(d => ['2', nm[d.dst] ? nm[d.dst].name : d.dst, nm[d.via] ? nm[d.via].name : d.via, String(d.lag), String(d.cum_lag), fmtSigned(d.rho, 3)]));
      const t = H('table');
      t.appendChild(H('caption', { text: 'Two-level downstream cascade from ' + n.name + '. Cumulative lag is the sum along the path, and inherits every caveat above — it is not a propagation time.' }));
      t.appendChild(H('thead', null, [H('tr', null, ['Step', 'Follower', 'Via', 'Lag (m)', 'Cumulative lag (m)', 'ρ'].map(x => H('th', { text: x, scope: 'col' })))]));
      const tb = H('tbody');
      for (const r of rows) tb.appendChild(H('tr', null, r.map((v, i) => H(i === 0 ? 'th' : 'td', { text: v, scope: i === 0 ? 'row' : null }))));
      t.appendChild(tb);
      casHost.appendChild(H('div', { class: 'tablewrap' }, [t]));
    }

    tbl.appendChild(tableView(
      'All ' + V.edges.length + ' stable edges in the ' + (state.v === 'raw' ? 'raw' : 'common-factor-removed') +
      ' variant, strongest first. ρ, lag and q are full-sample; the window count comes from the four overlapping windows.',
      ['Leader', 'Follower', 'Lag (m)', 'ρ', 'ρ other variant', 'FDR q', 'Windows'],
      V.edges.slice().sort((a, b) => Math.abs(b.rho) - Math.abs(a.rho)).map(e => [
        nodeMap[e.src] ? nodeMap[e.src].name : e.src,
        nodeMap[e.dst] ? nodeMap[e.dst].name : e.dst,
        String(e.lag), fmtSigned(e.rho, 3), fmtSigned(e.rho_other, 3), fmt(e.q, 4), e.n_windows_pass + ' of 4'])));
  }
  paint();
}

function p10Funnel(p10) {
  const host = $('p10Funnel'), tbl = $('p10FunnelTable');
  const A = p10.variants.common_removed.stages, B = p10.variants.raw.stages;
  barChart(host, {
    rows: [
      { label: 'Candidate ordered pairs', title: 'Every ordered pair of the 74 nodes — "does A lead B" and "does B lead A" are different questions', values: [A.pairs, B.pairs] },
      { label: 'Pass |ρ| > 0.25 or q < 0.05', title: 'Screened on the full sample, either criterion', values: [A.screen_any, B.screen_any] },
      { label: 'Stable in ≥ 3 of 4 windows', title: 'Same sign, every best lag within ±2 months of their median — this is the graph', values: [A.stable, B.stable] },
      { label: '…and also passing on the full sample', title: 'The subset that is strong everywhere', values: [A.stable_and_full_screen, B.stable_and_full_screen] }
    ],
    series: [{ label: 'Common factor removed', color: 'var(--series-3)' }, { label: 'Raw', color: 'var(--series-2)' }],
    unit: ' pairs', dp: 0, tickDp: 0, barMax: 14,
    ariaLabel: 'Filtering stages, pairs surviving each'
  });
  const w = A.per_window || {};
  tbl.appendChild(tableView(
    'Pairs surviving each filtering stage, and per window. The 2008–2022 window is by far the loosest — it contains ' +
    'both the financial crisis and the 2021–22 inflation, when the cross-section really did move together, which is ' +
    'exactly why one window is not enough.',
    ['Stage / window', 'Common factor removed', 'Raw'],
    [['Candidate ordered pairs', String(A.pairs), String(B.pairs)],
     ['Tested (≥ 60 usable observations)', String(A.tested), String(B.tested)],
     ['|ρ| > 0.25, full sample', String(A.rho_screen), String(B.rho_screen)],
     ['FDR q < 0.05, full sample', String(A.fdr_pass), String(B.fdr_pass)],
     ['Either, full sample', String(A.screen_any), String(B.screen_any)],
     ['Stable (≥ 3 of 4 windows)', String(A.stable), String(B.stable)],
     ['Stable and also passing on the full sample', String(A.stable_and_full_screen), String(B.stable_and_full_screen)]]
      .concat(Object.keys(w).map(k => [
        'window ' + k + ' (' + w[k].start + ' – ' + w[k].end + '), either',
        String(w[k].screen_any), String((B.per_window[k] || {}).screen_any)]))));

  $('p10FunnelNote').innerHTML =
    '<strong>70 arrows out of 5,402 possible</strong>, most of them weak, and the strongest are a food chain and a BLS ' +
    'methodology link. That is a finding, not a failure: once the general inflation tide is taken out, CPI items barely ' +
    'lead each other at all, which is a direct argument against the folk model where a shock enters at one item and ' +
    'cascades predictably through the basket. Note also that ' + (A.stable - A.stable_and_full_screen) + ' of the ' +
    A.stable + ' stable edges do <em>not</em> clear the screen on the full sample — they pass in three windows but ' +
    'wash out when all 26 years are pooled.';
}

function p10Sanity(p10) {
  const host = $('p10Sanity');
  const rows = p10.sanity || [];
  if (!rows.length) { stub(host, 'sanity table not present — panel stubbed.'); return; }
  const names = [];
  const by = {};
  for (const r of rows) {
    if (names.indexOf(r.name) < 0) names.push(r.name);
    by[r.name + '|' + r.variant] = r;
  }
  const t = H('table');
  t.appendChild(H('caption', { text:
    'Ten relationships specified in the brief before the pipeline ran. "Stable" means the pair reappeared in at least ' +
    '3 of the 4 overlapping windows with the same sign and a consistent lag.' }));
  t.appendChild(H('thead', null, [H('tr', null,
    ['Expected relationship', 'Raw: lag / ρ / q', 'Raw', 'Common removed: lag / ρ / q', 'Common removed']
      .map(c => H('th', { text: c, scope: 'col' })))]));
  const tb = H('tbody');
  const cell = r => r ? (r.lag + ' m / ' + fmtSigned(r.rho, 3) + ' / q ' + fmt(r.q, 3) + ' / ' + r.n_windows_pass + ' of 4') : 'not found';
  const badge = r => {
    const ok = r && r.stable;
    return H('span', { class: 'badge ' + (ok ? 'pass' : 'fail'), text: ok ? '✓ stable' : '✕ not stable' });
  };
  for (const n of names) {
    const a = by[n + '|raw'], b = by[n + '|common_removed'];
    tb.appendChild(H('tr', null, [
      H('th', { scope: 'row', style: 'white-space:normal', text: n }),
      H('td', { text: cell(a) }),
      H('td', null, [badge(a)]),
      H('td', { text: cell(b) }),
      H('td', null, [badge(b)])
    ]));
  }
  t.appendChild(tb);
  host.appendChild(H('div', { class: 'tablewrap' }, [t]));

  $('p10SanityNote').innerHTML =
    '<strong>Energy → transport appears at the expected one-month lag in <code>raw</code> and dies when the common ' +
    'factor is removed.</strong> That is the intended result, not a miss: those items do not have a private ' +
    'relationship, they both ride the energy-driven tide that sits inside every series. The food chain — grocery ' +
    'categories leading food away from home by three months — and the rent ↔ owners’ equivalent rent link survive ' +
    'both variants. The rent/OER pair is a <em>positive control</em>: BLS builds OER from the same rent sample on the ' +
    'same six-month rotating panel, so it is a methodology link rather than a market one, and a method that could not ' +
    'find it would not be trustworthy anywhere else.';
}

/* =======================================================================
 * P6 — PPI → CPI pipeline pressure
 * ===================================================================== */

/* Curated facets: one lag-0 pair (gasoline, where the answer is "nothing is
 * in the pipe"), the largest food pair, the largest in-sum pair, and two
 * import-heavy pairs where the domestic PPI is the wrong upstream price. */
const P6_CURATED = [
  'WPS0571|SETB01',      /* gasoline — lag 0, rho 0.82 */
  'WPSFD41112|SAF11',    /* food at home */
  'WPS141101|SETA01',    /* new vehicles */
  'WPU121|SEHJ',         /* furniture and bedding */
  'WPU071201|SETC01'     /* tires */
];
/* Colour follows the entity, not the facet: producer price is always orange,
 * consumer price always blue, in every one of these facets. */
const P6_PPI_COLOR = 'var(--series-2)';
const P6_CPI_COLOR = 'var(--series-1)';
const P6_FD_DEFAULT = ['WPSFD4', 'WPSFD41', 'WPSFD42', 'WPSFD412'];
const P6_FD_COLOR = {
  WPSFD4:   'var(--series-1)',
  WPSFD41:  'var(--series-2)',
  WPSFD42:  'var(--series-3)',
  WPSFD412: 'var(--series-4)'
};
const P6_FD_SPARE = ['var(--series-5)', 'var(--series-7)', 'var(--series-8)', 'var(--series-6)'];

function esc(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function renderP6(p6) {
  const HOSTS = ['p6Press', 'p6Top', 'p6Sm', 'p6Pairs', 'p6Fd'];
  if (!p6 || !p6.pairs || !p6.pairs.length) {
    HOSTS.forEach(id => stub($(id), 'p6_pipeline.json not available — panel stubbed.'));
    return;
  }
  const cov = p6.pressure && p6.pressure.latest && p6.pressure.latest.weight_covered_pct;
  if (cov != null && $('p6Cover')) $('p6Cover').textContent = fmt(cov, 1);
  p6Pressure(p6);
  p6Small(p6);
  p6PairTable(p6);
  p6Fd(p6);
}

function p6Pressure(p6) {
  const P = p6.pressure;
  if (!P || !P.ym || !P.ym.length) { stub($('p6Press'), 'Pressure series missing from p6_pipeline.json.'); return; }
  const L = P.latest || {};
  const x = P.ym.map(mkey);
  const lo = P.total_bp.map((v, i) => (v == null || P.se_bp[i] == null) ? null : v - P.se_bp[i]);
  const hi = P.total_bp.map((v, i) => (v == null || P.se_bp[i] == null) ? null : v + P.se_bp[i]);

  /* the current value as a stat — the chart carries the path, the tile the reading */
  const kv = $('p6PressKv');
  const put = (k, v, sub) => {
    const d = H('div');
    d.appendChild(H('span', { class: 'k', text: k }));
    const val = H('span', { class: 'v' });
    val.appendChild(document.createTextNode(v));
    if (sub) val.appendChild(H('small', { text: sub }));
    d.appendChild(val);
    kv.appendChild(d);
  };
  put('Pressure in the pipe, still to come, ' + ymLabel(L.ym || P.ym[P.ym.length - 1]),
      fmtSigned(L.total_bp, 2) + ' bp', '±' + fmt(L.se_bp, 2) + ' · bp still to reach CPI over the coming ~12 months (already-realised pass-through discounted out), not next month');
  put('Comonotone band (pairs not independent)', '±' + fmt(L.se_bp_comonotone, 2) + ' bp');
  put('Pairs contributing', String(L.n_pairs));
  put('Basket weight in the sum', fmt(L.weight_covered_pct, 1) + '%',
      'of ' + fmt(L.weight_concordance_pct, 1) + '% paired');

  lineChart($('p6Press'), {
    x: x, height: 280, yUnit: ' bp', yDp: 1, zeroLine: true, zeroEmphasis: true,
    ariaLabel: 'Pipeline pressure still to come, basis points of CPI yet to pass through over the coming ~12 months, with a ±1 standard-error band',
    series: [{ key: 'total', label: 'Pipeline pressure (bp of CPI still to come)', color: 'var(--series-1)', values: P.total_bp }],
    bands: [{ key: 'total', label: '±1 SE, β errors treated as independent (a lower bound)', color: 'var(--band)', lo: lo, hi: hi }]
  });
  $('p6PressTable').appendChild(tableView(
    'Pipeline pressure, last ' + P.ym.length + ' months. Basis points still to reach the headline CPI over the ~12 months following each reading — each recent producer surprise discounted by the pass-through it has already delivered (not a next-month pressure). Not a forecast.',
    ['Month', 'Pressure (bp)', '±1 SE independent', '±1 SE comonotone'],
    P.ym.map((ym, i) => [ymLabel(ym), fmtSigned(P.total_bp[i], 3), fmt(P.se_bp[i], 3),
      fmt(P.se_bp_comonotone ? P.se_bp_comonotone[i] : null, 3)]).reverse()));

  /* what is in the total this month */
  const top = (L.top || []).slice();
  if (top.length) {
    const byPair = p6.pairs.reduce((m, p) => { m[p.pair_id] = p; return m; }, {});
    barChart($('p6Top'), {
      diverging: true, unit: ' bp', dp: 2, tickDp: 1,
      ariaLabel: 'Largest pair contributions to this month’s pipeline pressure',
      series: [{ label: 'Contribution (bp)', color: 'var(--series-1)' }],
      rows: top.map(t => ({
        label: t.cpi_item_name, title: t.cpi_item_name + ' (' + t.pair_id + ')',
        values: [t.contrib_bp]
      })),
      rowTip: r => {
        const t = top.find(q => q.cpi_item_name === r.label) || {};
        const p = byPair[t.pair_id] || {};
        return '<b>' + esc(t.cpi_item_name) + '</b><table class="tiptab">' +
          '<tr><td>Contribution</td><td>' + fmtSigned(t.contrib_bp, 2) + ' bp</td></tr>' +
          '<tr><td>±1 SE</td><td>' + fmt(t.contrib_se, 2) + ' bp</td></tr>' +
          '<tr><td>Best lag</td><td>' + t.best_lag + ' months</td></tr>' +
          '<tr><td>β₁₂</td><td>' + fmt(t.beta12, 3) + '</td></tr>' +
          '<tr><td>β₁₂ rolling range</td><td>' + fmt(t.beta12_range ? t.beta12_range[0] : null, 2) + ' … ' +
            fmt(t.beta12_range ? t.beta12_range[1] : null, 2) + '</td></tr>' +
          '<tr><td>Basket weight</td><td>' + fmt(t.weight, 3) + '%</td></tr>' +
          '<tr><td>Producer price</td><td>' + esc(p.ppi_title || t.pair_id.split('|')[0]) + '</td></tr>' +
          '</table>';
      }
    });
    $('p6TopTable').appendChild(tableView(
      'Largest contributions at ' + ymLabel(L.ym) + '. Contribution = recent producer-price deviation × β₁₂ × basket weight.',
      ['CPI item', 'Pair', 'Contribution (bp)', '±1 SE', 'Lag (m)', 'β₁₂', 'β₁₂ range', 'Weight %'],
      top.map(t => [t.cpi_item_name, t.pair_id, fmtSigned(t.contrib_bp, 3), fmt(t.contrib_se, 3),
        String(t.best_lag), fmt(t.beta12, 3),
        fmt(t.beta12_range ? t.beta12_range[0] : null, 2) + ' … ' + fmt(t.beta12_range ? t.beta12_range[1] : null, 2),
        fmt(t.weight, 3)])));
  } else {
    stub($('p6Top'), 'No per-pair contributions in this run.');
  }

  const lag0 = p6.pairs.filter(p => p.best_lag === 0).length;
  const weak = (p6.weak_pairs || []).length;
  $('p6PressNote').innerHTML =
    '<strong>' + lag0 + ' of the ' + p6.pairs.length + ' pairs peak at lag 0 and therefore contribute exactly zero ' +
    'by construction</strong> — gasoline, electricity, fuel oil, airline fares, milk. If the producer move and the ' +
    'consumer move land in the same month, nothing is in the pipe by the time the producer print exists. ' + weak +
    ' more are excluded as weak, and the import-price overlays are excluded because they would double-count the ' +
    'PPI pair on the same item. The PPI panel runs to ' + ymLabel(p6.latest_ppi_month) + ' and the CPI panel to ' +
    ymLabel(p6.latest_cpi_month) + '; the last four months of any PPI series are preliminary and will move.';
}

function p6Small(p6) {
  const host = $('p6Sm'), ctl = $('p6SmControls'), tbl = $('p6SmTable'), legHost = $('p6SmLegend');
  const byId = p6.pairs.reduce((m, p) => { m[p.pair_id] = p; return m; }, {});
  const curated = P6_CURATED.filter(id => byId[id] && byId[id].small_multiple);
  const rest = p6.pairs.filter(p => p.small_multiple && curated.indexOf(p.pair_id) < 0)
    .slice().sort((a, b) => b.weight - a.weight);

  legHost.appendChild(legend([
    { label: 'Producer price, month-over-month, shifted forward by the pair’s best lag', color: P6_PPI_COLOR },
    { label: 'Consumer price, month-over-month', color: P6_CPI_COLOR }
  ]));

  const state = { extra: '' };
  ctl.appendChild(H('span', { class: 'ctl-label', text: 'Curated: gasoline, food at home, new vehicles, furniture, tires.' }));
  selectControl(ctl, 'Add another pair:',
    [{ value: '', label: '— none —' }].concat(rest.map(p => ({
      value: p.pair_id,
      label: p.cpi_item_name + '  (' + fmt(p.weight, 2) + '% · lag ' + p.best_lag + (p.weak ? ' · weak' : '') + ')'
    }))), '', v => { state.extra = v; paint(); });

  function paint() {
    clear(host); clear(tbl);
    const ids = curated.concat(state.extra && byId[state.extra] ? [state.extra] : []);
    for (const id of ids) {
      const p = byId[id], sm = p.small_multiple;
      const cell = H('div', { class: 'sm-cell' });
      cell.appendChild(H('h4', { text: p.cpi_item_name }));
      const flags = [];
      if (p.weak) flags.push('weak');
      if (!p.lead_ok) flags.push('CPI leads');
      if (p.best_lag === 0) flags.push('lag 0 — contributes zero');
      if (!p.in_sum && p.best_lag !== 0 && !p.weak) flags.push('not in the sum');
      const sub = H('p', { class: 'sm-sub' });
      sub.appendChild(document.createTextNode(
        p.ppi_title + ' · lag ' + p.best_lag + 'm · ρ ' + fmt(p.rho_best, 2) + ' · ' + p.sa_mode +
        ' · ' + fmt(p.weight, 2) + '% of basket'));
      if (flags.length) { sub.appendChild(document.createTextNode(' · ')); sub.appendChild(H('span', { class: 'sm-warn', text: flags.join(' · ') })); }
      cell.appendChild(sub);
      const plot = H('div');
      cell.appendChild(plot);
      host.appendChild(cell);
      lineChart(plot, {
        x: sm.ym.map(mkey), height: 140, yUnit: '%', yDp: 1,
        zeroLine: true, endLabels: false, noLegend: true,
        ariaLabel: p.cpi_item_name + ': producer price shifted by ' + p.best_lag + ' months over consumer price',
        series: [
          { key: 'ppi', label: 'Producer (shifted ' + p.best_lag + 'm)', color: P6_PPI_COLOR, values: sm.ppi_shifted },
          { key: 'cpi', label: 'Consumer', color: P6_CPI_COLOR, values: sm.cpi }
        ]
      });
    }
    /* the accessible twin: the last two years of every facet on screen */
    const rows = [];
    for (const id of ids) {
      const p = byId[id], sm = p.small_multiple;
      const from = Math.max(0, sm.ym.length - 24);
      for (let i = sm.ym.length - 1; i >= from; i--) {
        rows.push([p.cpi_item_name, ymLabel(sm.ym[i]), fmtSigned(sm.ppi_shifted[i], 3), fmtSigned(sm.cpi[i], 3)]);
      }
    }
    tbl.appendChild(tableView(
      'Last 24 months of every facet shown above. Producer values are already shifted forward by that pair’s best lag, ' +
      'so the two columns in a row are the values the chart draws at the same x position. Percent per month.',
      ['CPI item', 'Month', 'Producer MoM %', 'Consumer MoM %'], rows));
  }
  paint();
}

function p6PairTable(p6) {
  const host = $('p6Pairs'), ctl = $('p6PairControls');
  const state = { conf: 'all', scope: 'all' };
  selectControl(ctl, 'Concordance confidence:', [
    { value: 'all', label: 'All 61 pairs' },
    { value: 'high', label: 'high — the producer series is the right upstream price' },
    { value: 'med', label: 'med' },
    { value: 'low', label: 'low — closest available proxy only' }
  ], 'all', v => { state.conf = v; paint(); });
  selectControl(ctl, 'Show:', [
    { value: 'all', label: 'Everything' },
    { value: 'sum', label: 'In the pressure sum' },
    { value: 'weak', label: 'Weak (β₁₂ not distinguishable from zero)' },
    { value: 'lead', label: 'CPI leads the PPI (alignment fails)' },
    { value: 'lag0', label: 'Lag 0 (nothing in the pipe)' },
    { value: 'ei', label: 'Import-price overlays' }
  ], 'all', v => { state.scope = v; paint(); });

  const CONF_RANK = { high: 0, med: 1, low: 2 };

  function paint() {
    clear(host);
    let rows = p6.pairs.filter(p =>
      (state.conf === 'all' || p.confidence === state.conf) &&
      (state.scope === 'all' ||
       (state.scope === 'sum' && p.in_sum) ||
       (state.scope === 'weak' && p.weak) ||
       (state.scope === 'lead' && !p.lead_ok) ||
       (state.scope === 'lag0' && p.best_lag === 0) ||
       (state.scope === 'ei' && p.source === 'ei')));

    const cols = [
      { label: 'CPI item' }, { label: 'Producer series' },
      { label: 'Confidence', title: 'How good the hand-built concordance row is — a property of the mapping, not of the statistics' },
      { label: 'Mode', title: 'SA, or NSA with calendar-month means removed from both sides' },
      { label: 'Lag (m)', num: true }, { label: 'ρ at best lag', num: true },
      { label: 'β₁₂', num: true, title: 'Cumulative pp response of the CPI item over 13 months to a 1pp producer-price move' },
      { label: 'SE (β₁₂)', num: true, title: 'Newey–West HAC' },
      { label: 'β₁₂ rolling range', num: true, title: 'Min and max across 10-year rolling windows — usually wider than the SE band, and the uncertainty that matters' },
      { label: 'Weight %', num: true }, { label: 'Flags' }
    ];
    const body = rows.map(p => {
      const b = (p.beta && p.beta['12']) || {};
      const r = p.beta12_range || [null, null];
      const flags = [];
      if (p.weak) flags.push('<span class="pill bad">weak</span>');
      if (!p.lead_ok) flags.push('<span class="pill bad">CPI leads</span>');
      if (p.best_lag === 0) flags.push('<span class="pill">lag 0</span>');
      if (p.in_sum) flags.push('<span class="pill ok">in sum</span>');
      if (p.source === 'ei') flags.push('<span class="pill">import overlay</span>');
      return [
        { k: p.cpi_item_name, t: p.cpi_item_name },
        { k: p.ppi_series, t: p.ppi_series + ' · ' + fitLabel(p.ppi_title, 260) },
        { k: CONF_RANK[p.confidence] === undefined ? 9 : CONF_RANK[p.confidence], t: p.confidence },
        { k: p.sa_mode, t: p.sa_mode },
        { k: p.best_lag, t: String(p.best_lag) },
        { k: p.rho_best, t: fmtSigned(p.rho_best, 3) },
        { k: b.beta, t: fmt(b.beta, 3) },
        { k: b.se, t: fmt(b.se, 3) },
        { k: r[1] === null || r[0] === null ? null : (r[1] - r[0]), t: fmt(r[0], 2) + ' … ' + fmt(r[1], 2) },
        { k: p.weight, t: fmt(p.weight, 3) },
        { k: flags.length, t: '', html: flags.join(' ') || '—' }
      ];
    });
    host.appendChild(sortableTable(cols, body, {
      sort: 9, dir: -1,
      caption: rows.length + ' of ' + p6.pairs.length + ' pairs shown. Click any column heading to sort; the rolling-range ' +
        'column sorts on the width of the range. NSA-demeaned rows are not comparable with seasonally adjusted rows.'
    }));
  }
  paint();

  const dropped = (p6.dropped || []).map(d => d.pair + ' (' + d.reason + ')');
  $('p6PairNote').innerHTML =
    '62 concordance rows were requested and <strong>61 kept</strong>. ' +
    (dropped.length ? 'Dropped: ' + esc(dropped.join('; ')) + '. ' : '') +
    'Best-lag distribution across the surviving pairs: ' +
    (() => {
      const c = {};
      for (const p of p6.pairs) c[p.best_lag] = (c[p.best_lag] || 0) + 1;
      return Object.keys(c).map(Number).sort((a, b) => a - b).map(k => k + 'm:' + c[k]).join('  ');
    })() +
    '. Gasoline is 0, beef / pork / milk / coffee one to two, garbage collection ten, dental services never ' +
    'convincingly — that map is the thing people most often guess wrong about.';
}

function p6Fd(p6) {
  const host = $('p6Fd'), ctl = $('p6FdControls'), tbl = $('p6FdTable');
  const FD = p6.fd_id || [];
  if (!FD.length) { stub(host, 'No FD-ID context series in this run.'); return; }
  const byId = FD.reduce((m, f) => { m[f.series_id] = f; return m; }, {});
  const base = P6_FD_DEFAULT.filter(id => byId[id]);
  const rest = FD.filter(f => base.indexOf(f.series_id) < 0);
  const state = { extra: '' };

  selectControl(ctl, 'Add a series:',
    [{ value: '', label: '— none —' }].concat(rest.map(f => ({ value: f.series_id, label: f.label }))),
    '', v => { state.extra = v; paint(); });

  function paint() {
    clear(host); clear(tbl);
    const ids = base.concat(state.extra && byId[state.extra] ? [state.extra] : []);
    /* one calendar axis across all shown series, so a series that starts late
     * is a real hole rather than a shifted line */
    let lo = Infinity, hi = -Infinity;
    for (const id of ids) { const f = byId[id]; lo = Math.min(lo, mkey(f.ym[0])); hi = Math.max(hi, mkey(f.ym[f.ym.length - 1])); }
    lo = Math.max(lo, hi - 12 * 12);            /* last 12 years */
    const x = []; for (let k = lo; k <= hi; k++) x.push(k);
    const series = ids.map((id, i) => {
      const f = byId[id];
      const m = {}; f.ym.forEach((ym, j) => { m[mkey(ym)] = f.yoy[j]; });
      return {
        key: id, label: f.label,
        color: P6_FD_COLOR[id] || P6_FD_SPARE[i % P6_FD_SPARE.length],
        values: x.map(k => (k in m) ? m[k] : null)
      };
    });
    lineChart(host, {
      x: x, height: 280, yUnit: '%', yDp: 1, zeroLine: true,
      ariaLabel: 'Producer price index final-demand aggregates, 12-month change',
      series: series
    });
    tbl.appendChild(tableView(
      'PPI final-demand and intermediate-demand aggregates, 12-month change, seasonally adjusted. Context only — a ' +
      'different weighting universe from the CPI and never paired with a CPI item.',
      ['Month'].concat(series.map(s => s.label)),
      x.map((k, i) => [mlabel(k)].concat(series.map(s => fmt(s.values[i], 2)))).reverse()));
  }
  paint();
}

/* =======================================================================
 * P7 — tariff-exposed vs domestic prices
 * ===================================================================== */

/* Colour follows the scheme. official_replica keeps the orange it has in P1
 * and P3 so the same construction is the same colour on every section. */
const P7_TIER = [
  { key: 'exposed',          label: 'Exposed — import content ≥ 25% (12.6% of the basket)', color: 'var(--series-8)' },
  { key: 'mid',              label: 'Mid — 10–25% (19.9%)',                                 color: 'var(--series-4)' },
  { key: 'domestic',         label: 'Domestic — under 10% (65.2%)',                         color: 'var(--series-1)' },
  { key: 'official_replica', label: 'All items — official replica',                         color: 'var(--series-2)' }
];
/* import content of a consumer dollar; the two tier cutoffs are cut points,
 * so the ramp reads the same way the tiers do */
const P7_CUTS = [0.10, 0.175, 0.25, 0.375];
const P7_CUT_LABELS = ['< 10% (domestic)', '10 – 17.5%', '17.5 – 25%', '25 – 37.5% (exposed)', '≥ 37.5%'];

function renderP7(p7) {
  const HOSTS = ['p7Series', 'p7Tree', 'p7Event', 'p7Timeline'];
  if (!p7 || !p7.series || !p7.series.length) {
    HOSTS.forEach(id => stub($(id), 'p7_tariff.json not available — panel stubbed.'));
    return;
  }
  const last = p7.series[p7.series.length - 1];
  const set = (id, v) => { if ($(id)) $(id).textContent = v; };
  set('p7LatestMonth', ymLabel(p7.latest_month));
  set('p7Exposed', fmt(last.exposed_yoy, 2));
  set('p7Mid', fmt(last.mid_yoy, 2));
  set('p7Domestic', fmt(last.domestic_yoy, 2));
  set('p7Replica', fmt(last.official_replica_yoy, 2));
  p7Series(p7);
  p7Tree(p7);
  p7Event(p7);
  p7Timeline(p7);
}

function p7Series(p7) {
  const host = $('p7Series'), ctl = $('p7SeriesControls'), tbl = $('p7SeriesTable');
  const S7 = p7.series;
  const x = S7.map(r => mkey(r.ym));
  const state = { markers: 'study' };

  selectControl(ctl, 'Tariff-action markers:', [
    { value: 'study', label: 'The 25 estimated events' },
    { value: 'all', label: 'Every action in the timeline (' + (p7.events || []).length + ')' },
    { value: 'none', label: 'None' }
  ], 'study', v => { state.markers = v; paint(); });

  function annotations() {
    if (state.markers === 'none') return [];
    const src = state.markers === 'study'
      ? (p7.event_study || []).map(e => ({ d: e.event_date, action: e.action, scope: e.scope, pp: e.ad_valorem_change_pp, conf: e.confidence, url: e.source_url, pt: e.pretrend_ok }))
      : (p7.events || []).map(e => ({ d: e.effective_date, action: e.action, scope: e.scope, pp: e.ad_valorem_change_pp, conf: e.confidence, url: e.source_url, pt: null }));
    return src.map(e => ({
      x: mkey(e.d.slice(0, 7)),
      label: e.d + ' · ' + e.action,
      title: esc(e.scope || '') +
        '<br>Rate change: ' + (e.pp === null || e.pp === undefined ? 'varies' : fmtSigned(e.pp, 0) + ' pp') +
        ' · confidence ' + esc(e.conf) +
        (e.pt === null ? '' : '<br>Pre-trend: ' + (e.pt ? 'ok' : 'FAILS')) +
        '<br>Source: ' + esc(sourceHost(e.url))
    }));
  }

  function paint() {
    clear(host);
    lineChart(host, {
      x: x, height: 320, yUnit: '%', yDp: 1, zeroLine: true,
      ariaLabel: 'Twelve-month inflation by import-content tier, with tariff-action markers',
      series: P7_TIER.map(t => ({
        key: t.key, label: t.label, color: t.color, values: S7.map(r => r[t.key + '_yoy'])
      })),
      annotations: annotations()
    });
  }
  paint();

  const tw = (p7.tier_weights || []).filter(t => t.weight_year === Math.max.apply(null, (p7.tier_weights || []).map(q => q.weight_year)));
  const wof = t => { const r = tw.find(q => q.tier === t); return r ? fmt(r.weight, 1) + '% of the basket, ' + r.n_items + ' items' : '—'; };
  $('p7SeriesNote').innerHTML =
    'Tier weights at the latest weight year — exposed ' + esc(wof('high')) + '; mid ' + esc(wof('mid')) +
    '; domestic ' + esc(wof('low')) + '. The <strong>mid line has a two-month hole where the others have one</strong>: ' +
    'October 2025 has no CPI for anybody, and November 2025 additionally fails the 90%-coverage gate for the mid tier ' +
    'at 86.0%, which is the gate working as designed on a narrower weight base. ' +
    'Marker dots sit at the top of the plot and are reachable by keyboard; every action is also in the timeline table below.';

  tbl.appendChild(tableView(
    'Twelve-month change by import-content tier. Index levels are December-chained Laspeyres over published BLS item indexes.',
    ['Month', 'Exposed %', 'Mid %', 'Domestic %', 'Replica %', 'Exposed − domestic (pp)'],
    S7.slice().reverse().map(r => [ymLabel(r.ym), fmt(r.exposed_yoy, 2), fmt(r.mid_yoy, 2), fmt(r.domestic_yoy, 2),
      fmt(r.official_replica_yoy, 2),
      (r.exposed_yoy == null || r.domestic_yoy == null) ? '—' : fmtSigned(r.exposed_yoy - r.domestic_yoy, 2)])));
}

function sourceHost(url) {
  if (!url) return 'no source recorded';
  const m = String(url).match(/^https?:\/\/([^/]+)/);
  return m ? m[1] : String(url);
}

function p7Tree(p7) {
  const host = $('p7Tree'), ctl = $('p7TreeControls'), tbl = $('p7TreeTable'), legHost = $('p7TreeLegend');
  const T = p7.treemap || [];
  if (!T.length) { stub(host, 'No item-level import shares in this run.'); return; }
  const groups = [];
  for (const t of T) if (groups.indexOf(t.major_group) < 0) groups.push(t.major_group);
  const state = { group: 'all' };

  selectControl(ctl, 'Major group:',
    [{ value: 'all', label: 'All 179 leaf items' }].concat(groups.map(g => ({ value: g, label: g }))),
    'all', v => { state.group = v; paint(); });

  legHost.appendChild(scaleLegend('Import content of a consumer dollar, colour:',
    P7_CUT_LABELS.map((l, i) => ({ color: 'var(--seq-' + (i + 1) + ')', label: l }))));

  function paint() {
    clear(host); clear(tbl);
    const items = state.group === 'all' ? T : T.filter(t => t.major_group === state.group);
    const wsum = items.reduce((s, t) => s + t.weight, 0);
    treemap(host, {
      height: 380,
      ariaLabel: 'CPI leaf items, area is basket weight and fill is total import content',
      items: items.map(t => ({
        label: t.name,
        sub: fmt(t.share_total * 100, 0) + '% · ' + fmt(t.weight, 2) + '%',
        value: t.weight,
        fill: seqColor(t.share_total, P7_CUTS),
        ink: t.share_total >= P7_CUTS[2] ? 'var(--surface-1)' : 'var(--text-primary)',
        title: t.name + ' (' + t.item_code + ')',
        rows: [
          ['Total import content', fmt(t.share_total * 100, 1) + '%'],
          ['of which direct', fmt(t.share_direct * 100, 1) + '%'],
          ['Tier', t.tier === 'high' ? 'exposed' : t.tier === 'low' ? 'domestic' : 'mid'],
          ['Basket weight', fmt(t.weight, 3) + '%'],
          ['Major group', t.major_group],
          ['Share of this view', fmt(100 * t.weight / wsum, 2) + '%']
        ]
      }))
    });
    const cols = [
      { label: 'Item' }, { label: 'Code' }, { label: 'Major group' },
      { label: 'Import content %', num: true }, { label: 'of which direct %', num: true },
      { label: 'Tier' }, { label: 'Basket weight %', num: true }
    ];
    tbl.appendChild(sortableTable(cols, items.map(t => [
      { k: t.name, t: t.name }, { k: t.item_code, t: t.item_code }, { k: t.major_group, t: t.major_group },
      { k: t.share_total, t: fmt(t.share_total * 100, 1) },
      { k: t.share_direct, t: fmt(t.share_direct * 100, 1) },
      { k: t.tier === 'high' ? 0 : t.tier === 'mid' ? 1 : 2, t: t.tier === 'high' ? 'exposed' : t.tier === 'low' ? 'domestic' : 'mid' },
      { k: t.weight, t: fmt(t.weight, 3) }
    ]), { sort: 3, dir: -1, caption: items.length + ' items. Sorted by import content; click a heading to re-sort.' }));
  }
  paint();

  const wm = (p7.method && p7.method.weighted_means) || {};
  const mr = (p7.method && p7.method.margin_rates) || {};
  $('p7TreeNote').innerHTML =
    'Weighted means: <strong>' + fmt(wm.pce_weighted * 100, 1) + '% of PCE</strong> (the figure to compare against ' +
    'the published 10–12% ballpark, and it lands inside it), <strong>' + fmt(wm.cpi_basket_all * 100, 1) +
    '% of the CPI basket</strong> — lower because the CPI weights shelter at about a third versus 15–18% in PCE, and ' +
    'shelter is entirely domestic — and <strong>' + fmt(wm.cpi_basket_goods * 100, 1) + '% of the CPI goods basket</strong>. ' +
    'Margins and transport carry only embodied content: wholesale ' + fmt(mr.wholesale, 3) + ', retail ' +
    fmt(mr.retail, 3) + ', transport ' + fmt(mr.transport, 3) + '. Method: <code>' +
    esc((p7.method && p7.method.method) || 'unknown') + '</code> on the ' + p7.basis_year + ' benchmark.';
}

function p7Event(p7) {
  const host = $('p7Event'), ctl = $('p7EventControls'), kv = $('p7EventKv');
  const ES = (p7.event_study || []).slice().sort((a, b) => a.event_date < b.event_date ? -1 : 1);
  if (!ES.length) { stub(host, 'No event study in this run.'); return; }
  const HEAD = ES.find(e => e.action === 'ieepa_baseline') || ES[ES.length - 1];
  const state = { ev: HEAD.event_date };

  selectControl(ctl, 'Action:', ES.map(e => ({
    value: e.event_date,
    label: e.event_date + '  ' + e.action + '  (' + fmtSigned(e.cum_0_12, 2) + ' pp' +
      (e.pretrend_ok ? '' : ', pre-trend FAILS') + ')'
  })), state.ev, v => { state.ev = v; paint(); });

  function paint() {
    clear(host); clear(kv); clear($('p7EventBundle'));
    const e = ES.find(q => q.event_date === state.ev) || HEAD;
    const coefs = (e.coefs || []).slice().sort((a, b) => a.rel_month - b.rel_month);
    const x = coefs.map(c => c.rel_month);
    const coef = coefs.map(c => c.coef);
    const se = coefs.map(c => c.se);
    /* the cumulative path is the running sum from month 0; before month 0 it
     * does not exist, so it is null rather than zero */
    let acc = 0;
    const cum = coefs.map(c => {
      if (c.rel_month < 0) return null;
      acc += (c.coef === null || !isFinite(c.coef)) ? 0 : c.coef;
      return acc;
    });

    const put = (k, v, sub) => {
      const d = H('div');
      d.appendChild(H('span', { class: 'k', text: k }));
      const val = H('span', { class: 'v' });
      val.appendChild(document.createTextNode(v));
      if (sub) val.appendChild(H('small', { text: sub }));
      d.appendChild(val);
      kv.appendChild(d);
    };
    const ratio = (e.cum_0_12_se && isFinite(e.cum_0_12_se) && e.cum_0_12_se !== 0)
      ? Math.abs(e.cum_0_12 / e.cum_0_12_se) : null;
    put('Cumulative 0…+12', fmtSigned(e.cum_0_12, 2) + ' pp', '± ' + fmt(e.cum_0_12_se, 2));
    put('That is', ratio === null ? '—' : '≈ ' + fmt(ratio, 1) + ' SE',
        ratio !== null && ratio < 1.96 ? 'not conventionally significant' : 'at |t| ≥ 1.96');
    put('Pre-trend, months −6…−1', fmtSigned(e.pretrend_t, 2) + ' t', e.pretrend_ok ? 'passes' : 'FAILS');
    put('Items', e.n_exposed + ' vs ' + e.n_domestic, 'exposed vs domestic');
    put('Rate change', e.ad_valorem_change_pp == null ? 'varies' : fmtSigned(e.ad_valorem_change_pp, 0) + ' pp',
        'confidence ' + e.confidence);

    lineChart(host, {
      x: x, height: 300, yUnit: ' pp', yDp: 1, zeroLine: true, zeroEmphasis: true, endLabels: false,
      xTicks: [-6, -3, 0, 3, 6, 9, 12],
      xTickFmt: v => (v > 0 ? '+' + v : String(v)),
      xLabel: v => 'Relative month ' + (v > 0 ? '+' + v : String(v)),
      ariaLabel: 'Event study for ' + e.action + ': per-horizon coefficients with a ±1 SE band and the cumulative path',
      series: [
        { key: 'coef', label: 'Per-horizon coefficient on the exposed − domestic gap', color: 'var(--series-1)', values: coef },
        { key: 'cum', label: 'Cumulative from month 0', color: 'var(--series-3)', values: cum }
      ],
      bands: [{
        key: 'coef', label: '±1 SE on the per-horizon coefficient (Newey–West, 6 lags)', color: 'var(--band)',
        lo: coef.map((v, i) => v === null ? null : v - se[i]),
        hi: coef.map((v, i) => v === null ? null : v + se[i])
      }],
      annotations: [{ x: 0, label: e.event_date, title: esc(e.action) + '<br>' + esc(e.scope || '') }],
      overlayBars: [{
        x: 12, lo: e.cum_0_12 - e.cum_0_12_se, hi: e.cum_0_12 + e.cum_0_12_se, color: 'var(--series-3)',
        title: '<b>Cumulative 0…+12</b><table class="tiptab">' +
          '<tr><td>Effect</td><td>' + fmtSigned(e.cum_0_12, 2) + ' pp</td></tr>' +
          '<tr><td>HAC SE, full covariance</td><td>' + fmt(e.cum_0_12_se, 2) + ' pp</td></tr>' +
          '<tr><td>Ratio</td><td>' + (ratio === null ? '—' : '≈ ' + fmt(ratio, 1) + ' SE') + '</td></tr></table>'
      }]
    });

    $('p7EventNote').innerHTML =
      'The <strong>cumulative line carries an interval only at month +12</strong>: the pipeline publishes the ' +
      'cumulative standard error from the full coefficient covariance for the 0…+12 total and not for the ' +
      'intermediate horizons, and drawing a band across them would mean inventing that covariance. The band on the ' +
      'per-horizon line is the published Newey–West(6) standard error for each relative month. Sample: ' +
      e.n_obs + ' months, ±24 around the action, with −24…−7 as the omitted baseline.';

    const bund = e.bundled_actions || [];
    const box = $('p7EventBundle');
    if (bund.length) {
      box.appendChild(H('p', { class: 'note', html:
        '<strong>' + bund.length + ' other tariff action' + (bund.length > 1 ? 's' : '') + ' took effect in the same ' +
        'month and cannot be separated from this one by monthly CPI:</strong> ' + esc(bund.join(', ')) + '. ' +
        'The representative row for this month is <code>' + esc(e.representative_row) + '</code>, chosen by duty ' +
        'impulse — rate change × annual import value covered — not by the largest rate change. Source: ' +
        (e.source_url ? '<a href="' + esc(e.source_url) + '" rel="noopener">' + esc(sourceHost(e.source_url)) + '</a>' : 'none recorded') + '.' }));
    } else {
      box.appendChild(H('p', { class: 'note', html:
        'No other eligible tariff action took effect in this month. Source: ' +
        (e.source_url ? '<a href="' + esc(e.source_url) + '" rel="noopener">' + esc(sourceHost(e.source_url)) + '</a>' : 'none recorded') + '.' }));
    }
  }
  paint();

  const cols = [
    { label: 'Date' }, { label: 'Action' },
    { label: 'cum 0…+12 (pp)', num: true }, { label: 'SE', num: true },
    { label: '|cum| / SE', num: true },
    { label: 'Pre-trend t', num: true }, { label: 'Pre-trend' },
    { label: 'Rate change (pp)', num: true }, { label: 'Bundled', num: true }, { label: 'Confidence' }
  ];
  $('p7EventTable').appendChild(sortableTable(cols, ES.map(e => {
    const ratio = (e.cum_0_12_se && isFinite(e.cum_0_12_se) && e.cum_0_12_se !== 0) ? Math.abs(e.cum_0_12 / e.cum_0_12_se) : null;
    return [
      { k: e.event_date, t: e.event_date },
      { k: e.action, t: e.action },
      { k: e.cum_0_12, t: fmtSigned(e.cum_0_12, 2) },
      { k: e.cum_0_12_se, t: fmt(e.cum_0_12_se, 2) },
      { k: ratio, t: ratio === null ? '—' : fmt(ratio, 1) },
      { k: e.pretrend_t, t: fmtSigned(e.pretrend_t, 2) },
      { k: e.pretrend_ok ? 1 : 0, t: '', html: e.pretrend_ok ? '<span class="pill ok">ok</span>' : '<span class="pill bad">fails</span>' },
      { k: e.ad_valorem_change_pp, t: e.ad_valorem_change_pp == null ? 'varies' : fmtSigned(e.ad_valorem_change_pp, 0) },
      { k: (e.bundled_actions || []).length, t: String((e.bundled_actions || []).length) },
      { k: e.confidence, t: e.confidence }
    ];
  }), { sort: 0, dir: 1,
    caption: ES.length + ' estimated events, ' + ES.filter(e => !e.pretrend_ok).length +
      ' of them failing the pre-trend check. Sort on "Pre-trend" to group them. Standard errors for events after ' +
      'mid-2025 are computed on truncated windows and are not comparable with the earlier rows.' }));
}

function p7Timeline(p7) {
  const host = $('p7Timeline'), ctl = $('p7TimelineControls');
  const EV = (p7.events || []).slice();
  if (!EV.length) { stub(host, 'No tariff timeline in this run.'); return; }
  const state = { f: 'all' };
  selectControl(ctl, 'Show:', [
    { value: 'all', label: 'All ' + EV.length + ' actions' },
    { value: 'used', label: 'Eligible for the event study' },
    { value: 'medium', label: 'Medium confidence only (secondary sourcing or an inferred rate)' },
    { value: 'varies', label: 'Rate shown as "varies"' }
  ], 'all', v => { state.f = v; paint(); });

  const cols = [
    { label: 'Effective date', title: 'The date duties began to be collected — not the announcement date' },
    { label: 'Action' }, { label: 'Scope' },
    { label: 'Rate change (pp)', num: true, title: 'The change in the ad-valorem rate, not the level: 10→25% is 15' },
    { label: 'Confidence' }, { label: 'Eligible' }, { label: 'Source' }
  ];

  function paint() {
    clear(host);
    const rows = EV.filter(e =>
      state.f === 'all' ||
      (state.f === 'used' && e.used_in_event_study) ||
      (state.f === 'medium' && e.confidence === 'medium') ||
      (state.f === 'varies' && e.ad_valorem_change_pp == null));
    host.appendChild(sortableTable(cols, rows.map(e => [
      { k: e.effective_date, t: e.effective_date },
      { k: e.action, t: e.action },
      { k: e.scope || '', t: e.scope || '—' },
      { k: e.ad_valorem_change_pp, t: e.ad_valorem_change_pp == null ? 'varies' : fmtSigned(e.ad_valorem_change_pp, 0) },
      { k: e.confidence === 'high' ? 0 : 1, t: e.confidence },
      { k: e.used_in_event_study ? 1 : 0, t: '', html: e.used_in_event_study ? '<span class="pill ok">yes</span>' : '<span class="pill">no</span>' },
      { k: e.source_url || '', t: sourceHost(e.source_url),
        html: e.source_url ? '<a href="' + esc(e.source_url) + '" rel="noopener">' + esc(sourceHost(e.source_url)) + '</a>' : '—' }
    ]), { sort: 0, dir: 1,
      caption: rows.length + ' of ' + EV.length + ' rows. "Eligible" means the row cleared the ≥5 pp and ' +
        'confidence filters; at most one event per month is actually estimated, so an eligible row can still be ' +
        'a bundled action rather than an estimated event.' }));
  }
  paint();
}

/* =======================================================================
 * P9 — metro CPI vs local wages and rents
 * ===================================================================== */

/* The three metros the pipeline calls out as the widest remaining CPI-rent /
 * market-rent gaps, the two widest the other way, and the two whose CPI
 * pricing area is wider than the CBSA they are joined to. */
const P9_HIGHLIGHT = ['Miami', 'Denver', 'Philadelphia', 'San Francisco', 'Houston', 'Urban Hawaii', 'Urban Alaska'];
const P9_RENT_COLOR = 'var(--series-1)';
const P9_ZORI_COLOR = 'var(--series-3)';

function renderP9(p9) {
  const HOSTS = ['p9Real', 'p9Shelter', 'p9Disp'];
  if (!p9 || !p9.metros || !p9.metros.length) {
    HOSTS.forEach(id => stub($(id), 'p9_metro.json not available — panel stubbed.'));
    return;
  }
  const C = p9.coverage || {};
  if ($('p9WageQ')) $('p9WageQ').textContent = C.latest_wage_quarter || '—';
  if ($('p9CpiM')) $('p9CpiM').textContent = C.latest_cpi_month || '—';
  p9Real(p9);
  p9Shelter(p9);
  p9Disp(p9);
}

function p9Real(p9) {
  const host = $('p9Real'), ctl = $('p9RealControls'), tbl = $('p9RealTable');
  const M = p9.metros.filter(m => m.latest_real && m.latest_real.real_yoy != null);
  if (!M.length) { stub(host, 'No real-wage rows in this run.'); return; }
  const state = { sort: 'real' };
  selectControl(ctl, 'Order:', [
    { value: 'real', label: 'Real wage growth, fastest first' },
    { value: 'name', label: 'Metro name' },
    { value: 'pop', label: 'Population' },
    { value: 'cpi', label: 'Local inflation, highest first' }
  ], 'real', v => { state.sort = v; paint(); });

  const shortName = m => m.area_name.split(',')[0].split('-')[0];

  function paint() {
    clear(host);
    const rows = M.slice().sort((a, b) =>
      state.sort === 'name' ? (a.area_name < b.area_name ? -1 : 1) :
      state.sort === 'pop' ? b.pop2020 - a.pop2020 :
      state.sort === 'cpi' ? b.latest_real.cpi_yoy - a.latest_real.cpi_yoy :
      b.latest_real.real_yoy - a.latest_real.real_yoy);
    barChart(host, {
      diverging: true, unit: ' pp', dp: 2, tickDp: 1,
      ariaLabel: 'Real wage growth by metro, wage 12-month change minus CPI 12-month change',
      series: [{ label: 'Wage growth − local inflation (pp)', color: 'var(--series-1)' }],
      rows: rows.map(m => ({
        label: shortName(m) + (m.approx_geo ? ' *' : ''),
        title: m.area_name,
        values: [m.latest_real.real_yoy]
      })),
      rowTip: r => {
        const m = rows.find(q => q.area_name === r.title) || {};
        const R = m.latest_real || {};
        return '<b>' + esc(m.area_name) + '</b><table class="tiptab">' +
          '<tr><td>Wage growth, ' + esc(R.yq) + '</td><td>' + fmtSigned(R.wage_yoy, 2) + '%</td></tr>' +
          '<tr><td>Local CPI (' + esc(R.cpi_month_used) + ')</td><td>' + fmtSigned(R.cpi_yoy, 2) + '%</td></tr>' +
          '<tr><td>Difference</td><td>' + fmtSigned(R.real_yoy, 2) + ' pp</td></tr>' +
          '<tr><td>Wage basis</td><td>' + (R.wage_own === '5' ? 'private' : 'total covered') + '</td></tr>' +
          '<tr><td>Publication schedule</td><td>' + esc(m.schedule) + '</td></tr>' +
          (m.approx_geo ? '<tr><td>Geography</td><td>CPI area wider than the CBSA</td></tr>' : '') +
          '</table>';
      }
    });
  }
  paint();

  const q = (p9.coverage || {}).latest_wage_quarter || '';
  const fallback = M.filter(m => m.latest_real.wage_own !== '5').length;
  $('p9RealNote').innerHTML =
    '<strong>' + fallback + ' of ' + M.length + ' metros in ' + esc(q) + ' use the total-covered wage basis</strong>, ' +
    'not private: MSA-level private average weekly wage is suppressed for every MSA from 2025Q3 onward. Where both ' +
    'bases exist they differ by 0.34 pp on average, so this cross-section is on a slightly different footing than ' +
    'quarters before 2025Q3, and a year-over-year change is never taken across bases. The wage panel is ' +
    '<strong>7–8 months behind the price panel</strong> by construction — QCEW posts a quarter roughly 5–6 months ' +
    'after it ends. Metros marked <strong>*</strong> have a CPI pricing area wider than the CBSA the wage data is ' +
    'joined to (Urban Hawaii, Urban Alaska).';

  tbl.appendChild(tableView(
    'Real wage growth by metro, ' + esc(q) + '. wage_yoy − cpi_yoy, percentage points. The CPI month used is the last ' +
    'month inside the quarter for which that metro actually published an all-items index.',
    ['Metro', 'Quarter', 'Wage %', 'Local CPI %', 'Real (pp)', 'CPI month used', 'Wage basis', 'Schedule', 'Population 2020'],
    M.slice().sort((a, b) => b.latest_real.real_yoy - a.latest_real.real_yoy).map(m => [
      m.area_name + (m.approx_geo ? ' *' : ''), m.latest_real.yq,
      fmtSigned(m.latest_real.wage_yoy, 2), fmtSigned(m.latest_real.cpi_yoy, 2), fmtSigned(m.latest_real.real_yoy, 2),
      m.latest_real.cpi_month_used, m.latest_real.wage_own === '5' ? 'private' : 'total covered',
      m.schedule, m.pop2020.toLocaleString('en-US')])));
}

function p9Shelter(p9) {
  const host = $('p9Shelter'), ctl = $('p9ShelterControls'), tbl = $('p9ShelterTable'), legHost = $('p9ShelterLegend');
  const SM = p9.shelter_small_multiples || [];
  if (!SM.length) { stub(host, 'No shelter small multiples in this run.'); return; }
  const byCbsa = p9.metros.reduce((m, r) => { m[r.cbsa] = r; return m; }, {});
  const lagByCbsa = (p9.best_lag_table || []).reduce((m, r) => { m[r.cbsa] = r; return m; }, {});
  const isHighlight = s => P9_HIGHLIGHT.some(h => s.name.indexOf(h) === 0);
  const state = { set: 'highlight' };

  legHost.appendChild(legend([
    { label: 'CPI rent of primary residence, 12-month change', color: P9_RENT_COLOR },
    { label: 'Zillow asking rents (ZORI), 12-month change, lagged 12 months', color: P9_ZORI_COLOR }
  ]));
  selectControl(ctl, 'Metros:', [
    { value: 'highlight', label: 'The widest gaps both ways, plus the two flagged geographies (7)' },
    { value: 'all', label: 'All 23 metros' },
    { value: 'approx', label: 'Only the approximate-geography metros (2)' }
  ], 'highlight', v => { state.set = v; paint(); });

  function paint() {
    clear(host); clear(tbl);
    const shown = state.set === 'all' ? SM
      : state.set === 'approx' ? SM.filter(s => byCbsa[s.cbsa] && byCbsa[s.cbsa].approx_geo)
      : SM.filter(isHighlight);
    for (const s of shown) {
      const m = byCbsa[s.cbsa] || {};
      const lg = lagByCbsa[s.cbsa] || {};
      const cell = H('div', { class: 'sm-cell' });
      cell.appendChild(H('h4', { text: s.name }));
      const sub = H('p', { class: 'sm-sub' });
      const gap = m.latest_shelter ? m.latest_shelter.gap : null;
      sub.appendChild(document.createTextNode(
        'gap ' + fmtSigned(gap, 2) + ' pp · best lag ' + (lg.best_lag === undefined ? '—' : lg.best_lag + 'm') +
        ' (r ' + fmt(lg.best_corr, 2) + ') · ' + (s.schedule === 'monthly' ? 'monthly' : s.schedule + ' months for all-items')));
      if (m.approx_geo) {
        sub.appendChild(document.createTextNode(' · '));
        sub.appendChild(H('span', { class: 'sm-warn', text: 'approx_geo — CPI area wider than the ZORI region' }));
      }
      if (lg.best_corr !== undefined && lg.best_corr < 0.3) {
        sub.appendChild(document.createTextNode(' · '));
        sub.appendChild(H('span', { class: 'sm-warn', text: 'no usable relationship at any lag' }));
      }
      cell.appendChild(sub);
      const plot = H('div');
      cell.appendChild(plot);
      host.appendChild(cell);
      lineChart(plot, {
        x: s.series.map(r => mkey(r[0])), height: 140, yUnit: '%', yDp: 1,
        zeroLine: true, endLabels: false, noLegend: true,
        ariaLabel: s.name + ': CPI rent against Zillow asking rents lagged twelve months',
        series: [
          { key: 'rent', label: 'CPI rent', color: P9_RENT_COLOR, values: s.series.map(r => r[1]) },
          { key: 'zori', label: 'ZORI, lagged 12m', color: P9_ZORI_COLOR, values: s.series.map(r => r[2]) }
        ]
      });
    }
    const rows = [];
    for (const s of shown) {
      const from = Math.max(0, s.series.length - 12);
      for (let i = s.series.length - 1; i >= from; i--) {
        const r = s.series[i];
        rows.push([s.name, ymLabel(r[0]), fmt(r[1], 2), fmt(r[2], 2),
          (r[1] == null || r[2] == null) ? '—' : fmtSigned(r[1] - r[2], 2)]);
      }
    }
    tbl.appendChild(tableView(
      'Last 12 months for every metro shown above. CPI rent of primary residence and ZORI, both 12-month changes; ' +
      'the ZORI column is already lagged 12 months, so a row compares this month’s CPI rent with the market a ' +
      'year earlier.',
      ['Metro', 'Month', 'CPI rent %', 'ZORI lagged 12m %', 'Gap (pp)'], rows));
  }
  paint();

  const lags = (p9.best_lag_table || []).map(r => r.best_lag).slice().sort((a, b) => a - b);
  const med = lags.length ? lags[Math.floor(lags.length / 2)] : null;
  const gaps = p9.metros.filter(m => m.latest_shelter && m.latest_shelter.gap != null)
    .slice().sort((a, b) => b.latest_shelter.gap - a.latest_shelter.gap);
  const nm = m => m.area_name.split(',')[0].split('-')[0];
  const g3 = gaps.slice(0, 3).map(m => nm(m) + ' ' + fmtSigned(m.latest_shelter.gap, 1) + ' pp').join(', ');
  const gL = gaps.slice(-2).map(m => nm(m) + ' ' + fmtSigned(m.latest_shelter.gap, 1) + ' pp').join(' and ');
  $('p9ShelterNote').innerHTML =
    'At ' + ymLabel(p9.coverage.latest_cpi_month) + ' the widest gaps with the CPI still <em>above</em> where the ' +
    'market was a year earlier are <strong>' + esc(g3) + '</strong>; the widest the other way, where the CPI has ' +
    'already overshot the market signal, are <strong>' + esc(gL) + '</strong>. ' +
    'Median best lag across the 23 metros is <strong>' + med + ' months</strong> (range ' + lags[0] + '–' +
    lags[lags.length - 1] + '); at a fixed 12 months the mean correlation is 0.735. ' +
    'CPI rent still running <em>above</em> the market a year earlier means the CPI has catching-up left to do; ' +
    'below means it has already overshot the market signal. <strong>Shelter and rent are monthly for all 23 metros</strong> ' +
    '— the bimonthly stagger applies to all-items and food, not to the housing survey — so these facets have no ' +
    'schedule holes even for the bimonthly metros.';
}

function p9Disp(p9) {
  const host = $('p9Disp'), ctl = $('p9DispControls'), tbl = $('p9DispTable');
  const D = (p9.dispersion || []).filter(d => d.sd != null);
  if (!D.length) { stub(host, 'No dispersion series in this run.'); return; }
  const state = { m: 'sd' };
  const seg = H('div', { class: 'seg', role: 'group', 'aria-label': 'Dispersion measure' });
  ['sd', 'range'].forEach((k, i) => {
    const b = H('button', { type: 'button', 'aria-pressed': i === 0 ? 'true' : 'false',
      text: k === 'sd' ? 'Population-weighted standard deviation' : 'Range (highest − lowest metro)' });
    b.dataset.m = k;
    seg.appendChild(b);
  });
  ctl.appendChild(H('span', { class: 'ctl-label', text: 'Measure:' }));
  ctl.appendChild(seg);
  segControl(ctl, 'm', v => { state.m = v; paint(); });

  const peak = D.reduce((a, b) => (b.sd > a.sd ? b : a), D[0]);
  const x = D.map(d => mkey(d.ym));

  function paint() {
    clear(host);
    const isSd = state.m === 'sd';
    lineChart(host, {
      x: x, height: 300, yUnit: ' pp', yDp: 1,
      ariaLabel: 'Dispersion of 12-month inflation across metro areas',
      series: [{
        key: state.m,
        label: isSd ? 'Population-weighted standard deviation across metros (pp)' : 'Highest metro − lowest metro (pp)',
        color: 'var(--series-1)',
        values: D.map(d => isSd ? d.sd : d.range)
      }],
      annotations: [{
        x: mkey(peak.ym), label: ymLabel(peak.ym),
        title: 'Peak dispersion — standard deviation ' + fmt(peak.sd, 2) + ' pp. ' +
          esc(peak.max_metro) + ' at ' + fmt(peak.max_yoy, 1) + '% and ' + esc(peak.min_metro) + ' at ' +
          fmt(peak.min_yoy, 1) + '% in the same month.'
      }],
      overlayDots: D.filter(d => d.comp_flag).map(d => ({
        x: mkey(d.ym), y: isSd ? d.sd : d.range, r: 4.5,
        fill: 'var(--div-neg)', stroke: 'var(--surface-1)', strokeWidth: 2,
        title: ymLabel(d.ym) + ' — composition flag: the odd/even panel swap moved the cross-metro mean by ' +
          fmtSigned(d.comp_delta, 2) + ' pp (' + d.n_metros + ' metros published)'
      }))
    });
  }
  paint();

  const flagged = D.filter(d => d.comp_flag);
  const last = D[D.length - 1];
  const pre = D.filter(d => d.ym >= '2015-01' && d.ym <= '2019-12');
  const preMean = pre.length ? pre.reduce((s, d) => s + d.sd, 0) / pre.length : null;
  $('p9DispNote').innerHTML =
    'In the quiet years before COVID the population-weighted standard deviation sat around <strong>' +
    fmt(preMean, 2) + ' pp</strong>. It peaked at <strong>' + fmt(peak.sd, 2) + ' pp in ' + ymLabel(peak.ym) +
    '</strong>. At ' + ymLabel(last.ym) + ' it is <strong>' + fmt(last.sd, 2) + ' pp</strong> — essentially the ' +
    'pre-COVID normal, so the metro divergence of 2021–23 has closed. The <strong>' + flagged.length + ' marked ' +
    'months</strong> (of ' + D.length + ') are where the odd/even panel swap moved the cross-metro mean by more than ' +
    '0.3 pp; they cluster in mid-2022 to mid-2023 and their signs alternate, which is the signature of a composition ' +
    'artefact rather than of inflation. The flag is null — and so unmarked — for the latest month and for the months ' +
    'either side of the October 2025 hole, because it needs both neighbours.';

  tbl.appendChild(tableView(
    'Cross-metro dispersion of the 12-month all-items change, population-weighted, over whichever metros published ' +
    'that month (minimum 8). Adjacent months hold different cities.',
    ['Month', 'Metros', 'Mean %', 'SD (pp)', 'Range (pp)', 'Lowest', 'Lowest %', 'Highest', 'Highest %', 'Composition Δ (pp)', 'Flagged'],
    D.slice().reverse().map(d => [ymLabel(d.ym), String(d.n_metros), fmt(d.mean, 2), fmt(d.sd, 2), fmt(d.range, 2),
      d.min_metro, fmt(d.min_yoy, 2), d.max_metro, fmt(d.max_yoy, 2),
      d.comp_delta == null ? '—' : fmtSigned(d.comp_delta, 2), d.comp_flag ? 'yes' : (d.comp_delta == null ? '—' : 'no')])));
}

/* =======================================================================
 * Method & sources — generated_at per file
 * ===================================================================== */
function renderMeta(D) {
  const rows = [];
  const meta = {
    p1: ['p1_salience.json', 'P1 — frequency-weighted indexes, sensitivity, bootstrap SEs, latest-month item weights'],
    p2: ['p2_distribution.json', 'P2 — cross-section statistics, ridgeline, variance decomposition'],
    p3: ['p3_persistence.json', 'P3 — half-life treemap, sticky/flexible indexes and the Atlanta Fed overlay, weight buckets'],
    p4: ['p4_vintages.json', 'P4 — vintage fan, month-of-year revisions, the 0.4 transition table, the 1.5 SE flag'],
    p5: ['p5_quality.json', 'P5 — imputation, response rates, stress composite, notices'],
    p6: ['p6_pipeline.json', 'P6 — pipeline pressure and its band, per-pair small multiples, the pass-through table, the PPI final-demand context strip'],
    p7: ['p7_tariff.json', 'P7 — the three import-content tiers, the item treemap, the event study and the tariff timeline'],
    p8: ['p8_chained.json', 'P8 — the substitution-gap heatmap, cumulative divergence by group, rankings, revisions'],
    p9: ['p9_metro.json', 'P9 — metro real wage growth, shelter vs ZORI small multiples, cross-metro dispersion'],
    p10: ['p10_network.json', 'P10 — the lead–lag map, the filtering funnel, the pre-specified sanity table'],
    r1: ['r1_expectations.json', 'R1 — expectations regressions (used for the footnote under P1)']
  };
  for (const k of ORDER) {
    const m = meta[k];
    const d = D[k];
    let gen = 'not loaded';
    if (d) {
      const g = d.generated_at || d.generated || (d.meta && d.meta.generated_at);
      gen = g ? new Date(g).toISOString().replace('T', ' ').slice(0, 16) + ' UTC' : 'no generated_at';
    }
    let note = m[1];
    if (REPAIRED[m[0]]) {
      note += ' — ⚠ ' + REPAIRED[m[0]] + ' non-JSON NaN/Infinity value' + (REPAIRED[m[0]] > 1 ? 's' : '') +
        ' repaired to null on load; the pipeline should emit null.';
    }
    rows.push([m[0], gen, note]);
  }
  const t = H('table');
  t.appendChild(H('thead', null, [H('tr', null, ['File', 'Generated', 'Panels'].map(c => H('th', { text: c, scope: 'col' })))]));
  const tb = H('tbody');
  for (const r of rows) {
    tb.appendChild(H('tr', null, [
      H('th', { scope: 'row' }, [H('a', { href: DATA + r[0], rel: 'noopener', text: r[0] })]),
      H('td', { text: r[1] }),
      H('td', { style: 'white-space:normal', text: r[2] })
    ]));
  }
  t.appendChild(tb);
  $('genTable').appendChild(H('div', { class: 'tablewrap' }, [t]));
}
