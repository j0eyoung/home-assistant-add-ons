/* Small canvas charts for the terminal: price (line / area / candles) with overlays, volume and indicator panes,
   a crosshair readout, grouped bars, sparklines and a treemap. No libraries, so pages load fast. */
(function () {
  "use strict";
  const C = { grid: "#15181c", axis: "#6f767f", text: "#a7adb5", cross: "#5c6168", up: "#2fd36b", dn: "#ff4f4f",
              amber: "#ffa62b", bg: "#0a0b0d" };
  const NY = "America/New_York";
  const fmtCache = {};
  function dfmt(opts) {
    const k = JSON.stringify(opts);
    return fmtCache[k] || (fmtCache[k] = new Intl.DateTimeFormat("en-US", { timeZone: NY, ...opts }));
  }
  const fTime = t => dfmt({ hour: "2-digit", minute: "2-digit", hour12: false }).format(t);
  const fDay = t => dfmt({ month: "short", day: "numeric" }).format(t);
  const fDayYr = t => dfmt({ month: "short", day: "numeric", year: "2-digit" }).format(t);
  const fMonYr = t => dfmt({ month: "short", year: "2-digit" }).format(t);
  const fYear = t => dfmt({ year: "numeric" }).format(t);
  const fFull = t => dfmt({ weekday: "short", month: "short", day: "numeric", year: "numeric" }).format(t);
  const fFullTime = t => dfmt({ weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }).format(t) + " ET";

  function niceStep(span, n) {
    const raw = span / Math.max(1, n), p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p;
    return (m < 1.5 ? 1 : m < 3 ? 2 : m < 7 ? 5 : 10) * p;
  }
  function range(arrs, pad = 0.06) {
    let lo = Infinity, hi = -Infinity;
    for (const a of arrs) if (a) for (const v of a) if (v != null && isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; }
    if (!isFinite(lo)) return [0, 1];
    if (lo === hi) { const d = Math.abs(lo) * 0.01 || 1; lo -= d; hi += d; }
    const d = (hi - lo) * pad;
    return [lo - d, hi + d];
  }
  const defFmt = v => v == null ? "–" : Math.abs(v) >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 })
    : Math.abs(v) >= 1 ? v.toFixed(2) : v.toFixed(Math.abs(v) >= 0.01 ? 4 : 6);
  function alpha(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`;
  }

  class TChart {
    constructor(el, cfg) {
      this.el = el;
      el.classList.add("chart");
      el.innerHTML = "";
      this.cv = document.createElement("canvas");
      this.lg = document.createElement("div");
      this.lg.className = "legend";
      el.append(this.cv, this.lg);
      this.ctx = this.cv.getContext("2d");
      this.hover = null;
      this.ro = new ResizeObserver(() => this.draw());
      this.ro.observe(el);
      const move = e => {
        const r = this.cv.getBoundingClientRect();
        this.pointer = { x: e.clientX - r.left, y: e.clientY - r.top };
        this.hover = this.indexAt(this.pointer.x);
        this.queue();
      };
      this.cv.addEventListener("pointermove", move);
      this.cv.addEventListener("pointerdown", move);
      this.cv.addEventListener("pointerleave", () => { this.hover = null; this.pointer = null; this.queue(); });
      this.set(cfg);
    }
    set(cfg) { this.cfg = cfg; this.n = (cfg.t || []).length; this.hover = null; this.draw(); }
    queue() { if (!this.raf) this.raf = requestAnimationFrame(() => { this.raf = 0; this.draw(); }); }
    indexAt(x) {
      if (!this.L || !this.n) return null;
      const i = Math.floor((x - this.L.left) / this.L.step);
      return i < 0 || i >= this.n ? null : i;
    }
    destroy() { this.ro.disconnect(); }

    draw() {
      const cfg = this.cfg, el = this.el, W = el.clientWidth, H = el.clientHeight;
      if (!W || !H) return;
      const dpr = window.devicePixelRatio || 1;
      if (this.cv.width !== Math.round(W * dpr) || this.cv.height !== Math.round(H * dpr)) {
        this.cv.width = Math.round(W * dpr); this.cv.height = Math.round(H * dpr);
      }
      const g = this.ctx;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, W, H);
      const n = this.n;
      if (!n) { this.lg.textContent = "No data for this range"; return; }
      const axes = cfg.axes !== false;
      const right = axes ? (W < 500 ? 46 : 58) : 0, bottom = axes ? 18 : 0, top = cfg.legend === false ? 4 : 20;
      const left = 0, plotW = W - right - left;
      const step = plotW / n;
      const panes = cfg.panes || [];
      const volH = cfg.v && cfg.volume ? Math.max(36, (H - top - bottom) * 0.14) : 0;
      const paneH = panes.length ? Math.max(56, (H - top - bottom) * 0.2) : 0;
      const mainH = H - top - bottom - volH - paneH * panes.length - (panes.length + (volH ? 1 : 0)) * 6;
      this.L = { left, step, plotW };
      const X = i => left + (i + 0.5) * step;
      const fmt = cfg.yfmt || defFmt;
      g.font = "10.5px 'IBM Plex Mono', monospace";
      g.textBaseline = "middle";

      // ---- main pane ----
      const candle = cfg.kind === "candle" && cfg.o;
      const ov = cfg.overlays || [];
      const [lo, hi] = range([candle ? cfg.h : cfg.c, candle ? cfg.l : null, ...ov.map(o => o.v),
                              cfg.baseline != null ? [cfg.baseline] : null]);
      const y0 = top, y1 = top + mainH;
      const Y = v => y1 - (v - lo) / (hi - lo) * (y1 - y0);
      this.grid(g, lo, hi, y0, y1, Y, W, right, axes, fmt);
      const first = cfg.c.find(v => v != null), last = [...cfg.c].reverse().find(v => v != null);
      const base = cfg.baseline != null ? cfg.baseline : first;
      const color = cfg.color || (last >= base ? C.up : C.dn);
      if (cfg.baseline != null) {
        g.strokeStyle = "#4a4f56"; g.setLineDash([2, 3]); g.lineWidth = 1;
        g.beginPath(); g.moveTo(left, Y(cfg.baseline)); g.lineTo(left + plotW, Y(cfg.baseline)); g.stroke(); g.setLineDash([]);
      }
      if (candle) {
        const bw = Math.max(1, Math.min(14, step * 0.68));
        for (let i = 0; i < n; i++) {
          const o = cfg.o[i], h = cfg.h[i], l = cfg.l[i], c = cfg.c[i];
          if (c == null || o == null) continue;
          const col = c >= o ? C.up : C.dn, x = X(i);
          g.strokeStyle = col; g.fillStyle = col; g.lineWidth = 1;
          g.beginPath(); g.moveTo(Math.round(x) + .5, Y(h)); g.lineTo(Math.round(x) + .5, Y(l)); g.stroke();
          const yt = Y(Math.max(o, c)), yb = Y(Math.min(o, c));
          g.fillRect(x - bw / 2, yt, bw, Math.max(1, yb - yt));
        }
      } else {
        g.beginPath();
        let started = false, lastX = 0;
        for (let i = 0; i < n; i++) {
          const v = cfg.c[i];
          if (v == null) continue;
          const x = X(i), y = Y(v);
          if (!started) { g.moveTo(x, y); started = true; } else g.lineTo(x, y);
          lastX = x;
        }
        g.strokeStyle = color; g.lineWidth = cfg.width || 1.6; g.lineJoin = "round"; g.stroke();
        if (cfg.kind === "area" && started) {
          g.lineTo(lastX, y1); g.lineTo(X(cfg.c.findIndex(v => v != null)), y1); g.closePath();
          const gr = g.createLinearGradient(0, y0, 0, y1);
          gr.addColorStop(0, alpha(color, 0.22)); gr.addColorStop(1, alpha(color, 0));
          g.fillStyle = gr; g.fill();
        }
      }
      for (const o of ov) {
        g.beginPath(); let s = false;
        for (let i = 0; i < n; i++) {
          const v = o.v[i];
          if (v == null) { s = false; continue; }
          if (!s) { g.moveTo(X(i), Y(v)); s = true; } else g.lineTo(X(i), Y(v));
        }
        g.strokeStyle = o.color; g.lineWidth = o.width || 1.2; g.setLineDash(o.dash || []); g.stroke(); g.setLineDash([]);
      }
      for (const m of cfg.markers || []) {
        const x = X(m.i), y = Y(m.y), up = m.kind === "buy";
        g.fillStyle = up ? C.up : C.dn;
        g.beginPath();
        if (up) { g.moveTo(x, y + 4); g.lineTo(x - 5, y + 12); g.lineTo(x + 5, y + 12); }
        else { g.moveTo(x, y - 4); g.lineTo(x - 5, y - 12); g.lineTo(x + 5, y - 12); }
        g.fill();
      }
      if (axes && last != null) {  // last-price tag on the axis
        const yl = Y(last);
        g.fillStyle = color; g.fillRect(W - right + 1, yl - 8, right - 1, 16);
        g.fillStyle = "#000"; g.textAlign = "left"; g.fillText(fmt(last), W - right + 4, yl);
      }

      // ---- volume ----
      let yy = y1 + 6;
      const extra = [];
      if (volH) {
        const vmax = Math.max(...cfg.v.map(v => v || 0)) || 1, vy1 = yy + volH;
        const bw = Math.max(1, step * 0.7);
        for (let i = 0; i < n; i++) {
          const v = cfg.v[i]; if (!v) continue;
          const up = (cfg.o && cfg.o[i] != null) ? cfg.c[i] >= cfg.o[i] : i === 0 || cfg.c[i] >= cfg.c[i - 1];
          g.fillStyle = up ? alpha(C.up, 0.35) : alpha(C.dn, 0.35);
          const hh = v / vmax * (volH - 2);
          g.fillRect(X(i) - bw / 2, vy1 - hh, bw, hh);
        }
        extra.push({ y0: yy, y1: vy1, name: "VOL", vals: [{ name: "Vol", v: cfg.v, color: C.text, big: true }] });
        yy = vy1 + 6;
      }
      // ---- indicator panes ----
      for (const p of panes) {
        const py0 = yy, py1 = yy + paneH;
        const [plo, phi] = p.min != null ? [p.min, p.max] : range(p.series.map(s => s.v).concat(p.levels ? [p.levels] : []), 0.08);
        const PY = v => py1 - (v - plo) / (phi - plo) * (py1 - py0);
        g.strokeStyle = C.grid; g.lineWidth = 1;
        g.beginPath(); g.moveTo(0, py0 - 3); g.lineTo(W - right, py0 - 3); g.stroke();
        for (const lv of p.levels || []) {
          g.strokeStyle = "#3a3f46"; g.setLineDash([2, 3]);
          g.beginPath(); g.moveTo(0, PY(lv)); g.lineTo(plotW, PY(lv)); g.stroke(); g.setLineDash([]);
          if (axes) { g.fillStyle = C.axis; g.textAlign = "left"; g.fillText(String(lv), W - right + 4, PY(lv)); }
        }
        for (const s of p.series) {
          if (s.type === "hist") {
            const bw = Math.max(1, step * 0.7), z = PY(0);
            for (let i = 0; i < n; i++) {
              const v = s.v[i]; if (v == null) continue;
              g.fillStyle = v >= 0 ? alpha(C.up, 0.6) : alpha(C.dn, 0.6);
              g.fillRect(X(i) - bw / 2, Math.min(z, PY(v)), bw, Math.abs(PY(v) - z));
            }
          } else {
            g.beginPath(); let st = false;
            for (let i = 0; i < n; i++) {
              const v = s.v[i]; if (v == null) { st = false; continue; }
              if (!st) { g.moveTo(X(i), PY(v)); st = true; } else g.lineTo(X(i), PY(v));
            }
            g.strokeStyle = s.color; g.lineWidth = 1.2; g.stroke();
          }
        }
        if (axes && !p.levels) { g.fillStyle = C.axis; g.textAlign = "left"; g.fillText(fmt2(phi), W - right + 4, py0 + 6); g.fillText(fmt2(plo), W - right + 4, py1 - 6); }
        g.fillStyle = C.axis; g.textAlign = "left"; g.fillText(p.name, 4, py0 + 7);
        extra.push({ y0: py0, y1: py1, name: p.name, vals: p.series, PY });
        yy = py1 + 6;
      }

      // ---- x axis ----
      if (axes) {
        const t = cfg.t, span = t[n - 1] - t[0];
        const lab = cfg.intraday ? (span > 2 * 864e5 ? fDay : fTime) : span > 3 * 365 * 864e5 ? fYear : span > 200 * 864e5 ? fMonYr : fDay;
        const want = Math.max(2, Math.floor(plotW / 90)), every = Math.max(1, Math.ceil(n / want));
        g.fillStyle = C.axis; g.textAlign = "center";
        let prev = "";
        for (let i = Math.floor(every / 2); i < n; i += every) {
          const s = lab(t[i]);
          if (s === prev) continue;
          prev = s;
          g.fillText(s, Math.min(Math.max(X(i), 20), plotW - 20), H - bottom / 2);
        }
      }

      // ---- crosshair & legend ----
      const i = this.hover != null ? this.hover : n - 1;
      if (this.hover != null) {
        const x = X(i);
        g.strokeStyle = C.cross; g.lineWidth = 1; g.setLineDash([3, 3]);
        g.beginPath(); g.moveTo(Math.round(x) + .5, y0); g.lineTo(Math.round(x) + .5, H - bottom); g.stroke();
        if (this.pointer && this.pointer.y >= y0 && this.pointer.y <= y1) {
          g.beginPath(); g.moveTo(0, this.pointer.y); g.lineTo(plotW, this.pointer.y); g.stroke();
          if (axes) {
            const v = lo + (y1 - this.pointer.y) / (y1 - y0) * (hi - lo);
            g.setLineDash([]); g.fillStyle = "#2b3036"; g.fillRect(W - right + 1, this.pointer.y - 8, right - 1, 16);
            g.fillStyle = "#fff"; g.textAlign = "left"; g.fillText(fmt(v), W - right + 4, this.pointer.y);
          }
        }
        g.setLineDash([]);
        const v = cfg.c[i];
        if (v != null && !candle) { g.fillStyle = color; g.beginPath(); g.arc(x, Y(v), 3, 0, 7); g.fill(); }
        if (axes) {
          const s = cfg.intraday ? fFullTime(cfg.t[i]) : fFull(cfg.t[i]);
          const w = g.measureText(s).width + 10, bx = Math.min(Math.max(x - w / 2, 0), plotW - w);
          g.fillStyle = "#2b3036"; g.fillRect(bx, H - bottom, w, bottom);
          g.fillStyle = "#fff"; g.textAlign = "center"; g.fillText(s, bx + w / 2, H - bottom / 2);
        }
      }
      if (cfg.legend !== false) {
        const parts = [];
        const when = cfg.intraday ? fFullTime(cfg.t[i]) : fFull(cfg.t[i]);
        parts.push(`<i style="color:#e6e6e6">${when}</i>`);
        if (candle) parts.push(`<i>O <b style="color:#fff">${fmt(cfg.o[i])}</b> H <b style="color:#fff">${fmt(cfg.h[i])}</b> L <b style="color:#fff">${fmt(cfg.l[i])}</b> C <b style="color:#fff">${fmt(cfg.c[i])}</b></i>`);
        else parts.push(`<i style="color:${color}">${cfg.name || ""} <b>${fmt(cfg.c[i])}</b>${cfg.pctOf != null && cfg.c[i] != null ? ` (${((cfg.c[i] / cfg.pctOf - 1) * 100).toFixed(2)}%)` : ""}</i>`);
        for (const o of ov) if (o.v[i] != null) parts.push(`<i style="color:${o.color}">${o.name} ${fmt(o.v[i])}</i>`);
        for (const p of extra) for (const s of p.vals) if (s.v && s.v[i] != null)
          parts.push(`<i style="color:${s.color || C.text}">${s.name} ${s.big ? big(s.v[i]) : fmt2(s.v[i])}</i>`);
        this.lg.innerHTML = parts.join("");
      } else this.lg.innerHTML = "";
    }

    grid(g, lo, hi, y0, y1, Y, W, right, axes, fmt) {
      const st = niceStep(hi - lo, Math.max(2, Math.floor((y1 - y0) / 48)));
      g.lineWidth = 1; g.textAlign = "left";
      for (let v = Math.ceil(lo / st) * st; v <= hi; v += st) {
        const y = Math.round(Y(v)) + .5;
        g.strokeStyle = C.grid; g.beginPath(); g.moveTo(0, y); g.lineTo(W - right, y); g.stroke();
        if (axes) { g.fillStyle = C.axis; g.fillText(fmt(v), W - right + 4, y); }
      }
    }
  }
  const fmt2 = v => v == null ? "–" : Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2);
  function big(v) {
    if (v == null) return "–";
    const a = Math.abs(v);
    return a >= 1e12 ? (v / 1e12).toFixed(2) + "T" : a >= 1e9 ? (v / 1e9).toFixed(2) + "B" : a >= 1e6 ? (v / 1e6).toFixed(2) + "M"
      : a >= 1e3 ? (v / 1e3).toFixed(1) + "K" : v.toFixed(0);
  }

  // Grouped bars (financial statements, earnings): labels along x, a readout on hover.
  class BarChart {
    constructor(el, cfg) {
      this.el = el; el.classList.add("chart"); el.innerHTML = "";
      this.cv = document.createElement("canvas"); this.lg = document.createElement("div"); this.lg.className = "legend";
      el.append(this.cv, this.lg); this.ctx = this.cv.getContext("2d"); this.cfg = cfg; this.hover = null;
      this.ro = new ResizeObserver(() => this.draw()); this.ro.observe(el);
      this.cv.addEventListener("pointermove", e => { const r = this.cv.getBoundingClientRect(); this.hover = Math.floor((e.clientX - r.left) / this.gw); this.draw(); });
      this.cv.addEventListener("pointerleave", () => { this.hover = null; this.draw(); });
    }
    draw() {
      const { labels, series } = this.cfg, fmt = this.cfg.fmt || big;
      const W = this.el.clientWidth, H = this.el.clientHeight, dpr = window.devicePixelRatio || 1;
      if (!W || !H) return;
      this.cv.width = W * dpr; this.cv.height = H * dpr;
      const g = this.ctx; g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
      const top = 20, bottom = 18, right = 52, plotW = W - right, n = labels.length;
      const all = series.flatMap(s => s.v).filter(v => v != null);
      let lo = Math.min(0, ...all), hi = Math.max(0, ...all);
      if (lo === hi) hi = lo + 1;
      const Y = v => top + (hi - v) / (hi - lo) * (H - top - bottom);
      this.gw = plotW / Math.max(1, n);
      g.font = "10.5px 'IBM Plex Mono', monospace"; g.textBaseline = "middle";
      const st = niceStep(hi - lo, 4);
      for (let v = Math.ceil(lo / st) * st; v <= hi; v += st) {
        g.strokeStyle = v === 0 ? "#3a3f46" : C.grid; g.beginPath(); g.moveTo(0, Y(v)); g.lineTo(plotW, Y(v)); g.stroke();
        g.fillStyle = C.axis; g.textAlign = "left"; g.fillText(fmt(v), plotW + 4, Y(v));
      }
      const bw = Math.min(26, this.gw * 0.8 / series.length);
      labels.forEach((lab, i) => {
        const cx = i * this.gw + this.gw / 2;
        series.forEach((s, k) => {
          const v = s.v[i]; if (v == null) return;
          const x = cx - bw * series.length / 2 + k * bw;
          g.fillStyle = typeof s.color === "function" ? s.color(v, i) : s.color;
          if (this.hover != null && this.hover !== i) g.globalAlpha = 0.45;
          g.fillRect(x + 1, Math.min(Y(v), Y(0)), bw - 2, Math.max(1, Math.abs(Y(v) - Y(0))));
          g.globalAlpha = 1;
        });
        if (n <= 16 || i % Math.ceil(n / 12) === 0) { g.fillStyle = C.axis; g.textAlign = "center"; g.fillText(String(lab).slice(0, 10), cx, H - bottom / 2); }
      });
      const i = this.hover != null && this.hover < n ? this.hover : n - 1;
      this.lg.innerHTML = `<i style="color:#e6e6e6">${labels[i] ?? ""}</i>` + series.map(s => `<i style="color:${typeof s.color === "string" ? s.color : C.text}">${s.name} ${fmt(s.v[i])}</i>`).join("");
    }
  }

  function spark(vals, base, w = 76, h = 22) {
    vals = (vals || []).filter(v => v != null);
    if (vals.length < 2) return "";
    const pts = base != null ? vals.concat([base]) : vals;
    const lo = Math.min(...pts), hi = Math.max(...pts), sp = hi - lo || 1;
    const y = v => (h - 2 - (v - lo) / sp * (h - 4)).toFixed(1);
    const d = vals.map((v, i) => `${(i * w / (vals.length - 1)).toFixed(1)},${y(v)}`).join(" ");
    const col = vals[vals.length - 1] >= (base != null ? base : vals[0]) ? C.up : C.dn;
    const bl = base != null ? `<line x1="0" x2="${w}" y1="${y(base)}" y2="${y(base)}" stroke="#3a3f46" stroke-dasharray="1 3"/>` : "";
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${bl}<polyline fill="none" stroke="${col}" stroke-width="1.4" points="${d}"/></svg>`;
  }

  // Squarified treemap: groups (sectors) holding items (stocks); colour from each item's value.
  function treemap(el, groups, color, onClick) {
    el.classList.add("tmap"); el.innerHTML = "";
    const W = el.clientWidth, H = el.clientHeight;
    const layout = (items, x, y, w, h) => {
      const total = items.reduce((a, b) => a + b.size, 0), out = [];
      let rest = items.slice().sort((a, b) => b.size - a.size), rx = x, ry = y, rw = w, rh = h, sum = total;
      while (rest.length) {
        const short = Math.min(rw, rh), row = [];
        let best = Infinity;
        for (const it of rest) {
          const r = row.concat(it), s = r.reduce((a, b) => a + b.size, 0), side = s / sum * (rw >= rh ? rw : rh);
          const worst = Math.max(...r.map(z => { const len = z.size / s * short; return Math.max(side / len, len / side); }));
          if (worst > best) break;
          best = worst; row.push(it);
        }
        const s = row.reduce((a, b) => a + b.size, 0), thick = s / sum * (rw >= rh ? rw : rh);
        let off = 0;
        for (const it of row) {
          const len = it.size / s * short;
          out.push(rw >= rh ? { it, x: rx, y: ry + off, w: thick, h: len } : { it, x: rx + off, y: ry, w: len, h: thick });
          off += len;
        }
        if (rw >= rh) { rx += thick; rw -= thick; } else { ry += thick; rh -= thick; }
        sum -= s; rest = rest.slice(row.length);
      }
      return out;
    };
    const gs = groups.map(g => ({ ...g, size: g.items.reduce((a, b) => a + b.size, 0) })).filter(g => g.size > 0);
    const frag = document.createDocumentFragment();
    for (const gb of layout(gs, 0, 0, W, H)) {
      const head = gb.h > 40 && gb.w > 60 ? 13 : 0;
      for (const c of layout(gb.it.items, gb.x, gb.y + head, gb.w, gb.h - head)) {
        const d = document.createElement("div");
        Object.assign(d.style, { left: c.x + "px", top: c.y + "px", width: c.w + "px", height: c.h + "px", background: color(c.it.value) });
        if (c.w > 34 && c.h > 22) d.innerHTML = `${c.it.label}<small>${c.it.sub || ""}</small>`;
        d.title = `${c.it.label} ${c.it.sub || ""}`;
        d.onclick = () => onClick && onClick(c.it);
        frag.append(d);
      }
      const gd = document.createElement("div");
      gd.className = "g";
      Object.assign(gd.style, { left: gb.x + "px", top: gb.y + "px", width: gb.w + "px", height: gb.h + "px" });
      if (head) gd.textContent = gb.it.name;
      frag.append(gd);
    }
    el.append(frag);
  }

  window.TChart = TChart; window.BarChart = BarChart; window.spark = spark; window.treemap = treemap; window.bigNum = big;
})();
