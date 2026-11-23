"use strict";
// Cook mode: full screen, big type, the screen stays awake, one step at a time, tap a time in a step to time it.

const TIME_RE = /(\d+(?:[.,]\d+)?|an?|one|half an?)(?:\s*(?:-|–|to)\s*(\d+(?:[.,]\d+)?))?\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b/gi;
const timers = [];       // {id, label, end, left, paused, done}
let tick = null, audio = null;

function secsOf(n, unit) {
  const v = /^an?$|^one$/i.test(n) ? 1 : /^half/i.test(n) ? 0.5 : parseFloat(String(n).replace(",", "."));
  const u = unit.toLowerCase();
  return Math.round(v * (u.startsWith("h") ? 3600 : u.startsWith("s") ? 1 : 60));
}
function withTimers(text) {
  return esc(text).replace(TIME_RE, (m, a, b, unit) => {
    const s = secsOf(a, unit);
    return s >= 10 && s <= 6 * 3600 ? `<button type="button" class="time-chip" data-timer="${s}" data-label="${esc(m)}">${icon("timer")}${m}</button>` : m;
  });
}
const clock = s => { s = Math.max(0, Math.ceil(s)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60; return h ? `${h}:${pad(m)}:${pad(x)}` : `${m}:${pad(x)}`; };

function startTimer(secs, label) {
  try { audio = audio || new (window.AudioContext || window.webkitAudioContext)(); audio.resume(); } catch (e) {}
  timers.push({ id: Date.now() + Math.random(), label, end: Date.now() + secs * 1000, left: secs, paused: false, done: false });
  haptic(20);
  drawTimers();
  if (!tick) tick = setInterval(stepTimers, 500);
}
function stepTimers() {
  const now = Date.now();
  for (const t of timers) {
    if (t.paused || t.done) continue;
    t.left = (t.end - now) / 1000;
    if (t.left <= 0) { t.done = true; ring(t); }
  }
  if (!timers.length) { clearInterval(tick); tick = null; }
  drawTimers();
}
function ring(t) {
  haptic([400, 160, 400, 160, 400]);
  toast(`Time's up: ${t.label}`, { ms: 8000 });
  if (!audio) return;
  try {
    for (let i = 0; i < 3; i++) {
      const o = audio.createOscillator(), g = audio.createGain(), at = audio.currentTime + i * 0.45;
      o.frequency.value = 880; o.connect(g); g.connect(audio.destination);
      g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(0.25, at + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, at + 0.3);
      o.start(at); o.stop(at + 0.32);
    }
  } catch (e) {}
}
function drawTimers() {
  const box = $("#timers");
  box.classList.toggle("show", timers.length > 0);
  box.innerHTML = timers.map(t => `<div class="tmr ${t.done ? "ring" : ""} ${t.paused ? "paused" : ""}">
    <button type="button" class="tmr-main" data-t="${t.id}" aria-label="${t.done ? "Dismiss" : t.paused ? "Resume" : "Pause"} timer ${esc(t.label)}">
      ${icon(t.done ? "check" : t.paused ? "play" : "timer")}<span class="tl">${esc(t.label)}</span><b>${t.done ? "Done" : clock(t.left)}</b></button>
    ${t.done ? "" : `<button type="button" class="tmr-x" data-tx="${t.id}" aria-label="Cancel timer ${esc(t.label)}">${icon("x")}</button>`}</div>`).join("");
}
$("#timers").addEventListener("click", e => {
  const m = e.target.closest("[data-t]"), x = e.target.closest("[data-tx]");
  const i =timers.findIndex(t => t.id === +(m ? m.dataset.t : x ? x.dataset.tx : NaN));
  if (i < 0) return;
  const t = timers[i];
  if (x || t.done) timers.splice(i, 1);
  else if (t.paused) { t.paused = false; t.end = Date.now() + t.left * 1000; }
  else { t.paused = true; t.left = (t.end - Date.now()) / 1000; }
  drawTimers();
});

async function wakeLock() {
  try { return navigator.wakeLock ? await navigator.wakeLock.request("screen") : null; } catch (e) { return null; }
}

async function openCook(r, ctx = {}) {
  flushLater();
  const ings = (r.ingredients || []).filter(i => i && i.name), steps = r.steps || [];
  const have = new Set();
  let step = ings.length ? -1 : 0;            // -1: get the ingredients out first
  let lock = await wakeLock();
  const relock = async () => { if (!document.hidden && ov.isConnected) lock = await wakeLock(); };
  const ov = document.createElement("div");
  ov.className = "cook";
  ov.setAttribute("role", "dialog"); ov.setAttribute("aria-modal", "true"); ov.setAttribute("aria-label", "Cooking " + r.name);
  document.body.appendChild(ov);
  document.body.classList.add("cooking");
  document.addEventListener("visibilitychange", relock);
  const n = ctx.servings || r.servings || 1;

  const close = () => {
    document.removeEventListener("visibilitychange", relock);
    document.removeEventListener("keydown", keys);
    try { lock && lock.release(); } catch (e) {}
    ov.remove(); document.body.classList.remove("cooking");
    render({ keepScroll: true });
  };
  const finish = async () => {
    if (ctx.date && !ctx.cooked && !ctx.leftover) {
      try {
        const res = await api("plan/cooked", "POST", { date: ctx.date, slot: ctx.slot });
        toast(res.changed && res.changed.length ? "Enjoy. Used from the pantry: " + res.changed.map(c => c.name).join(", ") : "Enjoy. Marked as cooked.", { ms: 6000 });
      } catch (e) { toast(e.message); }
    } else toast("Enjoy.");
    close();
  };
  const draw = () => {
    const total = steps.length, pct = total ? Math.max(0, step + 1) / total * 100 : 100;
    const sub = step < 0 ? `Get everything out · for ${n}` : total ? `Step ${step + 1} of ${total} · for ${n}` : `for ${n}`;
    ov.innerHTML = `
      <header class="cook-top">
        <button type="button" class="icon-btn quiet" data-x aria-label="Leave cook mode">${icon("x")}</button>
        <div class="cook-title"><h2>${esc(r.name)}</h2><p>${esc(sub)}${lock ? " · screen stays on" : ""}</p></div>
        <button type="button" class="icon-btn quiet" data-ings aria-label="Ingredients">${icon("list")}</button>
      </header>
      <div class="cook-progress" aria-hidden="true"><i style="width:${pct}%"></i></div>
      <main class="cook-main" tabindex="-1">
        ${step < 0 ? `<h3 class="cook-h">Ingredients</h3><ul class="cook-ings">${ings.map((i, k) => `<li><button type="button" class="tick ${have.has(k) ? "on" : ""}" data-have="${k}" aria-pressed="${have.has(k)}">
              <span class="box">${icon("check")}</span><span class="q">${esc(amount(i.qty, i.unit))}</span><span class="n">${esc(i.name)}</span></button></li>`).join("")}</ul>`
          : total ? `<p class="cook-step">${withTimers(steps[step])}</p>` : `<p class="cook-step">No steps saved for this recipe.</p>`}
      </main>
      <footer class="cook-nav">
        <button type="button" class="btn line big" data-prev ${step <= (ings.length ? -1 : 0) ? "disabled" : ""}>${icon("chev-left")} Back</button>
        ${step >= total - 1 && step >= 0 ? `<button type="button" class="btn herb big" data-done>${icon("check")} ${ctx.date && !ctx.cooked ? "Done, mark cooked" : "Done"}</button>`
          : `<button type="button" class="btn primary big" data-next>${step < 0 ? "Start cooking" : "Next step"} ${icon("chev-right")}</button>`}
      </footer>`;
    $(".cook-main", ov).focus({ preventScroll: true });
  };
  const move = d => { const lo = ings.length ? -1 : 0; const nx = Math.max(lo, Math.min(steps.length - 1, step + d)); if (nx !== step) { step = nx; draw(); } };
  ov.addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.matches("[data-x]")) close();
    else if (b.matches("[data-next]")) move(1);
    else if (b.matches("[data-prev]")) move(-1);
    else if (b.matches("[data-done]")) finish();
    else if (b.matches("[data-have]")) { const k = +b.dataset.have; have.has(k) ? have.delete(k) : have.add(k); haptic(8); b.classList.toggle("on"); b.setAttribute("aria-pressed", have.has(k)); }
    else if (b.matches("[data-timer]")) startTimer(+b.dataset.timer, b.dataset.label);
    else if (b.matches("[data-ings]")) sheet({ title: "Ingredients", body: `<ul class="ing">${ings.map(i => `<li><span class="q">${esc(amount(i.qty, i.unit))}</span><span class="n">${esc(i.name)}</span></li>`).join("")}</ul>` });
  });
  let x0 = null;
  ov.addEventListener("touchstart", e => { x0 = e.target.closest(".cook-main") ? e.touches[0].clientX : null; }, { passive: true });
  ov.addEventListener("touchend", e => { if (x0 == null) return; const dx = e.changedTouches[0].clientX - x0; if (Math.abs(dx) > 70) move(dx < 0 ? 1 : -1); x0 = null; }, { passive: true });
  const keys = e => {
    if (sheets.length) return;
    if (e.key === "ArrowRight") move(1);
    if (e.key === "ArrowLeft") move(-1);
    if (e.key === "Escape") close();
  };
  document.addEventListener("keydown", keys);
  draw();
}
