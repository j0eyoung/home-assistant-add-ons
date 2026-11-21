// Season recap: a 15-second vertical (9:16) animation of the season so far, drawn on a canvas.
// Every frame is a pure function of time (renderAt(t)), so playing, replaying and saving a video all match.
// Shots: 0-1.5 title · 1.5-4 days on snow · 4-6.5 vertical · 6.5-9 top speed · 9-11.5 resorts ·
//        11.5-13.5 against last season · 13.5-15 end card (held about 1.2 s).
const Recap = (() => {
  const W = 1080, H = 1920, DUR = 15, M = 108;  // 10% side margin keeps text in the safe area
  // Fixed dark look (the app's dark tokens) so a saved video looks the same whatever the page theme
  const C = { bg: '#0d0d0d', ink: '#f0efec', ink2: '#c3c2b7', muted: '#898781', board: '#3987e5', ski: '#d95926', track: '#2c2c2a', accent: '#3987e5' };
  const FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif';
  const EVEREST_FT = 29032;
  let D = null, ctx = null, raf = 0, rec = null, keep = false;

  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const ease = x => 1 - Math.pow(1 - clamp(x), 3);                 // ease-out cubic
  const prog = (t, a, b) => ease((t - a) / (b - a));
  const fmt = n => Math.round(n).toLocaleString('en-US');
  // Shot visibility: in over 0.3 s from a, out over 0.25 s before b (the end card stays)
  const vis = (t, a, b, last = false) => clamp((t - a) / 0.3) * (last ? 1 : clamp((b - t) / 0.25));
  const lift = (t, a) => (1 - prog(t, a, a + 0.5)) * 40;            // text rises 40 px as it appears

  // Seeded snowfall: each flake's position depends only on t
  const FLAKES = (() => {
    let s = 20262027;
    const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
    return Array.from({ length: 140 }, () => ({ x: r() * W, y: r() * H, r: 2 + r() * 5, v: 50 + r() * 130, ph: r() * 6.28 }));
  })();

  function txt(s, x, y, size, color, { weight = 700, align = 'left', alpha = 1, spacing = 0 } = {}) {
    ctx.globalAlpha = alpha; ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = 'alphabetic';
    ctx.font = `${weight} ${size}px ${FONT}`;
    if ('letterSpacing' in ctx) ctx.letterSpacing = spacing + 'px';
    ctx.fillText(s, x, y);
    if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
    ctx.globalAlpha = 1;
  }
  const eyebrow = (s, y, a) => txt(s.toUpperCase(), M, y, 44, C.ink2, { weight: 600, alpha: a, spacing: 6 });
  function pill(x, y, w, h, color, a) {
    if (w <= 0) return;
    const r = Math.min(h / 2, w / 2);
    ctx.globalAlpha = a; ctx.fillStyle = color;
    ctx.beginPath(); ctx.roundRect ? ctx.roundRect(x, y, w, h, r) : ctx.rect(x, y, w, h); ctx.fill();
    ctx.globalAlpha = 1;
  }
  // Big number with a smaller unit after it
  function bigNumber(n, unit, y, a) {
    // Shrinks to fit a long number (say 250,000 ft) inside the side margins
    ctx.font = `600 80px ${FONT}`;
    const uw = unit ? ctx.measureText(unit).width + 24 : 0;
    ctx.font = `800 260px ${FONT}`;
    const size = Math.min(260, 260 * (W - 2 * M - uw) / ctx.measureText(n).width);
    txt(n, M, y, size, C.ink, { weight: 800, alpha: a });
    ctx.font = `800 ${size}px ${FONT}`;
    if (unit) txt(unit, M + ctx.measureText(n).width + 24, y, 80, C.ink2, { weight: 600, alpha: a });
  }

  function snow(t) {
    ctx.fillStyle = C.ink;
    for (const f of FLAKES) {
      const y = ((f.y + f.v * t) % (H + 20)) - 10, x = f.x + Math.sin(f.ph + t * 0.8) * 14;
      ctx.globalAlpha = 0.35; ctx.beginPath(); ctx.arc(x, y, f.r, 0, 6.2832); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function title(t) {
    const a = vis(t, 0.1, 1.5);
    if (!a) return;
    txt(D.season, W / 2, H * 0.44 + lift(t, 0.1), 220, C.ink, { weight: 800, align: 'center', alpha: a });
    txt('season so far', W / 2, H * 0.44 + 110 + lift(t, 0.45), 68, C.ink2, { weight: 500, align: 'center', alpha: a * clamp((t - 0.45) / 0.3) });
  }

  function days(t) {
    const a = vis(t, 1.5, 4.0), s = D.this;
    if (!a) return;
    eyebrow('Days on snow', 640, a);
    bigNumber(fmt(s.days * prog(t, 1.7, 2.7)), s.days === 1 ? 'day' : 'days', 920 + lift(t, 1.6), a);
    if (!s.days) { txt('No days logged yet', M, 1060, 56, C.ink2, { weight: 500, alpha: a }); return; }
    const full = W - 2 * M, g = prog(t, 2.6, 3.3), gap = s.board_days && s.ski_days ? 8 : 0;
    const bw = (full - gap) * (s.board_days / s.days) * g, sw = (full - gap) * (s.ski_days / s.days) * g;
    pill(M, 1010, full, 56, C.track, a);
    pill(M, 1010, bw, 56, C.board, a);
    pill(M + bw + gap, 1010, sw, 56, C.ski, a);
    const la = a * clamp((t - 3.0) / 0.3);
    pill(M, 1130, 36, 36, C.board, la);
    txt(`${s.board_days} on the board`, M + 56, 1162, 52, C.ink, { weight: 600, alpha: la });
    pill(M, 1210, 36, 36, C.ski, la);
    txt(`${s.ski_days} on skis`, M + 56, 1242, 52, C.ink, { weight: 600, alpha: la });
  }

  function vertical(t) {
    const a = vis(t, 4.0, 6.5), v = D.this.vertical_ft || 0;
    if (!a) return;
    eyebrow('Vertical', 640, a);
    if (!v) { txt('Vertical shows up once', M, 860, 72, C.ink, { alpha: a }); txt('Garmin is connected', M, 950, 72, C.ink, { alpha: a }); return; }
    bigNumber(fmt(v * prog(t, 4.2, 5.2)), 'ft', 920 + lift(t, 4.1), a);
    const ev = v / EVEREST_FT, ea = a * clamp((t - 5.2) / 0.3);
    txt(ev >= 1 ? `That's ${ev.toFixed(1)} times up Everest` : `That's ${Math.round(ev * 100)}% of the way up Everest`, M, 1060, 60, C.ink2, { weight: 500, alpha: ea });
  }

  function speed(t) {
    const a = vis(t, 6.5, 9.0), mph = D.this.top_speed_mph;
    if (!a) return;
    // Speed streak: a few thin lines sweeping across, each fading toward its tail
    const head = -300 + (W + 900) * prog(t, 6.6, 7.4);
    for (let k = 0; k < 3; k++) {
      const y = 1150 + k * 34, len = 520 - k * 120;
      for (let s = 0; s < 6; s++) {
        ctx.globalAlpha = a * (0.6 - s * 0.1) * (k ? 0.6 : 1); ctx.strokeStyle = C.accent; ctx.lineWidth = 6 - k * 1.5;
        ctx.beginPath(); ctx.moveTo(head - k * 60 - s * len / 6, y); ctx.lineTo(head - k * 60 - (s + 1) * len / 6, y); ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
    eyebrow('Top speed', 640, a);
    if (!mph) { txt('Top speed comes', M, 860, 72, C.ink, { alpha: a }); txt('from Garmin', M, 950, 72, C.ink, { alpha: a }); return; }
    bigNumber(fmt(mph * prog(t, 6.8, 7.6)), 'mph', 920 + lift(t, 6.6), a);
  }

  function resortsShot(t) {
    const a = vis(t, 9.0, 11.5), list = D.resorts.slice(0, 5);
    if (!a) return;
    eyebrow('Where you rode', 560, a);
    if (!list.length) { txt('No resorts yet', M, 700, 72, C.ink, { alpha: a }); return; }
    const max = Math.max(...list.map(r => r.days)), full = W - 2 * M;
    list.forEach((r, i) => {
      const y = 700 + i * 190, at = 9.2 + i * 0.12, ra = a * clamp((t - at) / 0.3);
      txt(r.resort, M, y, 58, C.ink, { weight: 700, alpha: ra });
      txt(`${r.days} ${r.days === 1 ? 'day' : 'days'}`, W - M, y, 50, C.ink2, { weight: 600, align: 'right', alpha: ra });
      pill(M, y + 30, full, 34, C.track, ra);
      pill(M, y + 30, full * (r.days / max) * prog(t, at, at + 0.6), 34, C.board, ra);
    });
    const more = D.resorts.length - list.length;
    if (more > 0) txt(`+${more} more`, M, 700 + 5 * 190, 50, C.ink2, { weight: 500, alpha: a * clamp((t - 10.0) / 0.3) });
  }

  function versus(t) {
    const a = vis(t, 11.5, 13.5);
    if (!a) return;
    eyebrow('Against last season, same date', 640, a);
    if (!D.has_last) { txt('Your first season', M, 860, 80, C.ink, { alpha: a }); txt('in the log', M, 960, 80, C.ink, { alpha: a }); return; }
    const rows = [['Days', D.this.days, D.last.days, ''], ['Vertical', D.this.vertical_ft || 0, D.last.vertical_ft || 0, ' ft']];
    rows.forEach(([label, now, then, unit], i) => {
      const y = 800 + i * 400, ra = a * clamp((t - (11.6 + i * 0.25)) / 0.3), d = now - then;
      txt(label, M, y, 56, C.ink2, { weight: 600, alpha: ra });
      txt(fmt(now) + unit, M, y + 150, 140, C.ink, { weight: 800, alpha: ra });
      // Up or down is said in words and an arrow, not colour
      const delta = d === 0 ? 'Same as last season' : `${d > 0 ? '▲' : '▼'} ${fmt(Math.abs(d))}${unit} ${d > 0 ? 'more' : i ? 'less' : 'fewer'}`;
      txt(delta, M, y + 230, 52, C.ink, { weight: 600, alpha: ra });
      txt(`Last season by now: ${fmt(then)}${unit}`, M, y + 295, 44, C.ink2, { weight: 500, alpha: ra });
    });
  }

  function endCard(t) {
    const a = vis(t, 13.5, DUR, true);
    if (!a) return;
    // Snowflake mark, the same drawing as the app's Forecast tab icon
    const cx = W / 2, cy = H * 0.38, s = 6;
    ctx.globalAlpha = a; ctx.strokeStyle = C.accent; ctx.lineWidth = 10; ctx.lineCap = 'round';
    ctx.beginPath();
    for (const [x1, y1, x2, y2] of [[12, 2, 12, 22], [3.3, 7, 20.7, 17], [3.3, 17, 20.7, 7], [9.5, 3.5, 12, 6], [12, 6, 14.5, 3.5], [9.5, 20.5, 12, 18], [12, 18, 14.5, 20.5]]) {
      ctx.moveTo(cx + (x1 - 12) * s * 2, cy + (y1 - 12) * s * 2); ctx.lineTo(cx + (x2 - 12) * s * 2, cy + (y2 - 12) * s * 2);
    }
    ctx.stroke(); ctx.globalAlpha = 1;
    txt('Ski Assistant', W / 2, H * 0.52 + lift(t, 13.5), 110, C.ink, { weight: 800, align: 'center', alpha: a });
    const when = new Date(D.as_of + 'T12:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
    txt(`${D.season} season · as of ${when}`, W / 2, H * 0.52 + 90, 48, C.ink2, { weight: 500, align: 'center', alpha: a * clamp((t - 13.8) / 0.3) });
  }

  function renderAt(t) {
    ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
    snow(t);
    title(t);
    ctx.save(); ctx.translate(0, 110);   // data shots sit a little lower so they centre on the screen
    days(t); vertical(t); speed(t); resortsShot(t); versus(t);
    ctx.restore();
    endCard(t);
  }

  // Plain-text version of the recap, for screen readers
  function summary() {
    const s = D.this, bits = [`${D.season} season so far: ${s.days} days on snow (${s.board_days} board, ${s.ski_days} ski)`];
    if (s.vertical_ft) bits.push(`${fmt(s.vertical_ft)} ft vertical`);
    if (s.top_speed_mph) bits.push(`top speed ${s.top_speed_mph} mph`);
    if (D.resorts.length) bits.push('resorts: ' + D.resorts.map(r => `${r.resort} ${r.days}`).join(', '));
    if (D.has_last) bits.push(`last season by this date: ${D.last.days} days`);
    return bits.join('; ') + '.';
  }

  function play(onEnd) {
    cancelAnimationFrame(raf);
    const t0 = performance.now();
    const step = () => {
      const t = (performance.now() - t0) / 1000;
      renderAt(Math.min(t, DUR));
      if (t < DUR) raf = requestAnimationFrame(step);
      else if (typeof onEnd === 'function') onEnd();
    };
    raf = requestAnimationFrame(step);
  }

  async function open() {
    const dlg = $('recapdlg'), cv = $('recapcv'), msg = $('recapmsg');
    msg.textContent = '';
    try { D = await api('recap'); } catch (e) { alert('Season recap: ' + e.message); return; }
    ctx = cv.getContext('2d');
    cv.setAttribute('aria-label', 'Season recap. ' + summary());
    dlg.showModal();
    await document.fonts.ready;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) renderAt(3.6);  // still frame; Replay plays it
    else play();
  }

  function close() {
    cancelAnimationFrame(raf);
    if (rec && rec.state === 'recording') { keep = false; rec.stop(); }
    $('recapdlg').close();
  }

  function save() {
    const btn = $('recapsave'), msg = $('recapmsg');
    const types = ['video/mp4;codecs=avc1', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm'];
    const type = window.MediaRecorder && types.find(x => MediaRecorder.isTypeSupported(x));
    if (!type) { msg.textContent = 'This browser can’t record video. Try Chrome or Edge on a computer.'; return; }
    const chunks = [];
    rec = new MediaRecorder($('recapcv').captureStream(30), { mimeType: type, videoBitsPerSecond: 8e6 });
    rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
    rec.onstop = () => {
      btn.disabled = false;
      if (!keep) { msg.textContent = ''; rec = null; return; }
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob(chunks, { type: type.split(';')[0] }));
      a.download = `ski-recap-${D.season.replace('/', '-')}.${type.includes('mp4') ? 'mp4' : 'webm'}`;
      document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
      msg.textContent = `Saved ${a.download}.`; rec = null;
    };
    keep = true; btn.disabled = true; msg.textContent = 'Recording the 15 seconds…';
    rec.start();
    play(() => setTimeout(() => rec && rec.state === 'recording' && rec.stop(), 150));
  }

  return { open, close, play: () => play(), save, renderAt: t => renderAt(t), get data() { return D; } };
})();
