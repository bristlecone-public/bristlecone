/* charts.js — minimal dependency-free SVG chart primitives for the CPI Lab dashboard.
 *
 * Design rules come from the `dataviz` skill:
 *   - 2px lines, >=8px markers, ~10% area washes, hairline solid grid/axes
 *   - colours are CSS custom properties, so light/dark swap without a redraw
 *   - a legend whenever >= 2 series; selective direct end-labels; no per-point numbers
 *   - every chart ships a table view (the light-mode contrast relief + a11y twin)
 *   - crosshair + tooltip on lines, per-mark tooltip on bars, keyboard equivalents
 *
 * Charts register themselves and redraw on container resize.
 */
'use strict';

const NS = 'http://www.w3.org/2000/svg';

/* ---------- tiny DOM helpers ---------- */

function S(tag, attrs, kids) {
  const n = document.createElementNS(NS, tag);
  if (attrs) for (const k in attrs) {
    if (attrs[k] === null || attrs[k] === undefined) continue;
    n.setAttribute(k, attrs[k]);
  }
  if (kids) for (const c of [].concat(kids)) if (c) n.appendChild(c);
  return n;
}
function H(tag, attrs, kids) {
  const n = document.createElement(tag);
  if (attrs) for (const k in attrs) {
    if (attrs[k] === null || attrs[k] === undefined) continue;
    if (k === 'text') n.textContent = attrs[k];
    else if (k === 'html') n.innerHTML = attrs[k];
    else n.setAttribute(k, attrs[k]);
  }
  if (kids) for (const c of [].concat(kids)) if (c) n.appendChild(c);
  return n;
}
function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }

/* ---------- month keys ---------- */
/* "YYYY-MM" -> integer month index, so a missing month (2025-10) leaves a real
 * hole on the x axis instead of being silently closed up. */
function mkey(ym) {
  const y = +ym.slice(0, 4), m = +ym.slice(5, 7);
  return y * 12 + (m - 1);
}
function mlabel(k, style) {
  const y = Math.floor(k / 12), m = k % 12;
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  if (style === 'year') return String(y);
  if (style === 'short') return MON[m] + " '" + String(y).slice(2);
  return MON[m] + ' ' + y;
}
function ymLabel(ym) { return mlabel(mkey(ym)); }

/* ---------- number formatting ---------- */
function fmt(v, dp) {
  if (v === null || v === undefined || !isFinite(v)) return '—';
  return v.toFixed(dp === undefined ? 2 : dp);
}
function fmtSigned(v, dp) {
  if (v === null || v === undefined || !isFinite(v)) return '—';
  return (v > 0 ? '+' : '') + v.toFixed(dp === undefined ? 2 : dp);
}

/* ---------- scales & ticks ---------- */
function linScale(d0, d1, r0, r1) {
  const span = (d1 - d0) || 1;
  const f = v => r0 + (v - d0) / span * (r1 - r0);
  f.invert = p => d0 + (p - r0) / ((r1 - r0) || 1) * span;
  f.domain = [d0, d1]; f.range = [r0, r1];
  return f;
}

/* "nice" tick values for a numeric axis */
function niceTicks(lo, hi, target) {
  target = target || 5;
  if (!isFinite(lo) || !isFinite(hi) || lo === hi) return [lo];
  const raw = (hi - lo) / target;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm >= 7.5 ? 10 : norm >= 3.5 ? 5 : norm >= 1.5 ? 2 : 1) * mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) {
    out.push(Math.abs(v) < step * 1e-9 ? 0 : +v.toFixed(10));
  }
  return out;
}

/* year-boundary ticks for a month axis, thinned to fit */
function monthTicks(k0, k1, width) {
  const years = [];
  for (let k = Math.ceil(k0 / 12) * 12; k <= k1; k += 12) years.push(k);
  const room = Math.max(1, Math.floor(width / 56));
  const every = Math.max(1, Math.ceil(years.length / room));
  return years.filter((_, i) => i % every === 0);
}

/* ---------- label fitting ----------
 * SVG text has no wrapping and no ellipsis, so a label that does not fit is a
 * clipped label. Truncate to the available box instead, and keep the full
 * string on the <title> / tooltip / table. ~5.6px per character at 11.5px
 * system-ui is a deliberate slight over-estimate. */
function fitLabel(text, px, perChar) {
  const cpx = perChar || 5.6;
  const max = Math.floor(px / cpx);
  if (max < 2) return '';
  return text.length <= max ? text : text.slice(0, max - 1) + '…';
}

/* ---------- extent over nullable arrays ---------- */
function extent(arrays) {
  let lo = Infinity, hi = -Infinity;
  for (const a of arrays) for (const v of a) {
    if (v === null || v === undefined || !isFinite(v)) continue;
    if (v < lo) lo = v; if (v > hi) hi = v;
  }
  if (!isFinite(lo)) return [0, 1];
  return [lo, hi];
}
function padded(lo, hi, frac) {
  const p = (hi - lo) * (frac === undefined ? 0.08 : frac) || Math.abs(hi || 1) * 0.1;
  return [lo - p, hi + p];
}

/* ---------- shared tooltip ---------- */
let TIP = null;
function tip() {
  if (!TIP) {
    TIP = H('div', { class: 'tip', role: 'status', 'aria-live': 'polite' });
    document.body.appendChild(TIP);
  }
  return TIP;
}
function showTip(html, clientX, clientY) {
  const t = tip();
  t.innerHTML = html;
  t.classList.add('on');
  const r = t.getBoundingClientRect();
  let x = clientX + 14, y = clientY + 14;
  if (x + r.width > window.innerWidth - 8) x = clientX - r.width - 14;
  if (y + r.height > window.innerHeight - 8) y = clientY - r.height - 14;
  t.style.left = Math.max(8, x) + 'px';
  t.style.top = Math.max(8, y) + 'px';
}
function hideTip() { if (TIP) TIP.classList.remove('on'); }
document.addEventListener('scroll', hideTip, true);

/* ---------- chart registry / responsive redraw ---------- */
const CHARTS = [];
function register(node, draw) {
  /* NOTE: stale entries (panels re-rendered on toggle) are dropped in redrawAll, not here —
     charts are often mounted inside a DocumentFragment, so isConnected is false at register
     time and evicting here would purge freshly-mounted charts from the registry. */
  const rec = { node: node, draw: draw, w: 0 };
  CHARTS.push(rec);
  return rec;
}
function _doRedrawAll() {
  for (let i = CHARTS.length - 1; i >= 0; i--) {
    if (!CHARTS[i].node.isConnected) CHARTS.splice(i, 1);
  }
  for (const c of CHARTS) {
    const w = c.node.clientWidth;
    if (w > 0 && Math.abs(w - c.w) > 2) { c.w = w; try { c.draw(w); } catch (e) { console.error('chart draw failed', e); } }
  }
}
let _redrawPending = false;
function redrawAll() {
  /* rAF is throttled to zero in hidden/background tabs, so pair it with a timeout
     fallback — whichever fires first wins */
  if (_redrawPending) return;
  _redrawPending = true;
  let done = false;
  const run = () => { if (done) return; done = true; _redrawPending = false; _doRedrawAll(); };
  requestAnimationFrame(run);
  setTimeout(run, 150);
}
window.addEventListener('resize', redrawAll);

function mountChart(container, drawFn) {
  const rec = register(container, drawFn);
  if (typeof ResizeObserver !== 'undefined') {
    const ro = new ResizeObserver(() => {
      const w = container.clientWidth;
      if (w > 0 && Math.abs(w - rec.w) > 2) { rec.w = w; try { drawFn(w); } catch (e) { console.error(e); } }
    });
    ro.observe(container);
  }
  const w0 = container.clientWidth || 720;
  rec.w = w0;
  drawFn(w0);
  /* mounted detached (fragment) → clientWidth was 0 and we drew at the 720 fallback;
     re-measure after insertion and redraw at the real width. setTimeout, not rAF: rAF
     never fires in hidden/background tabs. Two passes in case the fragment is appended late. */
  const remeasure = () => {
    const w = container.clientWidth;
    if (w > 0 && Math.abs(w - rec.w) > 2) { rec.w = w; try { drawFn(w); } catch (e) { console.error(e); } }
  };
  setTimeout(remeasure, 0);
  setTimeout(remeasure, 300);
  return rec;
}

/* ---------- legend (always present for >= 2 series) ---------- */
function legend(items) {
  const box = H('div', { class: 'legend' });
  for (const it of items) {
    const swatch = it.kind === 'band'
      ? H('span', { class: 'sw sw-band', style: 'background:' + it.color })
      : it.kind === 'area'
        ? H('span', { class: 'sw sw-area', style: 'background:' + it.color })
        : H('span', { class: 'sw sw-line', style: 'background:' + it.color });
    box.appendChild(H('span', { class: 'legend-item' }, [swatch, H('span', { text: it.label })]));
  }
  return box;
}

/* ---------- table view (a11y twin, and the light-mode contrast relief) ---------- */
function tableView(caption, cols, rows) {
  const d = H('details', { class: 'tableview' });
  d.appendChild(H('summary', { text: 'Show data table' }));
  const t = H('table');
  if (caption) t.appendChild(H('caption', { text: caption }));
  const thead = H('thead');
  thead.appendChild(H('tr', null, cols.map(c => H('th', { text: c, scope: 'col' }))));
  t.appendChild(thead);
  const tb = H('tbody');
  for (const r of rows) tb.appendChild(H('tr', null, r.map((v, i) => H(i === 0 ? 'th' : 'td', { text: v, scope: i === 0 ? 'row' : null }))));
  t.appendChild(tb);
  d.appendChild(H('div', { class: 'tablewrap' }, [t]));
  return d;
}

/* =========================================================================
 * SORTABLE TABLE — a table that *is* the panel content rather than the
 * accessible twin of a chart, so it is visible by default and its columns
 * sort. Cells are either a plain string or {k, t} where `k` is the sort key
 * and `t` the rendered text (so "—" sorts as a missing value, not as a word,
 * and "0.41 (0.13)" sorts on 0.41).
 *   cols: [{label, num:true|false, title?}]
 *   rows: [[cell, ...]]
 *   opts: { sort: colIndex, dir: 1|-1, caption, groupBy: colIndex }
 * ========================================================================= */
function sortableTable(cols, rows, opts) {
  opts = opts || {};
  const wrap = H('div', { class: 'tablewrap' });
  const t = H('table', { class: 'sortable' });
  if (opts.caption) t.appendChild(H('caption', { text: opts.caption }));
  const key = c => (c && typeof c === 'object') ? c.k : c;
  const txt = c => (c && typeof c === 'object') ? c.t : c;

  let sort = opts.sort === undefined ? 0 : opts.sort;
  let dir = opts.dir === undefined ? 1 : opts.dir;

  const thead = H('thead'), tr = H('tr');
  const ths = cols.map((c, i) => {
    const b = H('button', { type: 'button', class: 'sortbtn', text: c.label });
    const th = H('th', { scope: 'col', 'aria-sort': 'none' }, [b]);
    if (c.title) th.setAttribute('title', c.title);
    b.addEventListener('click', () => {
      if (sort === i) dir = -dir; else { sort = i; dir = cols[i].num ? -1 : 1; }
      paint();
    });
    tr.appendChild(th);
    return th;
  });
  thead.appendChild(tr);
  t.appendChild(thead);
  const tb = H('tbody');
  t.appendChild(tb);

  function paint() {
    ths.forEach((th, i) => th.setAttribute('aria-sort', i === sort ? (dir > 0 ? 'ascending' : 'descending') : 'none'));
    const num = cols[sort].num;
    const sorted = rows.slice().sort((a, b) => {
      const ka = key(a[sort]), kb = key(b[sort]);
      const na = ka === null || ka === undefined || (num && !isFinite(ka));
      const nb = kb === null || kb === undefined || (num && !isFinite(kb));
      if (na && nb) return 0;
      if (na) return 1;              /* missing always sinks, both directions */
      if (nb) return -1;
      if (num) return (ka - kb) * dir;
      return (String(ka) < String(kb) ? -1 : String(ka) > String(kb) ? 1 : 0) * dir;
    });
    clear(tb);
    for (const r of sorted) {
      const row = H('tr');
      r.forEach((c, i) => {
        const cell = H(i === 0 ? 'th' : 'td', { scope: i === 0 ? 'row' : null });
        if (c && typeof c === 'object' && c.html) cell.innerHTML = c.html;
        else cell.textContent = txt(c) === null || txt(c) === undefined ? '—' : String(txt(c));
        if (c && typeof c === 'object' && c.cls) cell.className = c.cls;
        row.appendChild(cell);
      });
      tb.appendChild(row);
    }
  }
  paint();
  wrap.appendChild(t);
  return wrap;
}

/* =========================================================================
 * LINE CHART (time series over month keys)
 *   opts: { x:[mkeys], series:[{key,label,color,values[]}],
 *           bands:[{key,label,color,lo[],hi[]}],
 *           yUnit, yDp, height, annotations:[{x,label,title}],
 *           zeroLine, endLabels, valueFmt,
 *           noLegend        — suppress the per-chart legend (small multiples
 *                             carry one shared legend above the grid instead)
 *           xTicks, xTickFmt, xLabel
 *                           — the x axis is a plain number line, so a chart
 *                             whose x is not a calendar month (P7's event
 *                             study is indexed on months *relative to* the
 *                             action) can supply its own ticks and labels
 *           overlayBars:[{x,lo,hi,color,title}]
 *                           — a capped vertical interval at one x. Used where
 *                             an interval is published for a single point and
 *                             not for the whole path: drawing a full band
 *                             there would be inventing the other months.
 * Nulls break the line — never interpolated (2025-10 has no CPI).
 * ========================================================================= */
function lineChart(container, opts) {
  const height = opts.height || 300;
  const svgHost = H('div', { class: 'plot' });
  const legHost = H('div');
  container.appendChild(legHost);
  container.appendChild(svgHost);
  const xLabel = opts.xLabel || (k => mlabel(k));

  if (!opts.noLegend && opts.series.length + (opts.bands || []).length >= 2) {
    legHost.appendChild(legend(
      (opts.bands || []).map(b => ({ label: b.label, color: b.color, kind: 'band' }))
        .concat(opts.series.map(s => ({ label: s.label, color: s.color })))
    ));
  }

  let state = null;

  function draw(W) {
    clear(svgHost);
    const wantEnd = opts.endLabels !== false && opts.series.length <= 4;
    /* the right margin has to fit the widest end-label that will actually be
     * drawn — a percentage of the width is not enough at narrow viewports, and
     * the overflow lands outside the SVG box where it is clipped */
    let endW = 0;
    if (wantEnd) {
      for (const s of opts.series) {
        for (let i = s.values.length - 1; i >= 0; i--) {
          const v = s.values[i];
          if (v === null || v === undefined || !isFinite(v)) continue;
          endW = Math.max(endW, (fmt(v, opts.yDp === undefined ? 1 : opts.yDp) + (opts.yUnit || '')).length * 6.3);
          break;
        }
      }
    }
    const M = { t: 14, r: wantEnd ? Math.min(150, Math.max(56, endW + 24)) : 16, b: 28, l: 46 };
    const w = Math.max(220, W), h = height;
    const pw = w - M.l - M.r, ph = h - M.t - M.b;

    const xs = opts.x;
    const x = linScale(xs[0], xs[xs.length - 1], M.l, M.l + pw);

    const pool = opts.series.map(s => s.values);
    for (const b of (opts.bands || [])) { pool.push(b.lo); pool.push(b.hi); }
    for (const b of (opts.overlayBars || [])) pool.push([b.lo, b.hi]);
    let [lo, hi] = extent(pool);
    if (opts.zeroLine && lo > 0) lo = 0;
    if (opts.zeroLine && hi < 0) hi = 0;
    [lo, hi] = padded(lo, hi);
    const y = linScale(lo, hi, M.t + ph, M.t);

    const svg = S('svg', { width: w, height: h, role: 'img', 'aria-label': opts.ariaLabel || 'line chart' });

    /* gridlines — solid hairlines, one step off surface */
    const yt = niceTicks(lo, hi, 5);
    for (const v of yt) {
      svg.appendChild(S('line', { x1: M.l, x2: M.l + pw, y1: y(v), y2: y(v), stroke: 'var(--grid)', 'stroke-width': 1 }));
      svg.appendChild(S('text', { x: M.l - 8, y: y(v) + 4, 'text-anchor': 'end', class: 'tick', fill: 'var(--text-muted)' },
        [document.createTextNode(fmt(v, opts.yDp === undefined ? 1 : opts.yDp))]));
    }
    /* zero rule slightly stronger than the grid; `zeroEmphasis` pushes it
     * further still, for a chart whose whole reading is "which side of zero" */
    if (lo < 0 && hi > 0) {
      svg.appendChild(S('line', {
        x1: M.l, x2: M.l + pw, y1: y(0), y2: y(0),
        stroke: opts.zeroEmphasis ? 'var(--text-secondary)' : 'var(--axis)',
        'stroke-width': opts.zeroEmphasis ? 1.5 : 1
      }));
    }
    /* x ticks — year boundaries by default, caller-supplied on a non-calendar axis */
    const xTickFmt = opts.xTickFmt || (k => mlabel(k, 'year'));
    for (const k of (opts.xTicks || monthTicks(xs[0], xs[xs.length - 1], pw))) {
      if (k < xs[0] || k > xs[xs.length - 1]) continue;
      svg.appendChild(S('text', { x: x(k), y: h - 8, 'text-anchor': 'middle', class: 'tick', fill: 'var(--text-muted)' },
        [document.createTextNode(xTickFmt(k))]));
    }
    /* baseline */
    svg.appendChild(S('line', { x1: M.l, x2: M.l + pw, y1: M.t + ph, y2: M.t + ph, stroke: 'var(--axis)', 'stroke-width': 1 }));

    /* annotations (event markers) behind the data */
    for (const a of (opts.annotations || [])) {
      if (a.x < xs[0] || a.x > xs[xs.length - 1]) continue;
      const px = x(a.x);
      svg.appendChild(S('line', { x1: px, x2: px, y1: M.t, y2: M.t + ph, stroke: 'var(--annot)', 'stroke-width': 1 }));
      const dot = S('circle', { cx: px, cy: M.t + 6, r: 5, fill: 'var(--annot-dot)', stroke: 'var(--surface-1)', 'stroke-width': 2, class: 'annot-dot', tabindex: 0, role: 'button', 'aria-label': a.title });
      const body = '<b>' + a.label + '</b><br>' + a.title;
      dot.addEventListener('mouseenter', e => showTip(body, e.clientX, e.clientY));
      dot.addEventListener('mousemove', e => showTip(body, e.clientX, e.clientY));
      dot.addEventListener('mouseleave', hideTip);
      dot.addEventListener('focus', () => { const r = dot.getBoundingClientRect(); showTip(body, r.left, r.bottom); });
      dot.addEventListener('blur', hideTip);
      svg.appendChild(dot);
    }

    /* uncertainty bands, drawn under the lines */
    for (const b of (opts.bands || [])) {
      let d = '', open = false, back = [];
      for (let i = 0; i < xs.length; i++) {
        const a = b.hi[i], c = b.lo[i];
        if (a === null || a === undefined || !isFinite(a)) {
          if (open) { d += back.reverse().join(' ') + ' Z '; back = []; open = false; }
          continue;
        }
        d += (open ? 'L' : 'M') + x(xs[i]) + ' ' + y(a) + ' ';
        back.push('L' + x(xs[i]) + ' ' + y(c));
        open = true;
      }
      if (open) d += back.reverse().join(' ') + ' Z ';
      svg.appendChild(S('path', { d: d, fill: b.color, 'fill-opacity': b.opacity === undefined ? 0.22 : b.opacity, stroke: 'none' }));
    }

    /* lines — nulls break the path */
    for (const s of opts.series) {
      let d = '', open = false;
      for (let i = 0; i < xs.length; i++) {
        const v = s.values[i];
        if (v === null || v === undefined || !isFinite(v)) { open = false; continue; }
        d += (open ? 'L' : 'M') + x(xs[i]) + ' ' + y(v) + ' ';
        open = true;
      }
      svg.appendChild(S('path', { d: d, fill: 'none', stroke: s.color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    }

    /* optional per-point overlay marks (P4 first prints: flagged vs not).
     * Drawn on top of the lines, 8px minimum, 2px surface ring. */
    for (const dm of (opts.overlayDots || [])) {
      if (dm.y === null || dm.y === undefined || !isFinite(dm.y)) continue;
      if (dm.x < xs[0] || dm.x > xs[xs.length - 1]) continue;
      const c = S('circle', {
        cx: x(dm.x), cy: y(dm.y), r: dm.r || 4,
        fill: dm.fill || 'none', stroke: dm.stroke || 'var(--surface-1)',
        'stroke-width': dm.strokeWidth === undefined ? 1.5 : dm.strokeWidth
      });
      if (dm.title) c.appendChild(S('title', null, [document.createTextNode(dm.title)]));
      svg.appendChild(c);
    }

    /* capped interval at a single x — an SE that is published for one point
     * only. A full band would be inventing the other months. */
    for (const b of (opts.overlayBars || [])) {
      if (!isFinite(b.lo) || !isFinite(b.hi)) continue;
      if (b.x < xs[0] || b.x > xs[xs.length - 1]) continue;
      const px = x(b.x), col = b.color || 'var(--text-secondary)', cap = 5;
      const g = S('g', { tabindex: b.title ? 0 : null, role: b.title ? 'button' : null, 'aria-label': b.title || null });
      g.appendChild(S('line', { x1: px, x2: px, y1: y(b.lo), y2: y(b.hi), stroke: col, 'stroke-width': 2, 'stroke-linecap': 'round' }));
      g.appendChild(S('line', { x1: px - cap, x2: px + cap, y1: y(b.hi), y2: y(b.hi), stroke: col, 'stroke-width': 2, 'stroke-linecap': 'round' }));
      g.appendChild(S('line', { x1: px - cap, x2: px + cap, y1: y(b.lo), y2: y(b.lo), stroke: col, 'stroke-width': 2, 'stroke-linecap': 'round' }));
      if (b.title) {
        g.addEventListener('mouseenter', e => showTip(b.title, e.clientX, e.clientY));
        g.addEventListener('mousemove', e => showTip(b.title, e.clientX, e.clientY));
        g.addEventListener('mouseleave', hideTip);
        g.addEventListener('focus', () => { const r = g.getBoundingClientRect(); showTip(b.title, r.left, r.top); });
        g.addEventListener('blur', hideTip);
      }
      svg.appendChild(g);
    }

    /* selective direct end-labels (text in ink, colour carried by the dot) */
    if (wantEnd) {
      const ends = [];
      for (const s of opts.series) {
        let li = -1;
        for (let i = xs.length - 1; i >= 0; i--) { const v = s.values[i]; if (v !== null && v !== undefined && isFinite(v)) { li = i; break; } }
        if (li < 0) continue;
        ends.push({ s: s, i: li, y: y(s.values[li]), v: s.values[li] });
      }
      ends.sort((a, b) => a.y - b.y);
      /* leader lines rather than stacked labels when ends converge */
      for (let i = 1; i < ends.length; i++) {
        if (ends[i].y - ends[i - 1].y < 15) ends[i].y = ends[i - 1].y + 15;
      }
      for (const e of ends) {
        const px = x(xs[e.i]), py = y(e.v);
        svg.appendChild(S('circle', { cx: px, cy: py, r: 4, fill: e.s.color, stroke: 'var(--surface-1)', 'stroke-width': 2 }));
        if (Math.abs(e.y - py) > 1.5) {
          svg.appendChild(S('path', { d: 'M' + (px + 5) + ' ' + py + ' L' + (px + 12) + ' ' + e.y, stroke: 'var(--axis)', 'stroke-width': 1, fill: 'none' }));
        }
        svg.appendChild(S('text', { x: px + 14, y: e.y + 4, class: 'endlab', fill: 'var(--text-secondary)' },
          [document.createTextNode(fmt(e.v, opts.yDp === undefined ? 1 : opts.yDp) + (opts.yUnit || ''))]));
      }
    }

    /* crosshair + hover/keyboard layer */
    const cross = S('line', { x1: 0, x2: 0, y1: M.t, y2: M.t + ph, stroke: 'var(--axis)', 'stroke-width': 1, opacity: 0 });
    svg.appendChild(cross);
    const dots = S('g', { opacity: 0 });
    svg.appendChild(dots);

    const hit = S('rect', {
      x: M.l, y: M.t, width: pw, height: ph, fill: 'transparent',
      tabindex: 0, role: 'application', 'aria-label': (opts.ariaLabel || 'chart') + ' — use arrow keys to step through months'
    });
    svg.appendChild(hit);

    let cur = xs.length - 1;
    function nearest(px) {
      const kx = x.invert(px);
      let best = 0, bd = Infinity;
      for (let i = 0; i < xs.length; i++) { const d2 = Math.abs(xs[i] - kx); if (d2 < bd) { bd = d2; best = i; } }
      return best;
    }
    function paint(i, cx, cy) {
      cur = i;
      const px = x(xs[i]);
      cross.setAttribute('x1', px); cross.setAttribute('x2', px); cross.setAttribute('opacity', 1);
      clear(dots); dots.setAttribute('opacity', 1);
      let rows = '';
      for (const s of opts.series) {
        const v = s.values[i];
        if (v === null || v === undefined || !isFinite(v)) { rows += '<tr><td><i class="k" style="background:' + s.color + '"></i>' + s.label + '</td><td>no data</td></tr>'; continue; }
        dots.appendChild(S('circle', { cx: px, cy: y(v), r: 4.5, fill: s.color, stroke: 'var(--surface-1)', 'stroke-width': 2 }));
        let extra = '';
        const b = (opts.bands || []).find(bb => bb.key === s.key);
        if (b && b.lo[i] !== null && isFinite(b.lo[i])) extra = ' <span class="se">±' + fmt((b.hi[i] - b.lo[i]) / 2, 3) + '</span>';
        rows += '<tr><td><i class="k" style="background:' + s.color + '"></i>' + s.label + '</td><td>' + fmt(v, opts.yDp === undefined ? 2 : opts.yDp) + (opts.yUnit || '') + extra + '</td></tr>';
      }
      const html = '<b>' + xLabel(xs[i]) + '</b><table class="tiptab">' + rows + '</table>';
      if (cx === undefined) { const r = hit.getBoundingClientRect(); cx = r.left + (px - M.l); cy = r.top + ph / 2; }
      showTip(html, cx, cy);
    }
    function off() { cross.setAttribute('opacity', 0); dots.setAttribute('opacity', 0); hideTip(); }

    hit.addEventListener('mousemove', e => {
      const r = svg.getBoundingClientRect();
      paint(nearest(e.clientX - r.left), e.clientX, e.clientY);
    });
    hit.addEventListener('mouseleave', off);
    hit.addEventListener('focus', () => paint(cur));
    hit.addEventListener('blur', off);
    hit.addEventListener('keydown', e => {
      if (e.key === 'ArrowRight') { paint(Math.min(xs.length - 1, cur + 1)); e.preventDefault(); }
      else if (e.key === 'ArrowLeft') { paint(Math.max(0, cur - 1)); e.preventDefault(); }
      else if (e.key === 'Home') { paint(0); e.preventDefault(); }
      else if (e.key === 'End') { paint(xs.length - 1); e.preventDefault(); }
      else if (e.key === 'Escape') { off(); }
    });

    svgHost.appendChild(svg);
    state = { x: x, y: y };
  }

  mountChart(svgHost, draw);
  return { redraw: () => draw(svgHost.clientWidth) };
}

/* =========================================================================
 * HORIZONTAL BAR CHART
 *   opts: { rows:[{label, values:[..], title?}], series:[{label,color}],
 *           diverging:false, unit, dp, barMax, height? }
 * Grouped when series.length > 1. Bars <= 24px, 4px rounded data-end,
 * 2px surface gap between neighbours.
 * ========================================================================= */
function barChart(container, opts) {
  const svgHost = H('div', { class: 'plot' });
  const legHost = H('div');
  container.appendChild(legHost);
  container.appendChild(svgHost);
  if (opts.series.length >= 2) legHost.appendChild(legend(opts.series.map(s => ({ label: s.label, color: s.color }))));

  function draw(W) {
    clear(svgHost);
    const w = Math.max(260, W);
    const labW = Math.min(240, Math.max(96, w * 0.34));
    const valW = 52;
    const M = { t: 6, r: valW + 8, b: 24, l: labW + 10 };
    const pw = w - M.l - M.r;

    const ns = opts.series.length;
    const barH = Math.min(opts.barMax || 18, 18);
    const gap = 2;                      /* the surface gap, not a stroke */
    const rowH = ns * barH + (ns - 1) * gap + 14;
    const ph = opts.rows.length * rowH;
    const h = M.t + ph + M.b;

    let vals = [];
    for (const r of opts.rows) vals = vals.concat(r.values.filter(v => v !== null && isFinite(v)));
    let lo = Math.min(0, Math.min.apply(null, vals.concat([0])));
    let hi = Math.max(0, Math.max.apply(null, vals.concat([0])));
    if (lo === hi) hi = lo + 1;
    const pad = (hi - lo) * 0.04;
    const x = linScale(lo - (lo < 0 ? pad : 0), hi + pad, M.l, M.l + pw);
    const x0 = x(0);

    const svg = S('svg', { width: w, height: h, role: 'img', 'aria-label': opts.ariaLabel || 'bar chart' });

    /* tick target follows the plot width — 4 ticks in a 180px plot puts the
     * numbers on top of each other */
    for (const v of niceTicks(lo, hi, Math.max(2, Math.min(4, Math.floor(pw / 76))))) {
      svg.appendChild(S('line', { x1: x(v), x2: x(v), y1: M.t, y2: M.t + ph, stroke: v === 0 ? 'var(--axis)' : 'var(--grid)', 'stroke-width': 1 }));
      svg.appendChild(S('text', { x: x(v), y: h - 8, 'text-anchor': 'middle', class: 'tick', fill: 'var(--text-muted)' }, [document.createTextNode(fmt(v, opts.tickDp === undefined ? 1 : opts.tickDp))]));
    }

    opts.rows.forEach((r, ri) => {
      const top = M.t + ri * rowH + 7;
      const cy = top + (ns * barH + (ns - 1) * gap) / 2;
      const lab = S('text', { x: labW, y: cy + 4, 'text-anchor': 'end', class: 'rowlab', fill: 'var(--text-secondary)' },
        [document.createTextNode(fitLabel(r.label, labW - 6))]);
      lab.appendChild(S('title', null, [document.createTextNode(r.title || r.label)]));
      svg.appendChild(lab);

      r.values.forEach((v, si) => {
        if (v === null || !isFinite(v)) return;
        const yTop = top + si * (barH + gap);
        const col = opts.diverging
          ? (v >= 0 ? 'var(--div-pos)' : 'var(--div-neg)')
          : opts.series[si].color;
        const xa = Math.min(x0, x(v)), xb = Math.max(x0, x(v));
        const bw = Math.max(1, xb - xa);
        /* 4px rounded data-end, square at the baseline */
        const rr = Math.min(4, bw);
        const d = v >= 0
          ? 'M' + xa + ' ' + yTop + ' H' + (xa + bw - rr) + ' a' + rr + ' ' + rr + ' 0 0 1 ' + rr + ' ' + rr + ' V' + (yTop + barH - rr) + ' a' + rr + ' ' + rr + ' 0 0 1 ' + (-rr) + ' ' + rr + ' H' + xa + ' Z'
          : 'M' + xb + ' ' + yTop + ' H' + (xa + rr) + ' a' + rr + ' ' + rr + ' 0 0 0 ' + (-rr) + ' ' + rr + ' V' + (yTop + barH - rr) + ' a' + rr + ' ' + rr + ' 0 0 0 ' + rr + ' ' + rr + ' H' + xb + ' Z';
        const bar = S('path', { d: d, fill: col, tabindex: 0, role: 'button' });
        /* `rowTip` lets a single-series chart put the numbers the bar was
         * derived from into the tooltip without drawing them as extra bars */
        const body = opts.rowTip ? opts.rowTip(r) :
          '<b>' + (r.title || r.label) + '</b><table class="tiptab">' +
          r.values.map((vv, k) => vv === null || !isFinite(vv) ? '' :
            '<tr><td><i class="k" style="background:' + (opts.diverging ? (vv >= 0 ? 'var(--div-pos)' : 'var(--div-neg)') : opts.series[k].color) + '"></i>' +
            opts.series[k].label + '</td><td>' + fmt(vv, opts.dp === undefined ? 2 : opts.dp) + (opts.unit || '') + '</td></tr>').join('') + '</table>';
        bar.setAttribute('aria-label', (r.title || r.label) + ': ' + opts.series[si].label + ' ' + fmt(v, opts.dp) + (opts.unit || ''));
        bar.addEventListener('mouseenter', e => showTip(body, e.clientX, e.clientY));
        bar.addEventListener('mousemove', e => showTip(body, e.clientX, e.clientY));
        bar.addEventListener('mouseleave', hideTip);
        bar.addEventListener('focus', () => { const q = bar.getBoundingClientRect(); showTip(body, q.right, q.top); });
        bar.addEventListener('blur', hideTip);
        svg.appendChild(bar);

        /* Value at the tip, outside the bar — never clipped. Only for a single
         * series: on a grouped chart a number per bar is the "value on every
         * point" anti-pattern, so the axis, legend, tooltip and table carry it. */
        if (ns === 1) {
          /* Value at the tip, outside the bar. On a diverging chart the tip of
           * a negative bar points back at the row-label gutter, so if the
           * number would not clear the plot edge it flips to the inner end
           * instead of colliding with the label. */
          const txt = fmt(v, opts.dp === undefined ? 2 : opts.dp);
          const estW = txt.length * 6.3;
          let tx, anchor;
          if (v >= 0) {
            if (xb + 6 + estW <= w - 2) { tx = xb + 6; anchor = 'start'; }
            else { tx = xa - 6; anchor = 'end'; }
          } else {
            if (xa - 6 - estW >= M.l + 2) { tx = xa - 6; anchor = 'end'; }
            else { tx = xb + 6; anchor = 'start'; }
          }
          svg.appendChild(S('text', {
            x: tx, y: yTop + barH - 4,
            'text-anchor': anchor, class: 'endlab', fill: 'var(--text-secondary)'
          }, [document.createTextNode(txt)]));
        }
      });
    });

    svgHost.appendChild(svg);
  }

  mountChart(svgHost, draw);
}

/* =========================================================================
 * RIDGELINE — weight-scaled histograms of the item cross-section, one row
 * per month, stacked with overlap. Single hue (sequential/one-series).
 * ========================================================================= */
function ridgeline(container, months, opts) {
  const svgHost = H('div', { class: 'plot' });
  container.appendChild(svgHost);
  const NB = opts.bins || 56;

  /* Shared x-domain: the weighted 5th..95th percentile of every shown month.
   * Wider thresholds are dominated by a handful of tiny-weight items (fuel oil
   * at +39%, eggs at -26%) that stretch the axis without carrying any visible
   * area — the tails past this window are clamped into the end bins. */
  const Q = opts.tailQ || 0.05;
  let lo = Infinity, hi = -Infinity;
  for (const m of months) {
    const idx = m.yoy.map((v, i) => i).filter(i => isFinite(m.yoy[i]));
    idx.sort((a, b) => m.yoy[a] - m.yoy[b]);
    const tot = idx.reduce((s, i) => s + m.w[i], 0);
    let c = 0, pLo = null, pHi = null;
    for (const i of idx) {
      c += m.w[i];
      if (pLo === null && c >= tot * Q) pLo = m.yoy[i];
      if (pHi === null && c >= tot * (1 - Q)) { pHi = m.yoy[i]; break; }
    }
    if (pLo !== null) lo = Math.min(lo, pLo);
    if (pHi !== null) hi = Math.max(hi, pHi);
  }
  lo = Math.floor(lo) - 1; hi = Math.ceil(hi) + 1;

  function draw(W) {
    clear(svgHost);
    const w = Math.max(260, W);
    const labW = 62;
    const M = { t: 10, r: 14, b: 26, l: labW };
    const pw = w - M.l - M.r;
    const rowH = Math.max(13, Math.min(20, 460 / months.length));
    const ridgeH = rowH * 2.6;                     /* overlap */
    const ph = rowH * months.length + ridgeH;
    const h = M.t + ph + M.b;
    const x = linScale(lo, hi, M.l, M.l + pw);

    const svg = S('svg', { width: w, height: h, role: 'img', 'aria-label': opts.ariaLabel || 'ridgeline' });

    for (const v of niceTicks(lo, hi, 6)) {
      svg.appendChild(S('line', { x1: x(v), x2: x(v), y1: M.t, y2: M.t + ph, stroke: v === 0 ? 'var(--axis)' : 'var(--grid)', 'stroke-width': 1 }));
      svg.appendChild(S('text', { x: x(v), y: h - 8, 'text-anchor': 'middle', class: 'tick', fill: 'var(--text-muted)' }, [document.createTextNode(v + '%')]));
    }

    /* bin once, find a common vertical scale */
    const bw = (hi - lo) / NB;
    const dens = months.map(m => {
      const b = new Array(NB).fill(0);
      for (let i = 0; i < m.yoy.length; i++) {
        const v = m.yoy[i], ww = m.w[i];
        if (!isFinite(v) || !isFinite(ww)) continue;
        let k = Math.floor((v - lo) / bw);
        if (k < 0) k = 0; if (k >= NB) k = NB - 1;   /* extremes clamp into the end bins */
        b[k] += ww;
      }
      return b;
    });
    let peak = 0;
    for (const b of dens) for (const v of b) if (v > peak) peak = v;

    /* newest at top */
    months.forEach((m, mi) => {
      const base = M.t + ridgeH + mi * rowH;
      const b = dens[mi];
      let d = 'M' + x(lo) + ' ' + base + ' ';
      for (let k = 0; k < NB; k++) {
        const cx = x(lo + (k + 0.5) * bw);
        d += 'L' + cx + ' ' + (base - (b[k] / peak) * ridgeH) + ' ';
      }
      d += 'L' + x(hi) + ' ' + base + ' Z';
      svg.appendChild(S('path', { d: d, fill: 'var(--series-1)', 'fill-opacity': 0.13, stroke: 'var(--series-1)', 'stroke-width': 1.5, 'stroke-linejoin': 'round' }));

      svg.appendChild(S('text', { x: labW - 8, y: base - 1, 'text-anchor': 'end', class: 'tick', fill: 'var(--text-muted)' },
        [document.createTextNode(mlabel(mkey(m.ym), 'short'))]));

      /* hover band for the whole row */
      const hit = S('rect', { x: M.l, y: base - rowH, width: pw, height: rowH, fill: 'transparent', tabindex: 0, role: 'button', 'aria-label': ymLabel(m.ym) + ' distribution' });
      const st = m.stats;
      const body = '<b>' + ymLabel(m.ym) + '</b><table class="tiptab">' +
        '<tr><td>Weighted median</td><td>' + fmt(st.median, 2) + '%</td></tr>' +
        '<tr><td>10th pct</td><td>' + fmt(st.p10, 2) + '%</td></tr>' +
        '<tr><td>90th pct</td><td>' + fmt(st.p90, 2) + '%</td></tr>' +
        '<tr><td>Share falling</td><td>' + fmt(st.lt0, 1) + '%</td></tr>' +
        '<tr><td>Items</td><td>' + m.yoy.length + '</td></tr></table>';
      hit.addEventListener('mouseenter', e => showTip(body, e.clientX, e.clientY));
      hit.addEventListener('mousemove', e => showTip(body, e.clientX, e.clientY));
      hit.addEventListener('mouseleave', hideTip);
      hit.addEventListener('focus', () => { const r = hit.getBoundingClientRect(); showTip(body, r.left + 40, r.top); });
      hit.addEventListener('blur', hideTip);
      svg.appendChild(hit);
    });

    svgHost.appendChild(svg);
  }
  mountChart(svgHost, draw);
}

/* =========================================================================
 * BINNED VALUE SCALES
 * Fills that encode a *value* rather than an identity. Both ramps live in
 * styles.css as custom properties, so light/dark swaps without a redraw.
 *   seqColor  — sequential, one hue, 5 bins (magnitude: half-life)
 *   divColor  — diverging, two hues + neutral midpoint, 11 bins (polarity)
 * `cuts` are the upper edges of the bins; for divColor they are the absolute
 * values, applied symmetrically, so the scale is centred on zero by
 * construction rather than by choosing a midpoint from the data.
 * ========================================================================= */
function seqColor(v, cuts) {
  if (v === null || v === undefined || !isFinite(v)) return 'var(--null-cell)';
  let k = 0;
  while (k < cuts.length && v >= cuts[k]) k++;
  return 'var(--seq-' + Math.min(5, k + 1) + ')';
}
function divColor(v, cuts) {
  if (v === null || v === undefined || !isFinite(v)) return 'var(--null-cell)';
  const a = Math.abs(v);
  let k = 0;
  while (k < cuts.length && a >= cuts[k]) k++;
  if (k === 0) return 'var(--heat-0)';
  return 'var(--heat-' + (v > 0 ? 'p' : 'n') + Math.min(5, k) + ')';
}

/* legend for a binned scale — the identity channel for a value fill */
function scaleLegend(title, entries, extra) {
  const box = H('div', { class: 'scalelegend' });
  if (title) box.appendChild(H('span', { class: 'sl-title', text: title }));
  for (const e of entries) {
    box.appendChild(H('span', { class: 'sl-item' }, [
      H('span', { class: 'sl-sw', style: 'background:' + e.color }),
      H('span', { text: e.label })
    ]));
  }
  for (const e of (extra || [])) {
    box.appendChild(H('span', { class: 'sl-item' }, [
      H('span', { class: 'sl-sw', style: 'background:' + e.color }),
      H('span', { text: e.label })
    ]));
  }
  return box;
}
/* the standard 11-bin diverging legend for a set of absolute cuts */
function divLegendEntries(cuts, unit, dp) {
  const f = v => fmt(v, dp === undefined ? 2 : dp);
  const out = [];
  for (let i = cuts.length; i >= 1; i--) {
    out.push({ color: 'var(--heat-n' + i + ')', label: (i === cuts.length ? '≤ −' + f(cuts[i - 1]) : '−' + f(cuts[i - 1])) + (i === cuts.length ? unit : '') });
  }
  out.push({ color: 'var(--heat-0)', label: '±' + f(cuts[0]) });
  for (let i = 1; i <= cuts.length; i++) {
    out.push({ color: 'var(--heat-p' + i + ')', label: (i === cuts.length ? '≥ +' + f(cuts[i - 1]) + unit : '+' + f(cuts[i - 1])) });
  }
  return out;
}

/* a 45° hatch, used to mark a facet whose numbers are not comparable with the
 * one next to it (P3's nsa12 items). Texture, not colour, carries it. */
let _patId = 0;
function hatchDefs(svg, opacity) {
  const id = 'hatch' + (++_patId);
  const p = S('pattern', { id: id, width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' });
  p.appendChild(S('rect', { width: 6, height: 6, fill: 'none' }));
  p.appendChild(S('line', { x1: 0, y1: 0, x2: 0, y2: 6, stroke: 'var(--hatch)', 'stroke-width': 1.6, opacity: opacity === undefined ? 0.55 : opacity }));
  svg.appendChild(S('defs', null, [p]));
  return 'url(#' + id + ')';
}

/* =========================================================================
 * TREEMAP — area = weight, fill = a binned value scale.
 *   opts: { items:[{label, value, fill, title, rows:[[k,v]]}],
 *           height, hatch, ariaLabel }
 * Squarified (Bruls/Huizing/van Wijk): rectangles stay close to square, so
 * area stays readable. Deterministic — same input, same picture.
 * ========================================================================= */
function treemap(container, opts) {
  const svgHost = H('div', { class: 'plot' });
  container.appendChild(svgHost);

  function layout(items, x0, y0, w, h) {
    /* returns [{item, x, y, w, h}] */
    const out = [];
    const total = items.reduce((s, i) => s + i.value, 0);
    if (total <= 0) return out;
    let vals = items.map(i => ({ it: i, v: i.value }));
    let X = x0, Y = y0, W = w, Hh = h;
    let scale = (W * Hh) / total;

    const worst = (row, len) => {
      const s = row.reduce((a, b) => a + b.v, 0) * scale;
      const mx = Math.max.apply(null, row.map(r => r.v)) * scale;
      const mn = Math.min.apply(null, row.map(r => r.v)) * scale;
      if (s === 0 || len === 0) return Infinity;
      return Math.max((len * len * mx) / (s * s), (s * s) / (len * len * mn));
    };
    const place = row => {
      const s = row.reduce((a, b) => a + b.v, 0) * scale;
      const horiz = W >= Hh;
      const len = horiz ? Hh : W;
      const thick = len ? s / len : 0;
      let off = 0;
      for (const r of row) {
        const frac = s ? (r.v * scale) / s : 0;
        const side = frac * len;
        if (horiz) out.push({ item: r.it, x: X, y: Y + off, w: thick, h: side });
        else out.push({ item: r.it, x: X + off, y: Y, w: side, h: thick });
        off += side;
      }
      if (horiz) { X += thick; W -= thick; } else { Y += thick; Hh -= thick; }
    };

    let row = [];
    while (vals.length) {
      const c = vals[0];
      const len = Math.min(W, Hh);
      if (!row.length || worst(row.concat([c]), len) <= worst(row, len)) {
        row.push(c); vals.shift();
      } else {
        place(row); row = [];
        scale = (W * Hh) / vals.reduce((s, i) => s + i.v, 0);
        if (!isFinite(scale)) break;
      }
    }
    if (row.length) place(row);
    return out;
  }

  function draw(W) {
    clear(svgHost);
    const w = Math.max(300, W), h = opts.height || 300;
    const svg = S('svg', { width: w, height: h, role: 'img', 'aria-label': opts.ariaLabel || 'treemap' });
    const hatchFill = opts.hatch ? hatchDefs(svg) : null;

    const items = opts.items.filter(i => i.value > 0).slice().sort((a, b) => b.value - a.value);
    const cells = layout(items, 0, 0, w, h);

    for (const c of cells) {
      const g = S('g');
      const cw = Math.max(0, c.w - 1.6), ch = Math.max(0, c.h - 1.6);   /* the 2px surface gap */
      g.appendChild(S('rect', { x: c.x + 0.8, y: c.y + 0.8, width: cw, height: ch, rx: Math.min(2, cw / 2, ch / 2), fill: c.item.fill }));
      if (hatchFill) g.appendChild(S('rect', { x: c.x + 0.8, y: c.y + 0.8, width: cw, height: ch, rx: Math.min(2, cw / 2, ch / 2), fill: hatchFill }));

      /* label only where it genuinely fits — never a clipped word */
      if (cw > 54 && ch > 26) {
        const room = cw - 10;
        g.appendChild(S('text', { x: c.x + 6, y: c.y + 16, class: 'tmlab', fill: c.item.ink || 'var(--text-primary)' },
          [document.createTextNode(fitLabel(c.item.label, room, 6.0))]));
        /* the sub-line is tabular-nums and needs the same fit test — an
         * un-truncated one spills into the neighbouring cell */
        if (ch > 40 && c.item.sub) {
          /* a truncated number is a wrong number, so the sub-line is dropped
           * whole rather than ellipsised; the tooltip and table still carry it */
          const sub = c.item.sub.length * 5.6 <= room ? c.item.sub : '';
          if (sub) {
            g.appendChild(S('text', { x: c.x + 6, y: c.y + 30, class: 'tmsub', fill: c.item.ink || 'var(--text-primary)' },
              [document.createTextNode(sub)]));
          }
        }
      }
      const hit = S('rect', {
        x: c.x, y: c.y, width: c.w, height: c.h, fill: 'transparent',
        tabindex: 0, role: 'button', 'aria-label': c.item.title || c.item.label
      });
      const body = '<b>' + (c.item.title || c.item.label) + '</b><table class="tiptab">' +
        (c.item.rows || []).map(r => '<tr><td>' + r[0] + '</td><td>' + r[1] + '</td></tr>').join('') + '</table>';
      hit.addEventListener('mouseenter', e => showTip(body, e.clientX, e.clientY));
      hit.addEventListener('mousemove', e => showTip(body, e.clientX, e.clientY));
      hit.addEventListener('mouseleave', hideTip);
      hit.addEventListener('focus', () => { const r = hit.getBoundingClientRect(); showTip(body, r.left + r.width / 2, r.top); });
      hit.addEventListener('blur', hideTip);
      hit.addEventListener('keydown', e => { if (e.key === 'Escape') { hideTip(); hit.blur(); } });
      g.appendChild(hit);
      svg.appendChild(g);
    }
    svgHost.appendChild(svg);
  }
  mountChart(svgHost, draw);
}

/* =========================================================================
 * HEATMAP — rows x columns of a value fill.
 *   opts: { cols:[label], rows:[{label,title,group}], z:[[v]],
 *           fill(v), tip(ri,ci,v), colTick(ci)->string|null,
 *           colBand:[{ci,color,label}], rowH, labW, ariaLabel }
 * One hit rect per row (not per cell): 29 listeners instead of 3,480, and the
 * row is one arrow-key track for the keyboard equivalent.
 * ========================================================================= */
function heatmap(container, opts) {
  const svgHost = H('div', { class: 'plot' });
  container.appendChild(svgHost);

  function draw(W) {
    clear(svgHost);
    const rowH = opts.rowH || 15;
    const labW = opts.labW || 176;
    const bandH = opts.colBand ? 12 : 0;
    const M = { t: 6, r: 10, b: 22 + bandH, l: labW };
    const w = Math.max(560, W);
    const pw = w - M.l - M.r;
    const nC = opts.cols.length, nR = opts.rows.length;
    const cw = pw / nC;
    const ph = nR * rowH;
    const h = M.t + ph + M.b;

    const svg = S('svg', { width: w, height: h, role: 'img', 'aria-label': opts.ariaLabel || 'heatmap' });

    /* cells */
    opts.rows.forEach((r, ri) => {
      const yTop = M.t + ri * rowH;
      for (let ci = 0; ci < nC; ci++) {
        const v = opts.z[ri][ci];
        svg.appendChild(S('rect', {
          x: M.l + ci * cw, y: yTop, width: Math.max(0.5, cw - 0.4), height: rowH - 1,
          fill: opts.fill(v)
        }));
      }
      /* row label — group changes get a hairline above */
      if (ri > 0 && opts.rows[ri - 1].group !== r.group) {
        svg.appendChild(S('line', { x1: 4, x2: M.l + pw, y1: yTop - 0.5, y2: yTop - 0.5, stroke: 'var(--axis)', 'stroke-width': 1 }));
      }
      const t = S('text', { x: labW - 8, y: yTop + rowH - 4, 'text-anchor': 'end', class: 'rowlab', fill: 'var(--text-secondary)' },
        [document.createTextNode(r.label)]);
      t.appendChild(S('title', null, [document.createTextNode(r.title || r.label)]));
      svg.appendChild(t);
    });

    /* column ticks */
    for (let ci = 0; ci < nC; ci++) {
      const lab = opts.colTick ? opts.colTick(ci) : null;
      if (!lab) continue;
      svg.appendChild(S('line', { x1: M.l + ci * cw, x2: M.l + ci * cw, y1: M.t + ph, y2: M.t + ph + 4, stroke: 'var(--axis)', 'stroke-width': 1 }));
      svg.appendChild(S('text', { x: M.l + ci * cw, y: M.t + ph + 15, 'text-anchor': 'middle', class: 'tick', fill: 'var(--text-muted)' },
        [document.createTextNode(lab)]));
    }

    /* publication-stage band under the month axis */
    if (opts.colBand) {
      const by = M.t + ph + 22;
      for (const b of opts.colBand) {
        svg.appendChild(S('rect', { x: M.l + b.ci * cw, y: by, width: Math.max(1, b.n * cw - 0.4), height: 7, fill: b.color, rx: 2 }));
      }
      svg.appendChild(S('text', { x: labW - 8, y: by + 7, 'text-anchor': 'end', class: 'tick', fill: 'var(--text-muted)' },
        [document.createTextNode('stage')]));
    }

    /* one hit strip per row */
    opts.rows.forEach((r, ri) => {
      const yTop = M.t + ri * rowH;
      const hit = S('rect', {
        x: M.l, y: yTop, width: pw, height: rowH, fill: 'transparent',
        tabindex: 0, role: 'application',
        'aria-label': (r.title || r.label) + ' — use arrow keys to step through months'
      });
      let cur = nC - 1;
      const mark = S('rect', { x: 0, y: yTop, width: cw, height: rowH - 1, fill: 'none', stroke: 'var(--text-primary)', 'stroke-width': 1.5, opacity: 0 });
      const paint = (ci, cx, cy) => {
        cur = ci;
        mark.setAttribute('x', M.l + ci * cw); mark.setAttribute('opacity', 1);
        if (cx === undefined) { const q = hit.getBoundingClientRect(); cx = q.left + ci * cw + cw / 2; cy = q.top; }
        showTip(opts.tip(ri, ci, opts.z[ri][ci]), cx, cy);
      };
      hit.addEventListener('mousemove', e => {
        const q = svg.getBoundingClientRect();
        let ci = Math.floor((e.clientX - q.left - M.l) / cw);
        ci = Math.max(0, Math.min(nC - 1, ci));
        paint(ci, e.clientX, e.clientY);
      });
      hit.addEventListener('mouseleave', () => { mark.setAttribute('opacity', 0); hideTip(); });
      hit.addEventListener('focus', () => paint(cur));
      hit.addEventListener('blur', () => { mark.setAttribute('opacity', 0); hideTip(); });
      hit.addEventListener('keydown', e => {
        if (e.key === 'ArrowRight') { paint(Math.min(nC - 1, cur + 1)); e.preventDefault(); }
        else if (e.key === 'ArrowLeft') { paint(Math.max(0, cur - 1)); e.preventDefault(); }
        else if (e.key === 'Home') { paint(0); e.preventDefault(); }
        else if (e.key === 'End') { paint(nC - 1); e.preventDefault(); }
        else if (e.key === 'Escape') { mark.setAttribute('opacity', 0); hideTip(); hit.blur(); }
      });
      svg.appendChild(mark);
      svg.appendChild(hit);
    });

    svgHost.appendChild(svg);
  }
  mountChart(svgHost, draw);
}

/* =========================================================================
 * FAN CHART — every vintage of the same series, latest in ink.
 *   opts: { x:[mkeys], lines:[[v]], labels:[vintage date], height,
 *           yUnit, yDp, ariaLabel }
 * A single hue at low opacity for the history (they are the same measurement,
 * not different series, so they must not be separate categorical colours) and
 * the current vintage at full weight on top.
 * ========================================================================= */
function fanChart(container, opts) {
  const svgHost = H('div', { class: 'plot' });
  const legHost = H('div');
  container.appendChild(legHost);
  container.appendChild(svgHost);
  legHost.appendChild(legend([
    { label: 'Earlier vintages (' + (opts.lines.length - 1) + ')', color: 'var(--series-1)', kind: 'band' },
    { label: 'Latest vintage — ' + opts.labels[opts.labels.length - 1], color: 'var(--series-1)' },
    { label: 'First print of each month', color: 'var(--series-2)' }
  ]));

  function draw(W) {
    clear(svgHost);
    const height = opts.height || 320;
    const M = { t: 12, r: 16, b: 28, l: 46 };
    const w = Math.max(280, W), h = height;
    const pw = w - M.l - M.r, ph = h - M.t - M.b;
    const xs = opts.x;
    const x = linScale(xs[0], xs[xs.length - 1], M.l, M.l + pw);
    let [lo, hi] = extent(opts.lines);
    [lo, hi] = padded(lo, hi);
    const y = linScale(lo, hi, M.t + ph, M.t);

    const svg = S('svg', { width: w, height: h, role: 'img', 'aria-label': opts.ariaLabel || 'vintage fan' });

    for (const v of niceTicks(lo, hi, 5)) {
      svg.appendChild(S('line', { x1: M.l, x2: M.l + pw, y1: y(v), y2: y(v), stroke: 'var(--grid)', 'stroke-width': 1 }));
      svg.appendChild(S('text', { x: M.l - 8, y: y(v) + 4, 'text-anchor': 'end', class: 'tick', fill: 'var(--text-muted)' },
        [document.createTextNode(fmt(v, opts.yDp === undefined ? 1 : opts.yDp))]));
    }
    if (lo < 0 && hi > 0) svg.appendChild(S('line', { x1: M.l, x2: M.l + pw, y1: y(0), y2: y(0), stroke: 'var(--axis)', 'stroke-width': 1 }));
    for (const k of monthTicks(xs[0], xs[xs.length - 1], pw)) {
      svg.appendChild(S('text', { x: x(k), y: h - 8, 'text-anchor': 'middle', class: 'tick', fill: 'var(--text-muted)' },
        [document.createTextNode(mlabel(k, 'year'))]));
    }
    svg.appendChild(S('line', { x1: M.l, x2: M.l + pw, y1: M.t + ph, y2: M.t + ph, stroke: 'var(--axis)', 'stroke-width': 1 }));

    const path = vals => {
      let d = '', open = false;
      for (let i = 0; i < xs.length; i++) {
        const v = vals[i];
        if (v === null || v === undefined || !isFinite(v)) { open = false; continue; }
        d += (open ? 'L' : 'M') + x(xs[i]) + ' ' + y(v) + ' ';
        open = true;
      }
      return d;
    };
    for (let i = 0; i < opts.lines.length - 1; i++) {
      svg.appendChild(S('path', { d: path(opts.lines[i]), fill: 'none', stroke: 'var(--series-1)', 'stroke-opacity': 0.24, 'stroke-width': 1, 'stroke-linejoin': 'round' }));
    }
    /* the first print of each obs month — the diagonal of the fan */
    if (opts.firstPrint) {
      svg.appendChild(S('path', { d: path(opts.firstPrint), fill: 'none', stroke: 'var(--series-2)', 'stroke-width': 2, 'stroke-dasharray': '4 3', 'stroke-linejoin': 'round' }));
    }
    svg.appendChild(S('path', { d: path(opts.lines[opts.lines.length - 1]), fill: 'none', stroke: 'var(--series-1)', 'stroke-width': 2.5, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));

    /* crosshair + tooltip: the spread across vintages at that month */
    const cross = S('line', { x1: 0, x2: 0, y1: M.t, y2: M.t + ph, stroke: 'var(--axis)', 'stroke-width': 1, opacity: 0 });
    svg.appendChild(cross);
    const hit = S('rect', { x: M.l, y: M.t, width: pw, height: ph, fill: 'transparent', tabindex: 0, role: 'application', 'aria-label': (opts.ariaLabel || 'fan') + ' — arrow keys step through months' });
    svg.appendChild(hit);
    let cur = xs.length - 1;
    function paint(i, cx, cy) {
      cur = i;
      cross.setAttribute('x1', x(xs[i])); cross.setAttribute('x2', x(xs[i])); cross.setAttribute('opacity', 1);
      const vals = opts.lines.map(l => l[i]).filter(v => v !== null && v !== undefined && isFinite(v));
      const latest = opts.lines[opts.lines.length - 1][i];
      const first = opts.firstPrint ? opts.firstPrint[i] : null;
      const dp = opts.yDp === undefined ? 2 : opts.yDp;
      let rows = '<tr><td>First print</td><td>' + fmt(first, dp) + (opts.yUnit || '') + '</td></tr>' +
        '<tr><td>Latest vintage</td><td>' + fmt(latest, dp) + (opts.yUnit || '') + '</td></tr>';
      if (first != null && latest != null && isFinite(first) && isFinite(latest)) {
        rows += '<tr><td>Revision</td><td>' + fmtSigned(latest - first, dp) + ' pp</td></tr>';
      }
      if (vals.length) {
        rows += '<tr><td>Range across ' + vals.length + ' vintages</td><td>' +
          fmt(Math.min.apply(null, vals), dp) + ' … ' + fmt(Math.max.apply(null, vals), dp) + '</td></tr>';
      }
      const html = '<b>' + mlabel(xs[i]) + '</b><table class="tiptab">' + rows + '</table>';
      if (cx === undefined) { const r = hit.getBoundingClientRect(); cx = r.left + (x(xs[i]) - M.l); cy = r.top + ph / 2; }
      showTip(html, cx, cy);
    }
    hit.addEventListener('mousemove', e => {
      const r = svg.getBoundingClientRect();
      const kx = x.invert(e.clientX - r.left);
      let best = 0, bd = Infinity;
      for (let i = 0; i < xs.length; i++) { const d2 = Math.abs(xs[i] - kx); if (d2 < bd) { bd = d2; best = i; } }
      paint(best, e.clientX, e.clientY);
    });
    hit.addEventListener('mouseleave', () => { cross.setAttribute('opacity', 0); hideTip(); });
    hit.addEventListener('focus', () => paint(cur));
    hit.addEventListener('blur', () => { cross.setAttribute('opacity', 0); hideTip(); });
    hit.addEventListener('keydown', e => {
      if (e.key === 'ArrowRight') { paint(Math.min(xs.length - 1, cur + 1)); e.preventDefault(); }
      else if (e.key === 'ArrowLeft') { paint(Math.max(0, cur - 1)); e.preventDefault(); }
      else if (e.key === 'Home') { paint(0); e.preventDefault(); }
      else if (e.key === 'End') { paint(xs.length - 1); e.preventDefault(); }
      else if (e.key === 'Escape') { cross.setAttribute('opacity', 0); hideTip(); }
    });

    svgHost.appendChild(svg);
  }
  mountChart(svgHost, draw);
}

/* =========================================================================
 * NETWORK — deterministic radial layout, grouped by major group.
 *   opts: { nodes:[{code,name,group,groupName,weight,color,deg}],
 *           edges:[{src,dst,lag,rho,...}], cascade:{code:{l1,l2}},
 *           groupOrder:[code], groupName:{}, edgeTip(e), nodeTip(n),
 *           height, ariaLabel }
 * NOT force-directed: nodes are placed on a circle, ordered by major group and
 * then by weight descending, so the picture is byte-identical on every render
 * and on every machine. Group identity is carried by *position* (a contiguous
 * arc with its own label) first and colour second, which is what lets eight
 * group hues coexist in an all-pairs form.
 * Edges are quadratic Béziers bent toward the centre; width = |rho|, colour =
 * sign of rho, arrowhead at the follower.
 * ========================================================================= */
function networkChart(container, opts) {
  const svgHost = H('div', { class: 'plot' });
  container.appendChild(svgHost);
  let selected = null;

  /* group -> categorical slot, fixed once, so a group keeps its colour when
   * the variant toggle changes the edge set */
  const SLOT = {};
  opts.groupOrder.forEach((g, i) => { SLOT[g] = i + 1; });

  function draw(W) {
    clear(svgHost);
    const w = Math.max(560, W);
    /* Radial labels stick out in *every* direction, so the ring has to leave
     * the same room vertically as horizontally — otherwise the labels at the
     * top and bottom of the circle run off the SVG box and get clipped. */
    const LAB_CHARS = 22;
    const labPx = LAB_CHARS * 5.6 + 12;
    const maxH = opts.maxHeight || 760;
    const R = Math.max(110, Math.min(w / 2, maxH / 2) - labPx - 8);
    const h = Math.min(maxH, 2 * (R + labPx) + 16);
    const cx = w / 2, cy = h / 2;

    /* deterministic order: group order, then weight descending, then code */
    const byGroup = {};
    for (const n of opts.nodes) (byGroup[n.group] = byGroup[n.group] || []).push(n);
    const order = [];
    const sectors = [];
    for (const g of opts.groupOrder) {
      const list = (byGroup[g] || []).slice().sort((a, b) =>
        (b.weight - a.weight) || (a.code < b.code ? -1 : 1));
      if (!list.length) continue;
      sectors.push({ group: g, from: order.length, n: list.length, slot: SLOT[g] });
      for (const n of list) order.push(n);
    }
    const N = order.length;
    const GAP = 0.035;                       /* radians of blank between groups */
    const usable = 2 * Math.PI - GAP * sectors.length;
    const pos = {};
    let ang = -Math.PI / 2 + GAP / 2;
    for (const s of sectors) {
      s.a0 = ang;
      for (let i = 0; i < s.n; i++) {
        const n = order[s.from + i];
        const a = ang + (i + 0.5) * (usable / N);
        pos[n.code] = { a: a, x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
      }
      ang += s.n * (usable / N);
      s.a1 = ang;
      ang += GAP;
    }

    const maxW = Math.max.apply(null, opts.nodes.map(n => n.weight || 0)) || 1;
    const rad = n => 2.4 + 9 * Math.sqrt((n.weight || 0) / maxW);

    const svg = S('svg', { width: w, height: h, role: 'img', 'aria-label': opts.ariaLabel || 'network' });

    /* group arcs + labels, outside the ring */
    for (const s of sectors) {
      const rr = R + 30;
      const a0 = s.a0, a1 = s.a1;
      const large = (a1 - a0) > Math.PI ? 1 : 0;
      svg.appendChild(S('path', {
        d: 'M' + (cx + rr * Math.cos(a0)) + ' ' + (cy + rr * Math.sin(a0)) +
           ' A' + rr + ' ' + rr + ' 0 ' + large + ' 1 ' + (cx + rr * Math.cos(a1)) + ' ' + (cy + rr * Math.sin(a1)),
        fill: 'none', stroke: 'var(--series-' + s.slot + ')', 'stroke-width': 3, 'stroke-linecap': 'round', opacity: 0.85
      }));
    }

    /* edges */
    const eg = S('g');
    svg.appendChild(eg);
    const edgeNodes = [];
    for (const e of opts.edges) {
      const a = pos[e.src], b = pos[e.dst];
      if (!a || !b) continue;
      const bend = 0.42;
      const mx = cx + (a.x + b.x) / 2 * 0 + ((a.x + b.x) / 2 - cx) * (1 - bend);
      const my = cy + ((a.y + b.y) / 2 - cy) * (1 - bend);
      const rn = rad(opts.nodeBy[e.dst]);
      /* stop short of the node so the arrowhead sits outside it */
      const t = 0.94;
      const px = (1 - t) * (1 - t) * a.x + 2 * (1 - t) * t * mx + t * t * b.x;
      const py = (1 - t) * (1 - t) * a.y + 2 * (1 - t) * t * my + t * t * b.y;
      const dx = b.x - px, dy = b.y - py, dl = Math.hypot(dx, dy) || 1;
      const ex = b.x - (dx / dl) * (rn + 5), ey = b.y - (dy / dl) * (rn + 5);
      const col = e.rho >= 0 ? 'var(--div-pos)' : 'var(--div-neg)';
      const sw = 0.8 + 3.2 * Math.min(1, Math.abs(e.rho));
      const p = S('path', {
        d: 'M' + a.x + ' ' + a.y + ' Q' + mx + ' ' + my + ' ' + ex + ' ' + ey,
        fill: 'none', stroke: col, 'stroke-width': sw, 'stroke-opacity': 0.5, 'stroke-linecap': 'round',
        tabindex: 0, role: 'button',
        'aria-label': opts.nodeBy[e.src].name + ' leads ' + opts.nodeBy[e.dst].name + ' by ' + e.lag + ' months, rho ' + fmt(e.rho, 2)
      });
      const ah = 4 + 1.6 * sw;
      const nx = dx / dl, ny = dy / dl;
      const head = S('path', {
        d: 'M' + ex + ' ' + ey +
           ' L' + (ex - nx * ah + ny * ah * 0.5) + ' ' + (ey - ny * ah - nx * ah * 0.5) +
           ' L' + (ex - nx * ah - ny * ah * 0.5) + ' ' + (ey - ny * ah + nx * ah * 0.5) + ' Z',
        fill: col, 'fill-opacity': 0.5
      });
      const body = opts.edgeTip(e);
      p.addEventListener('mouseenter', ev => showTip(body, ev.clientX, ev.clientY));
      p.addEventListener('mousemove', ev => showTip(body, ev.clientX, ev.clientY));
      p.addEventListener('mouseleave', hideTip);
      p.addEventListener('focus', () => { const r = p.getBoundingClientRect(); showTip(body, r.left + r.width / 2, r.top); });
      p.addEventListener('blur', hideTip);
      eg.appendChild(p); eg.appendChild(head);
      edgeNodes.push({ e: e, p: p, head: head });
    }

    /* nodes + radial labels */
    const ng = S('g');
    svg.appendChild(ng);
    const nodeMarks = {};
    for (const s of sectors) {
      for (let i = 0; i < s.n; i++) {
        const n = order[s.from + i];
        const p = pos[n.code], r = rad(n);
        const on = (n.deg || 0) > 0;
        const c = S('circle', {
          cx: p.x, cy: p.y, r: r,
          fill: on ? 'var(--series-' + s.slot + ')' : 'var(--surface-1)',
          stroke: on ? 'var(--surface-1)' : 'var(--axis)',
          'stroke-width': on ? 2 : 1.2,
          tabindex: 0, role: 'button', 'aria-label': n.name + ', ' + n.groupName + ', weight ' + fmt(n.weight, 2) + '%, ' + (n.deg || 0) + ' stable edges'
        });
        let lab = null;
        if (on) {
          const flip = Math.cos(p.a) < 0;
          const short = fitLabel(n.name, LAB_CHARS * 5.6, 5.6);
          lab = S('text', {
            x: flip ? -(R + 8) : (R + 8), y: 3.5, class: 'netlab',
            'text-anchor': flip ? 'end' : 'start', fill: 'var(--text-secondary)',
            transform: 'translate(' + cx + ',' + cy + ') rotate(' + (p.a * 180 / Math.PI + (flip ? 180 : 0)) + ')'
          }, [document.createTextNode(short)]);
          svg.appendChild(lab);
        }
        const body = opts.nodeTip(n);
        const enter = ev => { showTip(body, ev.clientX, ev.clientY); highlight(n.code); };
        c.addEventListener('mouseenter', enter);
        c.addEventListener('mousemove', ev => showTip(body, ev.clientX, ev.clientY));
        c.addEventListener('mouseleave', () => { hideTip(); highlight(selected); });
        c.addEventListener('focus', () => { const q = c.getBoundingClientRect(); showTip(body, q.left, q.top); highlight(n.code); });
        c.addEventListener('blur', () => { hideTip(); highlight(selected); });
        c.addEventListener('click', () => {
          selected = selected === n.code ? null : n.code;
          highlight(selected);
          if (opts.onSelect) opts.onSelect(selected ? n : null);
        });
        c.addEventListener('keydown', ev => {
          if (ev.key === 'Enter' || ev.key === ' ') { c.dispatchEvent(new Event('click')); ev.preventDefault(); }
          else if (ev.key === 'Escape') { selected = null; highlight(null); hideTip(); if (opts.onSelect) opts.onSelect(null); }
        });
        ng.appendChild(c);
        nodeMarks[n.code] = { c: c, lab: lab };
      }
    }

    /* 2-level cascade highlight */
    function highlight(code) {
      if (!code) {
        for (const en of edgeNodes) { en.p.setAttribute('stroke-opacity', 0.5); en.head.setAttribute('fill-opacity', 0.5); }
        for (const k in nodeMarks) { nodeMarks[k].c.setAttribute('opacity', 1); if (nodeMarks[k].lab) nodeMarks[k].lab.setAttribute('opacity', 1); }
        return;
      }
      const cas = (opts.cascade || {})[code] || { l1: [], l2: [] };
      const keep = {};
      keep[code] = 1;
      const pairs = {};
      for (const d of (cas.l1 || [])) { keep[d.dst] = 1; pairs[code + '|' + d.dst] = 1; }
      for (const d of (cas.l2 || [])) { keep[d.dst] = 1; keep[d.via] = 1; pairs[d.via + '|' + d.dst] = 1; }
      for (const en of edgeNodes) {
        const on = pairs[en.e.src + '|' + en.e.dst];
        en.p.setAttribute('stroke-opacity', on ? 0.95 : 0.06);
        en.p.setAttribute('stroke-width', on ? (1.4 + 3.4 * Math.min(1, Math.abs(en.e.rho))) : (0.8 + 3.2 * Math.min(1, Math.abs(en.e.rho))));
        en.head.setAttribute('fill-opacity', on ? 0.95 : 0.06);
      }
      for (const k in nodeMarks) {
        const on = keep[k];
        nodeMarks[k].c.setAttribute('opacity', on ? 1 : 0.18);
        if (nodeMarks[k].lab) nodeMarks[k].lab.setAttribute('opacity', on ? 1 : 0.18);
      }
    }
    highlight(selected);

    svgHost.appendChild(svg);
  }

  mountChart(svgHost, draw);
  return { slotOf: g => SLOT[g] };
}

/* =========================================================================
 * SPARKLINE for stat tiles — de-emphasis hue, current point in the accent.
 * ========================================================================= */
function sparkline(host, values, opts) {
  opts = opts || {};
  function draw(W) {
    clear(host);
    const w = Math.max(60, W), h = opts.height || 30;
    const vs = values;
    const idx = vs.map((v, i) => i).filter(i => vs[i] !== null && isFinite(vs[i]));
    if (!idx.length) return;
    let lo = Infinity, hi = -Infinity;
    for (const i of idx) { lo = Math.min(lo, vs[i]); hi = Math.max(hi, vs[i]); }
    if (lo === hi) { lo -= 1; hi += 1; }
    const x = linScale(0, vs.length - 1, 1, w - 5);
    const y = linScale(lo, hi, h - 3, 3);
    const svg = S('svg', { width: w, height: h, 'aria-hidden': 'true', focusable: 'false' });
    let d = '', open = false;
    for (let i = 0; i < vs.length; i++) {
      const v = vs[i];
      if (v === null || !isFinite(v)) { open = false; continue; }
      d += (open ? 'L' : 'M') + x(i) + ' ' + y(v) + ' ';
      open = true;
    }
    svg.appendChild(S('path', { d: d, fill: 'none', stroke: 'var(--spark)', 'stroke-width': 1.5, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    const last = idx[idx.length - 1];
    svg.appendChild(S('circle', { cx: x(last), cy: y(vs[last]), r: 3, fill: opts.color || 'var(--series-1)', stroke: 'var(--surface-1)', 'stroke-width': 2 }));
    host.appendChild(svg);
  }
  mountChart(host, draw);
}
