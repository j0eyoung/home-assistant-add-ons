// Small SVG chart helpers: bar charts (snow) and line charts (model totals, temperature).
// Marks follow the dataviz rules: thin marks, 4px rounded bar ends on the baseline, 2px gaps, recessive grid,
// one y-axis, hover tooltip on every mark, crosshair on lines. Colours come from CSS variables (light/dark).
const SVGNS = 'http://www.w3.org/2000/svg';

const Tip = {
  el: () => document.getElementById('tip'),
  show(html, ev) {
    const t = Tip.el(); t.innerHTML = html; t.style.display = 'block';
    const r = t.getBoundingClientRect();
    let x = ev.clientX + 14, y = ev.clientY + 14;
    if (x + r.width > innerWidth - 8) x = ev.clientX - r.width - 14;
    if (y + r.height > innerHeight - 8) y = ev.clientY - r.height - 14;
    t.style.left = Math.max(8, x) + 'px'; t.style.top = Math.max(8, y) + 'px';
  },
  hide() { Tip.el().style.display = 'none'; },
};

function svgEl(tag, attrs, parent) {
  const e = document.createElementNS(SVGNS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}

function niceMax(v, floor) {
  v = Math.max(v, floor || 0);
  for (const s of [1, 2, 3, 4, 6, 8, 10, 12, 16, 20, 24, 30, 36, 48, 60, 80, 100, 120]) if (v <= s) return s;
  return Math.ceil(v / 50) * 50;
}

// Bar with a 4px rounded top, flat on the baseline
function barPath(x, y, w, h, r) {
  if (h <= 0) return '';
  r = Math.min(r, w / 2, h);
  const b = y + h;
  return `M${x},${b}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${b}Z`;
}

// Re-render charts when the window width changes
const Charts = { list: [], add(fn) { this.list.push(fn); fn(); } };
let _rz;
addEventListener('resize', () => { clearTimeout(_rz); _rz = setTimeout(() => {
  Charts.list = Charts.list.filter(fn => fn() !== false);
}, 150); });

/* bars: [{v, fill, tip}] ; opts: {height, axis, labels, labelEvery, todayIndex, floorMax, unit}
   Returns false when the container is gone (so the resize list drops it). */
function barChart(el, bars, opts = {}) {
  if (!el.isConnected) return false;
  el.innerHTML = '';
  const W = el.clientWidth || 300, H = opts.height || 120;
  const axis = opts.axis !== false;
  const padL = axis ? 30 : 0, padB = axis && opts.labels ? 18 : 0, padT = axis ? 8 : 2;
  const pw = W - padL, ph = H - padB - padT;
  const max = niceMax(Math.max(0, ...bars.map(b => b.v || 0)), opts.floorMax ?? 2);
  const svg = svgEl('svg', { width: W, height: H, role: 'img', 'aria-label': opts.title || 'Snow chart' }, el);
  if (axis) {
    for (const f of [0, .5, 1]) {
      const y = padT + ph - ph * f;
      svgEl('line', { x1: padL, x2: W, y1: y, y2: y, class: f ? 'gridline' : 'baseline' }, svg);
      const t = svgEl('text', { x: padL - 6, y: y + 4, 'text-anchor': 'end' }, svg);
      t.textContent = (max * f) + (f === 1 ? (opts.unit || '"') : '');
    }
  } else {
    svgEl('line', { x1: 0, x2: W, y1: padT + ph, y2: padT + ph, class: 'baseline' }, svg);
  }
  const slot = pw / bars.length, gap = Math.max(2, Math.min(6, slot * .25)), bw = Math.max(2, slot - gap);
  if (opts.todayIndex != null && opts.todayIndex > 0) {
    const x = padL + slot * opts.todayIndex - gap / 2;
    svgEl('line', { x1: x, x2: x, y1: padT - 2, y2: padT + ph, class: 'today' }, svg);
  }
  bars.forEach((b, i) => {
    const x = padL + slot * i + gap / 2;
    const h = b.v > 0 ? Math.max(2, ph * b.v / max) : 0;
    const hit = svgEl('rect', { x: padL + slot * i, y: padT, width: slot, height: ph, class: 'hit' }, svg);
    const bar = svgEl('path', { d: barPath(x, padT + ph - h, bw, h, 4), fill: b.fill || 'var(--snow)', class: 'bar' }, svg);
    if (b.tip) {
      hit.addEventListener('mousemove', ev => { bar.classList.add('hl'); Tip.show(b.tip, ev); });
      hit.addEventListener('mouseleave', () => { bar.classList.remove('hl'); Tip.hide(); });
    }
    if (b.onclick) hit.addEventListener('click', b.onclick);
    if (axis && opts.labels && i % (opts.labelEvery || 1) === 0) {
      const t = svgEl('text', { x: x + bw / 2, y: H - 4, 'text-anchor': 'middle' }, svg);
      t.textContent = opts.labels[i];
    }
  });
}

/* series: [{name, color, values}] ; opts: {height, labels, labelEvery, unit, tip(i) -> html, directLabels, floorMax, min} */
function lineChart(el, series, opts = {}) {
  if (!el.isConnected) return false;
  el.innerHTML = '';
  const W = el.clientWidth || 300, H = opts.height || 140;
  const padL = 34, padR = opts.directLabels ? 56 : 8, padT = 8, padB = 18;
  const pw = W - padL - padR, ph = H - padT - padB;
  const all = series.flatMap(s => s.values.filter(v => v != null));
  let lo = opts.min != null ? opts.min : Math.min(...all), hi = Math.max(...all);
  if (opts.min == null) { const span = Math.max(hi - lo, 4); lo = Math.floor((lo - span * .1) / 5) * 5; hi = Math.ceil((hi + span * .1) / 5) * 5; }
  else hi = niceMax(hi, opts.floorMax ?? 2);
  const n = opts.labels.length;
  const X = i => padL + (n > 1 ? pw * i / (n - 1) : pw / 2);
  const Y = v => padT + ph - ph * (v - lo) / ((hi - lo) || 1);
  const svg = svgEl('svg', { width: W, height: H, role: 'img', 'aria-label': opts.title || 'Line chart' }, el);
  for (const f of [0, .5, 1]) {
    const v = lo + (hi - lo) * f, y = Y(v);
    svgEl('line', { x1: padL, x2: padL + pw, y1: y, y2: y, class: f ? 'gridline' : 'baseline' }, svg);
    const t = svgEl('text', { x: padL - 6, y: y + 4, 'text-anchor': 'end' }, svg);
    t.textContent = Math.round(v * 10) / 10 + (f === 1 ? (opts.unit || '') : '');
  }
  opts.labels.forEach((l, i) => {
    if (i % (opts.labelEvery || 1)) return;
    const t = svgEl('text', { x: X(i), y: H - 4, 'text-anchor': 'middle' }, svg); t.textContent = l;
  });
  for (const s of series) {
    let d = '', pen = false;
    s.values.forEach((v, i) => { if (v == null) { pen = false; return; } d += (pen ? 'L' : 'M') + X(i) + ',' + Y(v); pen = true; });
    svgEl('path', { d, fill: 'none', stroke: s.color, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
    if (opts.directLabels) {
      const last = s.values.reduce((a, v, i) => v != null ? i : a, -1);
      if (last >= 0) { const t = svgEl('text', { x: X(last) + 6, y: Y(s.values[last]) + 4, class: 'dlabel' }, svg); t.textContent = s.name; }
    }
  }
  // Crosshair + tooltip
  const cross = svgEl('line', { y1: padT, y2: padT + ph, class: 'cross', visibility: 'hidden' }, svg);
  const dots = series.map(s => svgEl('circle', { r: 4, fill: s.color, stroke: 'var(--surface)', 'stroke-width': 2, visibility: 'hidden' }, svg));
  const hit = svgEl('rect', { x: padL, y: padT, width: pw, height: ph, class: 'hit' }, svg);
  hit.addEventListener('mousemove', ev => {
    const box = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(n - 1, Math.round((ev.clientX - box.left - padL) / (pw / Math.max(1, n - 1)))));
    cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i)); cross.setAttribute('visibility', 'visible');
    series.forEach((s, k) => {
      const v = s.values[i];
      if (v == null) { dots[k].setAttribute('visibility', 'hidden'); return; }
      dots[k].setAttribute('cx', X(i)); dots[k].setAttribute('cy', Y(v)); dots[k].setAttribute('visibility', 'visible');
    });
    if (opts.tip) Tip.show(opts.tip(i), ev);
  });
  hit.addEventListener('mouseleave', () => { cross.setAttribute('visibility', 'hidden'); dots.forEach(d => d.setAttribute('visibility', 'hidden')); Tip.hide(); });
}
