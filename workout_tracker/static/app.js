"use strict";
// Phone-first workout UI. Taps update the page instantly; the server is only called to load data
// and save. Every URL is relative so the page works behind Home Assistant ingress.

const $view = document.getElementById("view");
const $date = document.getElementById("date");
const $save = document.getElementById("save-state");
const $toast = document.getElementById("toast");
const $title = document.getElementById("page-title");
const $lhSub = document.getElementById("lh-sub");
const $lhScores = document.getElementById("lh-scores");
const $back = document.getElementById("back");

// One drawn icon set, one stroke (styled by .ico in app.css)
const svg = (d) => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
const I = {
  play: svg('<path d="M8 5.5v13l10-6.5z"/>'),
  check: svg('<path d="M4.5 12.5l5 5 10-11"/>'),
  down: svg('<path d="M6 9.5l6 6 6-6"/>'),
  up: svg('<path d="M6 14.5l6-6 6 6"/>'),
  next: svg('<path d="M9.5 6l6 6-6 6"/>'),
  close: svg('<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>'),
  plus: svg('<path d="M12 5.5v13M5.5 12h13"/>'),
  again: svg('<path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3M4.5 4.5v3.7h3.7"/>'),
  star: svg('<path d="M12 3.8l2.5 5.1 5.6.8-4 3.9.9 5.6-5-2.6-5 2.6.9-5.6-4-3.9 5.6-.8z"/>'),
  pin: svg('<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>'),
  history: svg('<path d="M3.5 12a8.5 8.5 0 1 0 2.5-6M3.5 4v4h4M12 7.5V12l3 2"/>'),
  report: svg('<rect x="5" y="3.5" width="14" height="17" rx="2"/><path d="M8.5 8h7M8.5 11.5h7M8.5 15h4"/>'),
  library: svg('<path d="M5 4.5h4v15H5zM10 4.5h4v15h-4zM15.2 5.2l3.8-1 3 14.5-3.8 1z"/>'),
  camera: svg('<path d="M4 8.5h3.2L8.8 6h6.4l1.6 2.5H20v10.5H4z"/><circle cx="12" cy="13.5" r="3.3"/>'),
  chart: svg('<path d="M4 4.5v15h16"/><path d="M7.5 15l3.5-4 3 2.5 4.5-6"/>'),
  settings: svg('<circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M5.5 18.5l1.7-1.7M16.8 7.2l1.7-1.7"/>'),
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const num = (v) =>(v === "" || v === null || v === undefined || Number.isNaN(Number(v)) ? null : Number(v));
const store = {
  get(key, fallback) { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ } },
  remove(key) { try { localStorage.removeItem(key); } catch { /* private mode */ } },
};

async function api(path, options = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) {
    const err = new Error(await res.text());
    err.status = res.status;
    throw err;
  }
  return res.json();
}

let toastTimer;
function toast(text) {
  $toast.textContent = text;
  $toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $toast.classList.remove("show"), 2600);
}

function setSaveState(text, error = false) {
  $save.textContent = text;
  $save.classList.toggle("error", error);
}

const FINISH_DEFAULTS = { rpe: 5, pf: 1, kidney: 1, notes: "", rpe2: 5, notes2: "" };
const state = {
  tab: "today",
  status: null,
  plan: null,
  sets: {},        // exercise name -> [{weight, reps, done}]
  extras: [],      // exercises added by hand
  checks: {},      // warm-up item -> done
  finish: { ...FINISH_DEFAULTS },
  open: new Set(), // expanded how-to / history / library panels
  history: null,
  progress: { exercise: "" },
  prog: {},        // exercise name -> its progress (api/progress), shared by History and Today's cards
  progQ: "",
  coach: [],       // the chat is kept on the add-on (shared by every device); loadCoach() fills this
  coachLoaded: false,
  coachBusy: false,   // this device is waiting for a reply
  coachRemoteBusy: false,   // another device is waiting for one
  mind: null, mindFilter: "all", mindQ: "",
  week: null, weekOffset: 0, coachDraft: "", secondOpen: false, ck: null, ckEdit: false, snowOpen: false, snow: null,
  garmin: null, garminMsg: "", ha: null,
  cardioGarmin: [],   // today's watch activities ticked to log as today's cardio
  trends: null, trendDays: 30, report: null, reportDays: 30, ski: null, skiOpen: false, skiVals: {}, ptForm: null, install: null,
  bio: null, bioForm: null, questions: null, qSuggest: null, body: null, bodyForm: null, waterHist: null, bodySensors: null, bodyMsg: "",
  voices: null, voice: "lessac", audio: null,
  med: null, medFilter: "all", medShown: 10, medMinutes: 5, medFocus: "", medScript: "", medBusy: false, medError: "",
  lib: { q: "", focus: "", muscle: "", equipment: "", pictures: true, filtered: false, data: null, results: [], offset: 0 },
};

// --- Shared pieces --------------------------------------------------------------------------

function pictures(urls, note) {
  if (!urls || !urls.length) return "";
  // Start picture last so it is on top when the flip animation begins
  const imgs = [...urls].reverse().map((u) => `<img src="${esc(u)}" alt="" loading="lazy">`).join("");
  return `<div class="flip${urls.length > 1 ? " two" : ""}">${imgs}</div>` + (note ? `<div class="sub">${esc(note)}</div>` : "");
}

function hasHowTo(ex) {
  return Boolean(ex.images?.length || ex.steps?.length || ex.warning || ex.tips?.length);
}

function howTo(ex) {
  const facts = [ex.muscles?.join(", "), ex.equipment, ex.level, ex.sources?.length && `Sources: ${ex.sources.join(", ")}`]
    .filter(Boolean).map(esc).join(" · ");
  return `<div class="howto">
    ${ex.warning ? `<div class="warning">${esc(ex.warning)}</div>` : ""}
    ${pictures(ex.images, ex.image_note)}
    ${ex.credit ? `<div class="small muted">${esc(ex.credit)}</div>` : ""}
    ${ex.gallery?.length > 2 ? `<div class="gallery">${ex.gallery.slice(2).map((u) => `<img src="${esc(u)}" alt="" loading="lazy">`).join("")}</div>` : ""}
    ${ex.dose ? `<div><strong>${esc(ex.dose)}</strong></div>` : ""}
    ${ex.steps?.length ? `<ol>${ex.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>` : ""}
    ${ex.tips?.length ? `<p class="small muted">Tips: ${esc(ex.tips.join(" "))}</p>` : ""}
    ${facts ? `<p class="small muted">${facts}</p>` : ""}
  </div>`;
}

function toggleButton(key, label = "How to") {
  return `<button type="button" class="btn link" data-act="toggle" data-key="${esc(key)}" aria-expanded="${state.open.has(key)}">
    ${label} ${state.open.has(key) ? I.up : I.down}</button>`;
}

function formatDate(iso) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

// --- Today ------------------------------------------------------------------------------------

const finishKey = () => `finish-${state.plan?.date}`;

// --- Offline: what you log is kept on the phone until Home Assistant has it ------------------------------------------
// Every change to today's sets and ticks is copied here first; the copy is dropped once the add-on has saved it.
// A workout completed with no connection waits in an outbox and is sent (with its date) when the phone is back online.
const unsentKey = (date) => `unsent-draft-${date}`;
const OUTBOX = "outbox-complete";
const offline = (err) => !err.status;     // fetch itself failed: no connection (the add-on answering with an error has a status)

function keepUnsent() {
  if (state.plan) store.set(unsentKey(state.plan.date), { tracker: draftRows(), checks: state.checks, at: Date.now() });
}

function dropOldUnsent(today) {
  try {
    Object.keys(localStorage).filter((k) => k.startsWith("unsent-draft-") && k !== unsentKey(today)).forEach((k) => localStorage.removeItem(k));
  } catch { /* private mode */ }
}

function loadPlan(plan) {
  dropOldUnsent(plan.date);
  const unsent = store.get(unsentKey(plan.date), null);
  if (unsent && !plan.done?.["1"]) plan = { ...plan, draft: { tracker: unsent.tracker, checks: unsent.checks } };
  else if (unsent) store.remove(unsentKey(plan.date));
  state.plan = plan;
  state.checks = { ...(plan.draft?.checks || {}) };
  state.sets = {};
  for (const r of plan.draft?.tracker || []) {
    const name = r.exercise || "Custom";
    (state.sets[name] ||= []).push({ weight: r.weight || "", reps: r.reps || "", done: Boolean(r.done) });
  }
  for (const ex of plan.strength) {
    if (!state.sets[ex.name]) {
      // Pre-fill today's suggested weight and reps; an easy week has one set fewer
      const p = ex.progress;
      const count = Math.max(1, (ex.sets || 3) + (p?.sets_delta || 0));
      state.sets[ex.name] = Array.from({ length: count }, () => ({ weight: p?.weight ?? "", reps: p?.reps ?? "", done: false }));
    }
  }
  state.extras = Object.keys(state.sets).filter((n) => !plan.strength.some((e) => e.name === n));
  const watch = (plan.garmin_acts?.cardio || []).map((a) => a.activity_id);
  state.cardioGarmin = store.get(`garmin-cardio-${plan.date}`, []).filter((id) => watch.includes(id));
  state.finish = { ...FINISH_DEFAULTS, ...store.get(finishKey(), {}) };
  if (plan.checkin && !store.get(finishKey(), null)) {   // start the finish sliders from this morning's check-in
    state.finish.kidney = plan.checkin.kidney;
    state.finish.pf = plan.checkin.pelvic_floor;
  }
  $date.textContent = formatDate(plan.date);
  for (const q of store.get(OUTBOX, [])) {   // a workout waiting to be sent shows as done, not as a plan to do again
    if (q.date === plan.date && !plan.done?.[String(q.session)]) plan.done = { ...plan.done, [q.session]: q.summary };
  }
  letterhead();
  if (unsent && !plan.done?.["1"]) scheduleSave();
}

// The teal letterhead: page name and date; on Today also the kind of day and this morning's two scores
const TAB_TITLES = { today: "Today", week: "Week", coach: "Coach", mind: "Mind & Body", more: "Records",
  history: "History", report: "PT report", library: "Library", settings: "Settings" };

function letterhead() {
  const p = state.plan;
  $back.hidden = !MORE_TABS.includes(state.tab);
  if (state.tab !== "today" || !p) {
    $title.textContent = TAB_TITLES[state.tab] || "Workouts";
    $date.textContent = p ? formatDate(p.date) : "";
    $lhSub.textContent = "";
    $lhScores.innerHTML = "";
    return;
  }
  // On Today the date is the headline, as at the top of the printed program (the tab bar already says "Today")
  $title.textContent = new Date(`${p.date}T12:00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });
  $date.textContent = "";
  const day = p.day || {};
  const bits = [day.label, day.block_week ? `${p.phase}, week ${day.block_week} of your 4-week plan` : p.phase];
  $lhSub.textContent = bits.filter(Boolean).join(" · ");
  const ck = p.checkin;
  // a skiing or snowboarding day replaces the workout, so its prompt sits with the day's status, not in the program
  const snow = p.snow_sport && !p.snow_today && !state.snowOpen && !p.done?.["1"]
    ? `<button type="button" class="score snow" data-act="snow-toggle">Snow day?</button>` : "";
  $lhScores.innerHTML = (ck ? `<button type="button" class="score" data-act="checkin-edit" aria-label="Kidney ${esc(ck.kidney)} of 10. Change this morning's check-in">
      <b>${esc(ck.kidney)}</b><span>/10 kidney</span></button>
    <button type="button" class="score" data-act="checkin-edit" aria-label="Pelvic floor ${esc(ck.pelvic_floor)} of 10. Change this morning's check-in">
      <b>${esc(ck.pelvic_floor)}</b><span>/10 pelvic floor</span></button>` : "") + snow;
}

// "2 x 10-12, light and slow. Stop if..." -> a boxed dose ("2 × 10–12") and the rest as a note
function splitDose(dose) {
  const m = String(dose || "").match(/^\s*(\d+\s*[x×]\s*\d+(?:\s*[-–]\s*\d+)?(?:\s*(?:s|sec|min|reps?))?(?:\s+each (?:side|leg|way))?(?:\s*hold)?)[,.;:]?\s*(.*)$/i);
  if (!m) return String(dose || "").length <= 26 ? { box: dose || "", note: "" } : { box: "", note: dose };
  const note = m[2].charAt(0).toUpperCase() + m[2].slice(1);
  return { box: m[1].replace(/\s*[x×]\s*/i, " × ").replace(/\s*[-–]\s*/, "–"), note };
}

async function refreshPlan() {
  loadPlan(await api("api/plan"));
  if (state.tab === "today") render();
}

function draftRows() {
  const rows = [];
  for (const [exercise, sets] of Object.entries(state.sets)) {
    sets.forEach((s, i) => rows.push({ exercise, set: i + 1, weight: num(s.weight), reps: num(s.reps), done: s.done }));
  }
  return rows;
}

let saveTimer = null;
function scheduleSave() {
  keepUnsent();
  setSaveState("Saving…");
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveDraft, 700);
}

async function saveDraft() {
  clearTimeout(saveTimer);
  saveTimer = null;
  if (!state.plan) return;
  const date = state.plan.date;
  const body = JSON.stringify({ date, tracker: draftRows(), checks: state.checks });
  try {
    await api("api/draft", { method: "PUT", body });
    // drop the phone's copy only if nothing changed while it was on its way
    if (state.plan?.date === date && JSON.stringify({ date, tracker: draftRows(), checks: state.checks }) === body) store.remove(unsentKey(date));
    setSaveState("Saved");
  } catch (err) {
    if (err.status === 409) {
      store.remove(unsentKey(date));
      toast("A new day has started: loading today's plan");
      await refreshPlan();
    } else {
      setSaveState(offline(err) ? "No connection: kept on this phone" : "Not saved yet, retrying…", !offline(err));
      saveTimer = setTimeout(saveDraft, offline(err) ? 15000 : 5000);
    }
  }
}

function exerciseFor(name) {
  return state.plan.strength.find((e) => e.name === name)
    || { name, dose: null, sets: 1, why: null, images: [], steps: [], tips: [], warning: null };
}

// One numbered row of the program: picture, name, the boxed dose, last time and today's target in ballpoint, set boxes
function strengthCard(ex, idx) {
  const sets = state.sets[ex.name] || [];
  const done = sets.filter((s) => s.done).length;
  const key = `s:${ex.name}`;
  const sameLast = ex.progress?.sets?.length && !ex.hold && sets.some((s) => !s.done);
  const dose = splitDose(ex.dose);
  // the box shows today's dose: an easy week's one set fewer matches the set boxes below it
  if (sets.length && /^\d+ ×/.test(dose.box)) dose.box = dose.box.replace(/^\d+/, String(sets.length));
  const thumb = ex.images?.[0];
  const next = sets.findIndex((s) => !s.done);
  return `<div class="card" data-card="${esc(key)}">
    <div class="ex-head${thumb ? " has-thumb" : ""}">
      <span class="idx">${esc(idx || "")}</span>
      ${thumb ? `<img class="thumb" src="${esc(thumb)}" alt="" loading="lazy">` : ""}
      <div><div class="ex-name">${esc(ex.name)}${ex.pt ? ` <span class="badge pt">PT</span>` : ""}</div>
        ${dose.box ? `<span class="dose">${esc(dose.box)}</span>` : ""}${sets.length ? ` <span class="small muted">${done} of ${plural(sets.length, ex.hold ? "hold" : "set")} done</span>` : ""}
        ${dose.note ? `<div class="dose-note">${esc(dose.note)}</div>` : ""}
        ${!ex.dose ? `<div class="dose-note">Your own exercise</div>` : ""}</div>
    </div>
    ${ex.why ? `<div class="why">${esc(ex.why)}</div>` : ""}
    ${ex.bothered ? `<div class="warning" style="margin-top:8px">${esc(ex.bothered)}</div>` : ""}
    ${ex.progress ? `<div class="progress"><span class="last">Last time, ${esc(formatDate(ex.progress.date))}: <span class="pen">${esc(ex.progress.last)}</span></span>
      <strong>${esc(ex.progress.note)}</strong></div>` : ""}
    ${hasHowTo(ex) ? toggleButton(key) + (state.open.has(key) ? howTo(ex) : "") : ""}
    ${ex.progress ? toggleButton(`p:${ex.name}`, "Progress") + (state.open.has(`p:${ex.name}`) ? `<div class="chart prog-inline">${state.prog[ex.name]
      ? progressBody(state.prog[ex.name]) : `<div class="spinner">Loading…</div>`}</div>` : "") : ""}
    ${ex.hold ? `<p class="small muted" style="margin:6px 0">Tap a hold to start its ${esc(ex.hold_secs || 30)} s timer. It ticks itself off and starts your rest.</p>` : ""}
    <div class="sets">${ex.hold ? holdRow(ex, sets) : sets.map((s, i) => setRow(ex.name, s, i, i === next)).join("")}</div>
    <div class="row-actions">${sameLast ? `<button type="button" class="btn small" data-act="same-last" data-name="${esc(ex.name)}">${I.again}Same as last time</button>` : ""}
      <button type="button" class="btn small" data-act="add-set" data-name="${esc(ex.name)}">${I.plus}${ex.hold ? "Add hold" : "Add set"}</button>
      ${ex.hold && sets.length > 1 ? `<button type="button" class="btn link small" data-act="remove-set" data-name="${esc(ex.name)}" data-i="${sets.length - 1}">Remove last</button>` : ""}
      ${ex.dose && !(state.plan.session2 || []).includes(ex.name) ? `<button type="button" class="btn link small muted-link" data-act="swap" data-name="${esc(ex.name)}">Swap</button>` : ""}
      ${ex.dose ? `<button type="button" class="btn link small muted-link" data-act="bothered" data-name="${esc(ex.name)}">Bothered me</button>` : ""}</div>
  </div>`;
}

// Timed holds drawn to length (a 45 s hold is longer than a 20 s one), with the rest after each as a thin line
function holdRow(ex, sets) {
  const len = (secs) => `${Math.max(28, Math.min(100, Math.round((secs / 120) * 100)))}%`;
  const hold = Number(ex.hold_secs) || 30, rest = Number(ex.rest_secs) || 45;
  const next = sets.findIndex((s) => !s.done);
  return `<div class="holds">${sets.map((s, i) => `<button type="button" class="holdbtn${s.done ? " on" : i === next ? " next" : ""}" style="--len:${len(hold)}"
    data-act="done" data-name="${esc(ex.name)}" data-i="${i}" aria-pressed="${s.done}" aria-label="Hold ${i + 1}, ${hold} seconds${s.done ? ", done" : ""}">
    <span>${i + 1}</span><span>${fmtSecs(hold)}</span></button>
    ${i < sets.length - 1 ? `<div class="rest-line" style="--len:${len(rest)}" title="${rest} s rest"></div>` : ""}`).join("")}</div>`;
}

function setRow(name, s, i, isNext) {
  const attrs = `data-name="${esc(name)}" data-i="${i}"`;
  // Bodyweight moves, bands and the like only track reps; your own added exercises keep the weight box
  const weighted = exerciseFor(name).weighted !== false;
  return `<div class="set${weighted ? "" : " noweight"}${isNext ? " next" : ""}${s.done ? " isdone" : ""}">
    <button type="button" class="done${s.done ? " on" : ""}" data-act="done" ${attrs} aria-pressed="${s.done}" aria-label="Set ${i + 1} done"></button>
    <span class="n">${i + 1}</span>
    ${weighted ? `<label><input type="number" inputmode="decimal" min="0" step="2.5" value="${esc(s.weight)}" data-field="weight" ${attrs} aria-label="Set ${i + 1} weight in pounds"><span class="unit">lb</span></label>` : ""}
    <label><input type="number" inputmode="numeric" min="0" step="1" value="${esc(s.reps)}" data-field="reps" ${attrs} aria-label="Set ${i + 1} reps"><span class="unit">reps</span></label>
    <button type="button" class="remove" data-act="remove-set" ${attrs} aria-label="Remove set ${i + 1}">${I.close}</button>
  </div>`;
}

// Cardio minutes as a measured rule, drawn to the same scale every day (45 min fills the line): a tick every
// 5 minutes, longer ticks every 15, the warm-up's first 5 minutes highlighted, the length written at the end
function minutesRule(min, warmup) {
  const MAX = 45, W = 250;   // with the label room this draws at about 1:1 in a phone card, so the labels stay 12px
  const len = Math.max(24, Math.round((W * Math.min(min, MAX)) / MAX));
  const per = len / Math.min(min, MAX);
  const ticks = [];
  for (let m = 0; m <= Math.min(min, MAX); m += 5) {
    const x = Math.round(m * per);
    ticks.push(`<line class="tick" x1="${x}" y1="${m % 15 === 0 ? 6 : 11}" x2="${x}" y2="18"/>`);
  }
  const warm = warmup && min >= 10 ? `<rect class="warm" x="0" y="13" width="${Math.round(5 * per)}" height="5"/><text x="0" y="32">warm-up</text>` : "";
  return `<svg class="min-rule" viewBox="0 0 ${W + 60} 34" preserveAspectRatio="xMinYMid meet" role="img" aria-label="${min} minutes">
    ${warm}<line class="base" x1="0" y1="18" x2="${len}" y2="18"/>${ticks.join("")}<text class="end" x="${len + 6}" y="22">${min} min</text></svg>`;
}

// An exercise sitting out because it bothered you: printed as a greyed row so the plan stays honest about it
function pausedRow(p, idx) {
  return `<div class="card ex-paused"><div class="ex-head"><span class="idx">${esc(idx || "")}</span>
    <div><div class="ex-name">${esc(p.name)}</div><div class="dose-note">Sitting out until ${esc(formatDate(p.until))} because it bothered you.</div></div></div></div>`;
}

// A daily non-negotiable is one ruled line: tick box, name and dose, a timer box when it's timed, and the how-to
function warmupCard(ex) {
  const key = `w:${ex.name}`;
  const on = Boolean(state.checks[ex.name]);
  const leaky = /leaky can/i.test(ex.name);
  const open = state.open.has(key);
  const start = on ? "" : leaky
    ? `<button type="button" class="timer-box" data-act="breathe" data-v="calm" aria-label="Guided breathing, 4 in, 6 out">${I.play}Guided</button>`
    : ex.hold ? `<button type="button" class="timer-box" data-act="warmup-timer" data-name="${esc(ex.name)}" aria-label="Start a ${fmtSecs(ex.hold_secs || 60)} timer">${I.play}${fmtSecs(ex.hold_secs || 60)}</button>` : "";
  return `<div class="card tick-row" data-card="${esc(key)}">
    <div class="tick-line">
      <button type="button" class="check${on ? " on" : ""}" data-act="check" data-name="${esc(ex.name)}" aria-pressed="${on}">
        <span class="box" aria-hidden="true"></span>
        <span><span class="name">${esc(ex.name)}</span>${ex.pt ? ` <span class="badge pt">PT</span>` : ""}<span class="sub" style="display:block">${esc(ex.dose || "")}</span></span>
      </button>
      ${start || "<span></span>"}
      ${hasHowTo(ex) || leaky ? `<button type="button" class="chev" data-act="toggle" data-key="${esc(key)}" aria-expanded="${open}" aria-label="How to do ${esc(ex.name)}">${open ? I.up : I.down}</button>` : "<span></span>"}
    </div>
    ${open && leaky && !on ? `<div class="row-actions" style="margin:0 0 6px">
      <button type="button" class="btn small" data-act="breathe" data-v="calm">${I.play}Guided, 4 in / 6 out</button>
      <button type="button" class="btn small" data-act="breathe" data-v="quicker">${I.play}Quicker, 3 in / 5 out</button></div>` : ""}
    ${open && hasHowTo(ex) ? howTo(ex) : ""}
  </div>`;
}

// Water toward today's goal, one tap per glass
function waterCard(p) {
  const w = p.water;
  if (!w) return "";
  const pct = Math.min(100, w.pct || 0);
  return `<div class="card water" data-card="water">
    <div class="water-line"><strong class="water-label">Water <span class="pen">${esc(w.total)}</span> / ${esc(w.goal)} oz</strong>
      ${[8, 12, 16, 24].map((oz) => `<button type="button" class="btn small" data-act="water" data-v="${oz}" aria-label="Add ${oz} ounces">+${oz}</button>`).join("")}
      ${w.total ? `<button type="button" class="btn link small muted-link" data-act="water-undo">Undo</button>` : ""}</div>
    <div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="${esc(w.goal)}" aria-valuenow="${esc(w.total)}" aria-label="Water today"><i style="width:${pct}%"></i></div>
  </div>`;
}

function fmtSecs(s) {
  s = Number(s) || 0;
  return s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : `${s} s`;
}

function slider(id, label, help) {
  const v = state.finish[id];
  return `<div class="slider">
    <div class="lbl"><span>${label}</span><span class="val" id="val-${id}">${v}/10</span></div>
    <input type="range" min="1" max="10" step="1" value="${v}" data-finish="${id}" aria-label="${label}">
    ${help ? `<div class="sub">${help}</div>` : ""}
  </div>`;
}

// Morning check-in: how the flank and pelvic floor feel today. Today's plan is built from these.
function ckSlider(key, label) {
  const v = state.ck[key];
  return `<div class="slider"><div class="lbl"><span>${label}</span><span class="val" id="ckval-${key}">${v}/10</span></div>
    <input type="range" min="1" max="10" step="1" value="${v}" data-ck="${key}" aria-label="${label}"></div>`;
}

function checkinCard(p) {
  const saved = p.checkin;
  if (saved && !state.ckEdit) {
    // the scores sit on the letterhead (tap them to change); only say so when they turned the day into recovery
    return p.cardio?.type === "recovery"
      ? `<div class="card season"><strong>Recovery day</strong><div class="sub">This morning's scores made today gentle recovery work.</div></div>` : "";
  }
  state.ck ||= { kidney: saved?.kidney ?? p.last_scores?.kidney ?? 1, pelvic_floor: saved?.pelvic_floor ?? p.last_scores?.pelvic_floor ?? 1 };
  return `<div class="card"><h3>How do you feel today?</h3>
    <p class="sub" style="margin:2px 0 6px">Today's plan adapts to this. Skip it and the plan uses how you felt after your last workout.</p>
    ${ckSlider("kidney", "Left kidney / flank tightness")}
    ${ckSlider("pelvic_floor", "Pelvic floor tightness")}
    <div class="row-actions"><button type="button" class="btn primary" style="width:auto" data-act="checkin-save">Save check-in</button>
      ${saved ? `<button type="button" class="btn link small" data-act="checkin-cancel">Cancel</button>` : ""}</div></div>`;
}

// Snow days: a day skiing or snowboarding is logged as that day's workout (legs and cardio)
const fmtMinutes = (m) => (m >= 60 ? `${Math.floor(m / 60)} h${m % 60 ? ` ${m % 60} min` : ""}` : `${m} min`);

// Ski days your watch recorded that aren't logged yet: one tap opens the snow-day form, filled in from it
function garminSnowCard(p) {
  const offers = p.garmin_acts?.snow || [];
  if (!offers.length || state.snowOpen) return "";
  return offers.map((o, i) => `<div class="card season"><strong>${esc(o.label)} ${o.date === p.date ? "today" : `on ${esc(formatDate(o.date))}`}</strong>
    <div class="sub">From your Garmin: ${esc([...o.names, fmtMinutes(o.minutes)].join(", "))}. Log it as a snow day so it counts as that day's workout.</div>
    <div class="row-actions"><button type="button" class="btn small" data-act="garmin-snow" data-i="${i}">Log it</button>
      <button type="button" class="btn link small muted-link" data-act="garmin-ignore" data-v="${esc(o.ids.join(","))}">Not a snow day</button></div></div>`).join("");
}

// Cardio your watch recorded today: tick it and its minutes are logged with today's workout instead of the planned ones
function garminCardio(p) {
  if (!p.garmin_acts) return "";
  const acts = p.garmin_acts.cardio || [];
  return `<div class="garmin-acts">
    ${acts.map((a) => {
      const on = state.cardioGarmin.includes(a.activity_id);
      const bits = [a.name, a.avg_hr ? `average heart rate ${a.avg_hr}` : ""].filter(Boolean).join(" · ");
      return `<button type="button" class="check${on ? " on" : ""}" data-act="garmin-cardio" data-v="${esc(a.activity_id)}" aria-pressed="${on}">
        <span class="box" aria-hidden="true"></span>
        <span><span class="name">From your watch: ${esc(a.label)}, <span class="pen">${esc(fmtMinutes(a.minutes))}</span></span>
          <span class="sub">${bits ? `${esc(bits)}. ` : ""}${on ? "These minutes are logged with today's workout." : "Tick to log these minutes with today's workout."}</span></span></button>`;
    }).join("")}
    <div class="small muted">${acts.length ? "" : "Recorded it on your watch? "}<button type="button" class="btn link small" data-act="garmin-check">Check Garmin</button></div>
  </div>`;
}

function snowCard(p) {
  if (p.snow_today && !state.snowOpen) {
    return `<div class="card"><strong>Snow day logged: ${esc(p.snow_today)}</strong>
      <div class="sub">It counts as today's workout. Tomorrow's leg work becomes core so your legs can recover.</div></div>`;
  }
  if (!state.snowOpen) return "";   // the "Snow day?" button is on the letterhead
  const s = state.snow ||= { sport: "snowboarding", hours: 3, rpe: 6, kidney: p.checkin?.kidney ?? 1,
    pelvic_floor: p.checkin?.pelvic_floor ?? 1, notes: "" };
  const sl = (key, label) => `<div class="slider"><div class="lbl"><span>${label}</span><span class="val" id="snowval-${key}">${s[key]}/10</span></div>
    <input type="range" min="1" max="10" step="1" value="${s[key]}" data-snow="${key}" aria-label="${label}"></div>`;
  const other = s.date && s.date !== p.date;
  return `<div class="card"><h3>Log a snow day${other ? `: ${esc(formatDate(s.date))}` : ""}</h3>
    ${s.garmin_ids?.length ? `<p class="sub" style="margin:2px 0 0">Filled in from your watch. Add how it felt${other ? " that day" : ""}.</p>` : ""}
    <div class="chips wrap" style="margin:6px 0 10px">${[["skiing", "Skiing"], ["snowboarding", "Snowboarding"]].map(([k, l]) =>
      `<button type="button" class="chip${s.sport === k ? " on" : ""}" data-act="snow-sport" data-v="${k}">${l}</button>`).join("")}</div>
    <label class="sub" for="snow-hours">Hours on the snow</label>
    <input id="snow-hours" class="code-input" style="width:100%" type="number" inputmode="decimal" min="0.5" max="12" step="0.5" value="${esc(s.hours)}" data-snow="hours">
    ${sl("rpe", "Overall effort")}
    ${sl("kidney", "Left kidney / flank tightness")}
    ${sl("pelvic_floor", "Pelvic floor tightness")}
    <textarea data-snow="notes" placeholder="How did it go? Falls, sore spots…">${esc(s.notes)}</textarea>
    <div class="row-actions"><button type="button" class="btn primary" style="width:auto" data-act="snow-save">Save snow day</button>
      <button type="button" class="btn link small" data-act="snow-toggle">Cancel</button></div></div>`;
}

function renderToday() {
  const p = state.plan;
  if (!p) {
    $view.innerHTML = `<div class="spinner">Loading today's plan…</div>`;
    return;
  }
  const cardio = p.cardio;
  const cardioText = (cardio.text || "").replace(/^\d+ min:\s*/, "");
  const main = p.strength.filter((e) => !(p.session2 || []).includes(e.name));
  if (p.done?.["1"]) return renderTodayDone(p);
  $view.innerHTML = `
    ${checkinCard(p)}
    ${waterCard(p)}
    ${p.garmin?.level ? `<div class="card season"><strong>${p.garmin.level === "recovery" ? "Garmin says: recovery day" : "Garmin says: go a bit lighter today"}</strong>
      <div class="sub">${esc(p.garmin.reasons.join(", "))}. ${p.garmin.level === "recovery"
        ? "Today is gentle recovery work."
        : "One fewer exercise, a quarter less cardio, and no load increases."} You can turn this off in Settings.</div></div>` : ""}
    ${garminSnowCard(p)}
    ${p.snow_sport || state.snowOpen ? snowCard(p) : ""}
    ${atPtCard(p)}
    ${bioDueCard(p)}
    ${skiDueCard(p)}
    ${p.coach_changes ?`<div class="small muted">Today's plan has added sessions or coach changes. <button type="button" class="btn link small" data-act="reset-plan">Undo them</button></div>` : ""}
    <h2 class="sec"><span class="n">1</span>Daily non-negotiables<span class="meta" id="meta-warmup">${warmupCount(p)}</span></h2>
    <div class="sheet">${p.warmup.map((e) => warmupCard(e)).join("")}</div>

    <h2 class="sec"><span class="n">2</span>Strength &amp; stability<span class="meta" id="meta-strength">${strengthCount(p)}</span></h2>
    <div class="sheet">
    ${main.map((e, i) => strengthCard(e, `2.${i + 1}`)).join("")}
    ${state.extras.map((n, i) => strengthCard(exerciseFor(n), `2.${main.length + i + 1}`)).join("")}
    ${(p.paused || []).map((x, i) => pausedRow(x, `2.${main.length + state.extras.length + i + 1}`)).join("")}
    </div>
    <div class="row-actions"><button type="button" class="btn small" data-act="add-exercise">${I.plus}Add another exercise</button>
      <button type="button" class="btn small" data-act="pt-add-go">${I.plus}Add one from my PT</button></div>

    <h2 class="sec"><span class="n">3</span>Cardio</h2>
    <div class="card">
      <div class="minutes">${esc(cardio.minutes ?? "")} <small>min</small></div>
      ${cardio.minutes ? minutesRule(cardio.minutes, cardio.type !== "recovery") : ""}
      <p>${esc(cardioText)}</p>
      ${cardio.note ? `<div class="sub">Why this length: ${esc(cardio.note)}</div>` : ""}
      ${garminCardio(p)}
    </div>

    ${p.cooldown?.cards?.length ? `<h2 class="sec"><span class="n">4</span>${esc(p.cooldown.title || "Cool-down")}<span class="meta">optional</span></h2>
    <p class="small muted" style="margin-top:0">${esc(p.cooldown.note)}</p>
    <div class="row-actions" style="margin:0 0 10px"><button type="button" class="btn small" data-act="guided-cooldown" data-v="45">${I.play}Play guided cool-down</button></div>
    ${p.cooldown.cards.map(mindCard).join("")}` : ""}

    <h2 class="sec"><span class="n">${p.cooldown?.cards?.length ? "5" : "4"}</span>Finish</h2>
    <div class="card">
      ${slider("rpe", "Overall effort")}
      ${slider("pf", "Pelvic floor tightness", "Higher numbers reduce impact cardio (running) next time.")}
      ${slider("kidney", "Left kidney / flank tightness", "Above 5 makes the next workout a recovery day.")}
      <label class="sub" for="notes">Notes for the coach</label>
      <textarea id="notes" data-finish="notes" placeholder="How did it feel?">${esc(state.finish.notes)}</textarea>
      <div style="height:12px"></div>
      <button type="button" class="btn primary" data-act="complete" data-session="1">Complete workout</button>
    </div>
    ${secondSessionSection(p)}`;
}

function atPtCard(p) {
  if (!p.at_pt) return "";
  return `<div class="card season"><strong>You're at the PT office</strong>
    <div class="sub">Ask your PT: any new exercises, or changes to the ones you do now? Add them here so they show up every day.</div>
    ${p.questions?.length ? `<div class="sub" style="margin-top:8px"><strong>Your questions:</strong></div>${questionList(p.questions, true)}` : ""}
    <div class="row-actions"><button type="button" class="btn small" data-act="pt-add-go">${I.plus}Add a PT exercise</button>
      ${p.bio?.enabled ? `<button type="button" class="btn small" data-act="bio-go">Log biofeedback</button>` : ""}
      <button type="button" class="btn small" data-act="goto" data-v="report">Show my PT report</button></div></div>`;
}

function bioDueCard(p) {
  if (!p.bio?.due) return "";
  return `<div class="card season"><strong>Pelvic floor biofeedback</strong>
    <div class="sub">${p.bio.last ? "About time for your next session with your pelvic PT." : "Log your next session with your pelvic PT."}
      Add the readings afterwards to see your progress.</div>
    <div class="row-actions"><button type="button" class="btn small" data-act="bio-go">Log my results</button>
      <button type="button" class="btn link small" data-act="bio-snooze">Remind me in 3 days</button></div></div>`;
}

function skiDueCard(p) {
  if (!p.ski_due) return "";
  return `<div class="card season"><strong>Ski readiness check due</strong>
    <div class="sub">Six quick tests (wall sit, balance, skater steps, side plank), about 10 minutes. Best before a workout, when you're fresh.</div>
    <div class="row-actions"><button type="button" class="btn small" data-act="ski-go">Open the check</button></div></div>`;
}

function prList(prs) {
  return prs?.length ? `<ul class="prs">${prs.map((x) => `<li><span class="pr-mark">Record</span><span><strong>${esc(x.exercise)}</strong>: ${esc(x.text)}</span></li>`).join("")}</ul>` : "";
}

function doneSummary(d) {
  const bits = [];
  if (d.exercises) bits.push(`${d.exercises} exercise${d.exercises === 1 ? "" : "s"}, ${d.sets} set${d.sets === 1 ? "" : "s"}`);
  if (d.minutes) bits.push(`${d.minutes} min cardio`);
  if (d.rpe) bits.push(`effort ${d.rpe}/10`);
  return bits.join(" · ");
}

// Today's workout is logged: show it as done (no second Complete), keep the cool-down and a second session available
function renderTodayDone(p) {
  const d = p.done["1"];
  $view.innerHTML = `
    <div class="card done-card"><h3>${I.check}Today's workout is done</h3>
      <p class="sub">${esc(doneSummary(d) || "Saved to History.")}</p>
      ${prList(d.prs)}
      ${d.pending ? `<p class="small muted">Kept on this phone until it's back online, then it goes to History on its own.</p>`
        : `<div class="row-actions"><button type="button" class="btn small" data-act="goto" data-v="history">View in History</button></div>`}</div>
    ${waterCard(p)}
    ${garminSnowCard(p)}
    ${p.snow_sport || state.snowOpen ? snowCard(p) : ""}
    ${atPtCard(p)}
    ${bioDueCard(p)}
    ${skiDueCard(p)}
    ${p.cooldown?.cards?.length ? `<h2 class="sec">${esc(p.cooldown.title || "Cool-down")}<span class="meta">optional</span></h2>
    <p class="small muted" style="margin-top:0">${esc(p.cooldown.note)}</p>
    <div class="row-actions" style="margin:0 0 10px"><button type="button" class="btn small" data-act="guided-cooldown" data-v="45">${I.play}Play guided cool-down</button></div>
    ${p.cooldown.cards.map(mindCard).join("")}` : ""}
    ${secondSessionSection(p)}`;
}

// A second workout on the same day, logged on its own (its own effort rating and its own History entry)
function secondSessionSection(p) {
  if (p.done?.["2"]) {
    return `<h2 class="sec">Second session</h2><div class="card done-card"><h3>${I.check}Second session done</h3>
      <p class="sub">${esc(doneSummary(p.done["2"]) || "Saved to History.")}</p>${prList(p.done["2"].prs)}</div>`;
  }
  const names = p.session2 || [];
  const has = names.length || p.extra_cardio;
  return `<h2>Second session${has ? "" : " <span class=\"muted\">(optional)</span>"}</h2>
    ${has ? `${names.map((n) => strengthCard(exerciseFor(n))).join("")}
      ${p.extra_cardio ? `<div class="card"><h3>Easy ${esc(p.extra_cardio.type)}</h3>
        <div class="minutes">${esc(p.extra_cardio.minutes)} <small>min</small></div>
        <p class="sub">${esc(p.extra_cardio.text)}. Easy pace, later in the day.</p></div>` : ""}
      <div class="card">
        ${slider("rpe2", "Second session effort")}
        <label class="sub" for="notes2">Notes</label>
        <textarea id="notes2" data-finish="notes2" placeholder="How did it feel?">${esc(state.finish.notes2)}</textarea>
        <div style="height:12px"></div>
        <button type="button" class="btn primary" data-act="complete" data-session="2">Complete second session</button>
      </div>` : ""}
    <div class="card">
      <button type="button" class="btn small" data-act="second-toggle">${state.secondOpen ? "Cancel" : I.plus + "Add a second session"}</button>
      ${state.secondOpen ? `<p class="sub" style="margin:10px 0 6px">What would you like to add today?</p>
        <div class="chips wrap">${[["strength", "Strength (different group)"], ["core", "Core"], ["mobility", "Mobility"], ["cardio", "Easy cardio"]].map(([k, l]) =>
          `<button type="button" class="chip" data-act="second-add" data-v="${k}">${l}</button>`).join("")}</div>
        <p class="small muted" style="margin:8px 0 0">It uses your equipment and the same kidney and pelvic floor safety checks. Extra cardio is 20 easy minutes.</p>` : ""}
    </div>`;
}

function rerenderCard(key) {
  const el = $view.querySelector(`[data-card="${CSS.escape(key)}"]`);
  if (!el) return render();
  const name = key.slice(2);
  const idx = el.querySelector(".idx")?.textContent || "";   // keep the row's number (2.3) as it was drawn
  el.outerHTML = key.startsWith("w:")
    ? warmupCard(state.plan.warmup.find((e) => e.name === name))
    : strengthCard(exerciseFor(name), idx);
  sectionCounts();
}

// "4 of 5" beside the section headings, kept current as you tick things off
function warmupCount(p) {
  return `${p.warmup.filter((e) => state.checks[e.name]).length} of ${p.warmup.length}`;
}
function strengthCount(p) {
  const names = p.strength.filter((e) => !(p.session2 || []).includes(e.name)).map((e) => e.name).concat(state.extras);
  const full = names.filter((n) => (state.sets[n] || []).length && state.sets[n].every((s) => s.done)).length;
  return `${full} of ${names.length} done`;
}
function sectionCounts() {
  const p = state.plan;
  if (!p) return;
  const w = document.getElementById("meta-warmup"), s = document.getElementById("meta-strength");
  if (w) w.textContent = warmupCount(p);
  if (s) s.textContent = strengthCount(p);
}

async function completeWorkout(btn, session = 1) {
  if (!confirm(session === 2 ? "Save the second session to your History?" : "Save this workout to your History?")) return;
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Saving…";
  clearTimeout(saveTimer);
  saveTimer = null;
  const payload = {
    rpe: Number(session === 2 ? state.finish.rpe2 : state.finish.rpe), pelvic_floor: Number(state.finish.pf),
    kidney: Number(state.finish.kidney), notes: session === 2 ? state.finish.notes2 : state.finish.notes,
    tracker: draftRows(), checks: state.checks, session, cardio_garmin_ids: session === 1 ? state.cardioGarmin : [],
    date: state.plan.date,
  };
  try {
    const res = await api("api/complete", { method: "POST", body: JSON.stringify(payload) });
    store.remove(unsentKey(state.plan.date));
    if (session === 1) {
      // keep the second session's effort and notes; the first session's are done
      const keep = { rpe2: state.finish.rpe2, notes2: state.finish.notes2 };
      store.remove(finishKey());
      state.finish = { ...FINISH_DEFAULTS, ...keep };
      store.set(finishKey(), state.finish);
    } else {
      state.finish.rpe2 = FINISH_DEFAULTS.rpe2;
      state.finish.notes2 = "";
      store.set(finishKey(), state.finish);
    }
    state.history = null;
    stopTimer(false);   // no rest timer once the workout is saved
    toast(session === 2 ? "Second session saved to History" : "Workout saved to History. Done for today.");
    await refreshPlan();
    window.scrollTo({ top: 0 });
    if (res.prs?.length) showTrophies(res.prs);
  } catch (err) {
    if (err.status === 409) {
      toast("Already logged today.");
      return refreshPlan();
    }
    if (offline(err)) return queueComplete(payload);
    toast("Couldn't save. Check your connection and try again.");
    btn.disabled = false;
    btn.textContent = label;
  }
}

// No connection: keep the finished workout on the phone and show the day as done; sendOutbox() delivers it later
function queueComplete(payload) {
  const session = payload.session;
  const names = new Set(payload.tracker.filter((r) => r.done).map((r) => r.exercise));
  const summary = { pending: true, rpe: payload.rpe, exercises: names.size, sets: payload.tracker.filter((r) => r.done).length,
    minutes: session === 1 ? state.plan.cardio?.minutes : state.plan.extra_cardio?.minutes };
  store.set(OUTBOX, [...store.get(OUTBOX, []).filter((q) => !(q.date === payload.date && q.session === session)),
    { date: payload.date, session, payload, summary }]);
  store.remove(unsentKey(payload.date));
  if (session === 1) {
    const keep = { rpe2: state.finish.rpe2, notes2: state.finish.notes2 };
    state.finish = { ...FINISH_DEFAULTS, ...keep };
  } else {
    state.finish.rpe2 = FINISH_DEFAULTS.rpe2;
    state.finish.notes2 = "";
  }
  store.set(finishKey(), state.finish);
  state.plan.done = { ...state.plan.done, [session]: summary };
  stopTimer(false);
  setSaveState("No connection: kept on this phone");
  toast("No connection. Your workout is kept on this phone and goes to History when you're back online.");
  render();
  window.scrollTo({ top: 0 });
}

let sending = false;
async function sendOutbox() {
  const queue = store.get(OUTBOX, []);
  if (!queue.length || sending) return;
  sending = true;
  let sent = 0;
  try {
    for (const q of queue) {
      try {
        const res = await api("api/complete", { method: "POST", body: JSON.stringify(q.payload) });
        sent += 1;
        if (res.prs?.length) showTrophies(res.prs);
      } catch (err) {
        if (offline(err)) break;                 // still no connection: try again later
        if (err.status === 400) toast("A workout kept on this phone was too old to add. Add it to History by hand.");
      }
      // sent, already logged (409) or refused (400): either way it no longer waits here
      store.set(OUTBOX, store.get(OUTBOX, []).filter((x) => !(x.date === q.date && x.session === q.session)));
    }
  } finally { sending = false; }
  if (sent) {
    state.history = null;
    toast(sent === 1 ? "Your workout reached History" : `${sent} workouts reached History`);
    setSaveState("Saved");
    refreshPlan().catch(() => {});
  }
}

// --- History ----------------------------------------------------------------------------------

// --- One exercise over time: weight (or reps, or hold seconds) per day, and the days it bothered you --------------------

const progValue = (p, d) => (p.kind === "weight" ? d.top_weight_lbs : d.best_reps);
function bestSet(p, d) {
  if (p.kind === "hold") return `${d.best_reps} s`;
  if (p.kind === "reps") return plural(d.best_reps, "rep");
  return `${d.top_weight_lbs} lb × ${d.reps_at_top}`;
}
const setsText = (p, d) => d.sets.map(([w, r]) => (p.kind === "hold" ? `${r} s` : p.kind === "reps" ? `${r}` : `${w}×${r}`)).join(", ");

// A time axis, so a two-week gap looks like one. "Bothered me" days are dashed upright lines in amber.
function progressChart(p) {
  const days = p.days;
  if (!days.length) return `<div class="empty">No sets of this exercise ticked done yet.</div>`;
  const W = 340, P = 34, PR = 18, TOP = 22, H = 120;
  const ms = (iso) => new Date(`${iso}T12:00:00`).getTime();
  const bothered = p.bothered || [];
  const isos = days.map((d) => d.date).concat(bothered).sort();
  const t0 = ms(isos[0]), t1 = ms(isos[isos.length - 1]), span = t1 - t0;
  const x = (iso) => (span ? P + ((ms(iso) - t0) / span) * (W - P - PR) : P + (W - P - PR) / 2);
  const vals = days.map((d) => progValue(p, d));
  const hi = Math.max(...vals), lo = Math.min(...vals), pad = Math.max(1, (hi - lo) * 0.15);
  const min = Math.max(0, Math.floor(lo - pad)), max = Math.ceil(hi + pad);
  const y = (v) => TOP + (1 - (v - min) / Math.max(1, max - min)) * H;
  const line = days.map((d, i) => `${i ? "L" : "M"}${x(d.date).toFixed(1)},${y(progValue(p, d)).toFixed(1)}`).join(" ");
  const showReps = p.kind === "weight" && days.length <= 14;
  const dots = days.map((d) => {
    const cx = x(d.date).toFixed(1), cy = y(progValue(p, d));
    return `<circle class="dot-a" cx="${cx}" cy="${cy.toFixed(1)}" r="4"><title>${esc(`${formatDate(d.date)}: ${bestSet(p, d)}, ${plural(d.sets_done, "set")}`)}</title></circle>
      ${showReps ? `<text x="${cx}" y="${(cy - 8).toFixed(1)}" text-anchor="middle" class="axis-text">×${d.reps_at_top}</text>` : ""}`;
  }).join("");
  const marks = bothered.map((b) => `<line class="bothered" x1="${x(b).toFixed(1)}" x2="${x(b).toFixed(1)}" y1="${TOP - 14}" y2="${TOP + H}"><title>${esc(`${formatDate(b)}: bothered you`)}</title></line>`).join("");
  const what = p.kind === "weight" ? "Heaviest weight (lb), with the reps you did at it" : p.kind === "hold" ? "Longest hold (seconds)" : "Most reps in a set";
  return `<div class="legend"><span><i class="sw-a"></i>${what}</span>${bothered.length ? `<span><i class="sw-bothered"></i>Bothered me</span>` : ""}</div>
    <svg viewBox="0 0 ${W} ${TOP + H + 18}" role="img" aria-label="${esc(`${p.exercise}: ${what.toLowerCase()} by day`)}">
      ${[min, max].map((v) => `<line class="grid" x1="${P}" x2="${W - PR}" y1="${y(v)}" y2="${y(v)}"/>
        <text x="${P - 4}" y="${y(v) + 4}" text-anchor="end" class="axis-text">${v}</text>`).join("")}
      ${marks}
      ${days.length > 1 ? `<path class="ln-a" d="${line}"/>` : ""}
      ${dots}
      <text x="${P}" y="${TOP + H + 14}" class="axis-text">${esc(formatDate(isos[0]))}</text>
      ${span ? `<text x="${W - PR}" y="${TOP + H + 14}" text-anchor="end" class="axis-text">${esc(formatDate(isos[isos.length - 1]))}</text>` : ""}
    </svg>`;
}

function progressBody(p) {
  const d = p.days;
  if (!d.length) return progressChart(p);
  const first = d[0], last = d[d.length - 1];
  const best = d.reduce((a, b) => (progValue(p, b) > progValue(p, a) || (progValue(p, b) === progValue(p, a) && b.reps_at_top > a.reps_at_top) ? b : a));
  const cell = (x) => `<td><span class="pen">${esc(bestSet(p, x))}</span><div class="small muted">${esc(formatDate(x.date))}</div></td>`;
  return `${progressChart(p)}
    <table><thead><tr><th>First</th><th>Latest</th><th>Best</th></tr></thead><tbody><tr>${cell(first)}${cell(last)}${cell(best)}</tr></tbody></table>
    ${p.paused_until ? `<p class="small muted">Sitting out until ${esc(formatDate(p.paused_until))} because it bothered you.</p>` : ""}
    <details class="small"><summary>Every session (${d.length})</summary>
      <table><thead><tr><th>Day</th><th>${p.kind === "weight" ? "Sets (lb × reps)" : p.kind === "hold" ? "Holds" : "Reps per set"}</th></tr></thead><tbody>
      ${[...d].reverse().map((x) => `<tr><td class="nowrap">${esc(formatDate(x.date))}${(p.bothered || []).includes(x.date) ? ` <span class="badge bad">bothered</span>` : ""}</td>
        <td>${esc(setsText(p, x))}</td></tr>`).join("")}</tbody></table></details>`;
}

// Symptoms over time: kidney and pelvic floor (same 1-10 scale, one axis) above, that day's workout effort below.
// Gaps are days with no score. Hover or tap a day for its numbers; the table under it has the same data.
function symptomChart(series) {
  if (!series.some((s) => s.kidney != null || s.effort != null)) return `<div class="empty">No scores in this period yet.</div>`;
  const W = 340, P = 22, PR = 62, TOP = 10, H1 = 120, GAP = 14, H2 = 44, n = series.length;
  const plotW = W - P - PR;
  const x = (i) => P + (n === 1 ? plotW / 2 : (i * plotW) / (n - 1));
  const y = (v) => TOP + (1 - v / 10) * H1;
  const base2 = TOP + H1 + GAP + H2;
  const line = (k) => {
    let d = "", pen = false;
    series.forEach((s, i) => {
      if (s[k] == null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(s[k]).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  const dots = (k, cls) => series.map((s, i) => s[k] == null ? "" :
    `<circle class="${cls}" cx="${x(i).toFixed(1)}" cy="${y(s[k]).toFixed(1)}" r="4"/>`).join("");
  const bw = Math.max(2, Math.min(8, plotW / n - 2));
  const bars = series.map((s, i) => {
    if (!s.effort) return "";
    const h = (s.effort / 10) * H2;
    return `<rect class="effort" x="${(x(i) - bw / 2).toFixed(1)}" y="${(base2 - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="${Math.min(2, bw / 2)}"/>`;
  }).join("");
  // Direct labels at each line's last point, nudged apart when they'd overlap
  const lastOf = (k) => { for (let i = n - 1; i >= 0; i--) if (series[i][k] != null) return { i, v: series[i][k] }; return null; };
  const lk = lastOf("kidney"), lp = lastOf("pf");
  let yk = lk && y(lk.v) + 4, yp = lp && y(lp.v) + 4;
  if (lk && lp && Math.abs(yk - yp) < 12) { const mid = (yk + yp) / 2; yk = mid + (lk.v >= lp.v ? -6 : 6); yp = mid + (lk.v >= lp.v ? 6 : -6); }
  const label = (l, yy, cls, text) => l ? `<line class="${cls}" x1="${W - PR + 6}" x2="${W - PR + 14}" y1="${yy - 4}" y2="${yy - 4}"/>
    <text x="${W - PR + 17}" y="${yy}" class="axis-text">${text} ${l.v}</text>` : "";
  const hits = series.map((s, i) => {
    const w = n === 1 ? plotW : plotW / (n - 1);
    const tip = `${formatDate(s.date)}: kidney ${s.kidney ?? "–"}, pelvic floor ${s.pf ?? "–"}${s.effort ? `, ${s.type || "workout"} effort ${s.effort}` : ", no workout"}`;
    return `<rect class="hit" x="${(x(i) - w / 2).toFixed(1)}" y="0" width="${w.toFixed(1)}" height="${base2}"><title>${esc(tip)}</title></rect>`;
  }).join("");
  const grid = [0, 5, 10].map((v) => `<line class="grid" x1="${P}" x2="${W - PR}" y1="${y(v)}" y2="${y(v)}"/>
    <text x="${P - 4}" y="${y(v) + 4}" text-anchor="end" class="axis-text">${v}</text>`).join("");
  return `<div class="legend"><span><i class="sw-kidney"></i>Kidney / flank</span><span><i class="sw-pf"></i>Pelvic floor</span><span><i class="sw-effort"></i>Workout effort</span></div>
    <svg viewBox="0 0 ${W} ${base2 + 18}" role="img" aria-label="Kidney and pelvic floor scores by day, with workout effort below">
      ${grid}
      <path class="ln-kidney" d="${line("kidney")}"/><path class="ln-pf" d="${line("pf")}"/>
      ${dots("kidney", "dot-kidney")}${dots("pf", "dot-pf")}
      ${label(lk, yk, "ln-kidney", "Kidney")}${label(lp, yp, "ln-pf", "Pelvic")}
      <text x="${P}" y="${TOP + H1 + GAP - 2}" class="axis-text">Effort (0–10)</text>
      <line class="grid" x1="${P}" x2="${W - PR}" y1="${base2}" y2="${base2}"/>
      ${bars}
      <text x="${P}" y="${base2 + 14}" class="axis-text">${esc(formatDate(series[0].date))}</text>
      <text x="${W - PR}" y="${base2 + 14}" text-anchor="end" class="axis-text">${esc(formatDate(series[n - 1].date))}</text>
      ${hits}
    </svg>`;
}

function trendTable(t) {
  const rows = t.series.filter((s) => s.kidney != null || s.effort);
  return `<details class="small"><summary>Show as a table</summary>
    <table><thead><tr><th>Day</th><th>Kidney</th><th>Pelvic floor</th><th>Workout</th></tr></thead><tbody>
    ${rows.map((s) => `<tr><td>${esc(formatDate(s.date))}</td><td>${s.kidney ?? ""}</td><td>${s.pf ?? ""}</td>
      <td>${s.effort ? `${esc(s.type || "")} · effort ${s.effort}` : ""}</td></tr>`).join("")}</tbody></table></details>`;
}

function trendBody(t) {
  return `${symptomChart(t.series)}
    <ul class="insights">${t.notes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    ${t.by_type.some((r) => r.n >= 2) ? `<table><thead><tr><th>Morning after</th><th>Days</th><th>Kidney</th><th>Pelvic floor</th></tr></thead><tbody>
      ${t.by_type.filter((r) => r.n >= 2).map((r) => `<tr><td>${esc(r.type)}</td><td>${r.n}</td><td>${r.kidney ?? ""}</td><td>${r.pf ?? ""}</td></tr>`).join("")}
      </tbody></table>` : ""}
    ${trendTable(t)}`;
}

function trendSection() {
  const days = state.trendDays;
  if (!state.trends || state.trends.days !== days) {
    api(`api/trends?days=${days}`).then((t) => {
      state.trends = t;
      const box = document.getElementById("trend-body");
      if (box) box.innerHTML = trendBody(t);
    }).catch(() => {});
  }
  return `<h2>How you've felt</h2>
    <div class="card">
      <div class="chips wrap" style="margin-bottom:8px">${[14, 30, 60, 90].map((d) =>
        `<button type="button" class="chip${d === days ? " on" : ""}" data-act="trend-days" data-v="${d}">${d} days</button>`).join("")}</div>
      <div id="trend-body" class="chart">${state.trends?.days === days ? trendBody(state.trends) : `<div class="spinner">Loading…</div>`}</div>
    </div>`;
}

// --- Pelvic floor biofeedback: readings from each manometry session with the pelvic PT ---------------------------------

function bioFmt(m, v, unit) {
  if (v == null) return "–";
  const n = v % 1 ? v : Math.round(v);
  return m.unit === "pressure" ? `${n} ${unit}` : m.unit === "s" ? `${n} s` : `${n}`;
}

// Resting tone and peak squeeze over the sessions (same unit, one axis). Hover a session for its numbers.
function bioChart(results, unit) {
  const pts = results.filter((r) => r.unit === unit && (r.values.resting != null || r.values.peak != null));
  if (pts.length < 2) return "";
  const W = 340, P = 30, PR = 74, TOP = 10, H = 120, n = pts.length;
  const vals = pts.flatMap((r) => [r.values.resting, r.values.peak]).filter((v) => v != null);
  const max = Math.max(1, ...vals) * 1.15;
  const x = (i) => P + (i * (W - P - PR)) / (n - 1);
  const y = (v) => TOP + (1 - v / max) * H;
  const line = (k) => {
    let d = "", pen = false;
    pts.forEach((r, i) => {
      if (r.values[k] == null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(r.values[k]).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  const dots = (k, cls) => pts.map((r, i) => r.values[k] == null ? "" : `<circle class="${cls}" cx="${x(i).toFixed(1)}" cy="${y(r.values[k]).toFixed(1)}" r="4"/>`).join("");
  const lastOf = (k) => { for (let i = n - 1; i >= 0; i--) if (pts[i].values[k] != null) return pts[i].values[k]; return null; };
  const lr = lastOf("resting"), lp = lastOf("peak");
  let yr = lr != null && y(lr) + 4, yp = lp != null && y(lp) + 4;
  if (lr != null && lp != null && Math.abs(yr - yp) < 12) { const mid = (yr + yp) / 2; yp = mid - 6; yr = mid + 6; }
  const label = (v, yy, cls, text) => v == null ? "" : `<line class="${cls}" x1="${W - PR + 6}" x2="${W - PR + 14}" y1="${yy - 4}" y2="${yy - 4}"/>
    <text x="${W - PR + 17}" y="${yy}" class="axis-text">${text} ${v}</text>`;
  const step = (W - P - PR) / (n - 1);
  const hits = pts.map((r, i) => `<rect class="hit" x="${(x(i) - step / 2).toFixed(1)}" y="0" width="${step.toFixed(1)}" height="${TOP + H}">
    <title>${esc(`${formatDate(r.date)}: resting ${r.values.resting ?? "–"}, peak ${r.values.peak ?? "–"} ${unit}`)}</title></rect>`).join("");
  const top = Math.round(max / 1.15);
  return `<div class="legend"><span><i class="sw-a"></i>Resting tone (lower is better)</span><span><i class="sw-b"></i>Peak squeeze</span></div>
    <svg viewBox="0 0 ${W} ${TOP + H + 18}" role="img" aria-label="Resting tone and peak squeeze by session, in ${esc(unit)}">
      ${[0, top].map((v) => `<line class="grid" x1="${P}" x2="${W - PR}" y1="${y(v)}" y2="${y(v)}"/>
        <text x="${P - 4}" y="${y(v) + 4}" text-anchor="end" class="axis-text">${v}</text>`).join("")}
      <path class="ln-a" d="${line("resting")}"/><path class="ln-b" d="${line("peak")}"/>
      ${dots("resting", "dot-a")}${dots("peak", "dot-b")}
      ${label(lr, yr, "ln-a", "Rest")}${label(lp, yp, "ln-b", "Peak")}
      <text x="${P}" y="${TOP + H + 14}" class="axis-text">${esc(formatDate(pts[0].date))}</text>
      <text x="${W - PR}" y="${TOP + H + 14}" text-anchor="end" class="axis-text">${esc(formatDate(pts[n - 1].date))}</text>
      ${hits}
    </svg>`;
}

// First vs latest for each reading (only sessions in the same unit as the latest are compared)
function bioCompare(results, measures) {
  if (!results.length) return "";
  const unit = results[results.length - 1].unit;
  const same = results.filter((r) => r.unit === unit);
  const rows = measures.map((m) => {
    const have = same.filter((r) => r.values[m.id] != null);
    if (!have.length) return "";
    const a = have[0].values[m.id], z = have[have.length - 1].values[m.id];
    const d = Math.round((z - a) * 10) / 10;
    const good = m.better === "lower" ? d < 0 : d > 0;
    const change = have.length < 2 ? "" : d === 0 ? "same" : `${d > 0 ? "+" : ""}${bioFmt(m, d, unit)} · ${good ? "better" : "not yet"}`;
    return `<tr><td>${esc(m.name)}<div class="small muted">${m.better} is better</div></td><td>${esc(bioFmt(m, a, unit))}</td>
      <td>${esc(bioFmt(m, z, unit))}</td><td>${esc(change)}</td></tr>`;
  }).join("");
  return `<table><thead><tr><th>Reading</th><th>First</th><th>Latest</th><th>Change</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function bioSessionRow(r, measures, editable) {
  const vals = measures.filter((m) => r.values[m.id] != null).map((m) => `${m.name}: ${bioFmt(m, r.values[m.id], r.unit)}`).join(" · ");
  return `<li><strong>${esc(formatDate(r.date))}</strong>${vals ? ` <span class="small">${esc(vals)}</span>` : ""}
    ${r.notes ? `<div class="small muted">${esc(r.notes)}</div>` : ""}
    ${editable ? `<button type="button" class="btn link small" data-act="bio-edit" data-v="${esc(r.date)}">Edit</button>
      <button type="button" class="btn link small muted-link" data-act="bio-delete" data-v="${esc(r.date)}">Delete</button>` : ""}</li>`;
}

function bioFormHtml(b) {
  const f = state.bioForm;
  const unitFor = (m) => (m.unit === "pressure" ? b.unit : m.unit);
  return `<div class="ski-form" id="bio-form">
    <label class="sub" for="bio-date">Session date</label>
    <input type="date" id="bio-date" class="code-input" style="width:100%" data-bio="date" value="${esc(f.date)}" max="${esc(state.plan?.date || "")}">
    <p class="small muted">Fill in whatever your PT gave you and leave the rest blank. Pressures are in ${esc(b.unit)} (change the unit in Settings).</p>
    ${b.measures.map((m) => `<div class="ski-test">
      <div><strong>${esc(m.name)}</strong> <span class="small muted">(${m.better} is better)</span><div class="small muted">${esc(m.help)}</div></div>
      <div class="ski-row" style="grid-template-columns:1fr"><label><input type="number" inputmode="decimal" min="0" step="0.1" data-bio="${m.id}"
        value="${esc(f.values[m.id] ?? "")}" aria-label="${esc(m.name)}"><span class="unit">${esc(unitFor(m))}</span></label></div></div>`).join("")}
    <label class="sub" for="bio-notes" style="display:block;margin-top:8px">What your PT said (optional)</label>
    <textarea id="bio-notes" data-bio="notes" placeholder="e.g. better relaxation after squeezes, keep the down-training">${esc(f.notes)}</textarea>
    <div class="row-actions"><button type="button" class="btn primary" style="width:auto" data-act="bio-save">Save session</button>
      <button type="button" class="btn link small" data-act="bio-cancel">Cancel</button></div></div>`;
}

function bioSection() {
  const b = state.bio;
  if (!b) {
    api("api/biofeedback").then((r) => { state.bio = r; if (state.tab === "history") render(); }).catch(() => {});
    return "";
  }
  if (!b.enabled && !b.results.length) return "";
  const res = b.results;
  const unit = res.length ? res[res.length - 1].unit : b.unit;
  return `<h2 id="bio">Pelvic floor biofeedback</h2>
    <div class="card chart">
      ${res.length ? `${bioChart(res, unit)}${bioCompare(res, b.measures)}` : `<p class="sub" style="margin-top:0">No sessions logged yet. Add the readings after your next session with your pelvic PT.</p>`}
      ${b.enabled && res.length ? `<p class="small muted">${b.due ? "Your next session is due." : `Next session around ${esc(formatDate(b.next))}.`}</p>` : ""}
      ${state.bioForm ? bioFormHtml(b) : `<div class="row-actions"><button type="button" class="btn small" data-act="bio-new">+ Log a session</button></div>`}
      ${res.length ? `<details class="small"><summary>All sessions (${res.length})</summary>
        <ul class="plain" style="margin-top:8px">${[...res].reverse().map((r) => bioSessionRow(r, b.measures, true)).join("")}</ul></details>` : ""}
    </div>`;
}

async function loadProgress(exercise) {
  const p = await api(`api/progress?exercise=${encodeURIComponent(exercise)}`);
  state.prog[exercise] = p;
  const el = document.getElementById("chart");
  if (el && state.progress.exercise === exercise) el.innerHTML = progressBody(p);
  if (state.tab === "today" && state.open.has(`p:${exercise}`)) rerenderCard(`s:${exercise}`);
}

function workoutCard(w) {
  const key = `h:${w.id}`;
  const open = state.open.has(key);
  const sets = w.sets.map((s) => `<tr><td>${esc(s.exercise)}</td><td>${s.set_number ?? ""}</td><td>${s.weight_lbs ?? ""}</td><td>${s.reps ?? ""}</td><td>${s.done ? "Yes" : ""}</td></tr>`).join("");
  return `<div class="card">
    <button type="button" class="result" data-act="toggle" data-key="${esc(key)}" aria-expanded="${open}">
      <h3>${esc(formatDate(w.date))}</h3>
      <div class="stats">
        <span class="pill">Effort ${w.rpe ?? "?"}/10</span>
        <span class="pill">Flank ${w.kidney_flank_pain ?? "?"}/10</span>
        <span class="pill">Pelvic floor ${w.pelvic_floor_tightness ?? "?"}/10</span>
        ${w.sets.length ? `<span class="pill">${plural(w.sets.filter((s) => s.done).length, "set")}</span>` : ""}
        ${w.workout?.prs?.length ? `<span class="pill pr">${plural(w.workout.prs.length, "record")}</span>` : ""}
      </div>
    </button>
    ${open ? `<div class="howto">
      ${prList(w.workout?.prs)}
      ${w.workout?.strength?.length ? `<div class="small"><strong>Exercises:</strong> ${esc(w.workout.strength.join(", "))}</div>` : ""}
      ${w.workout?.cardio ? `<div class="small"><strong>Cardio:</strong> ${esc(w.workout.cardio)}</div>` : ""}
      ${sets ? `<table><thead><tr><th>Exercise</th><th>Set</th><th>lbs</th><th>Reps</th><th>Done</th></tr></thead><tbody>${sets}</tbody></table>` : ""}
      ${w.notes ? `<pre class="notes">${esc(w.notes)}</pre>` : ""}
    </div>` : ""}
  </div>`;
}

function progOptions(exercises) {
  const q = state.progQ.trim().toLowerCase();
  const shown = exercises.filter((e) => !q || e.toLowerCase().includes(q) || e === state.progress.exercise);
  return shown.map((e) => `<option${e === state.progress.exercise ? " selected" : ""}>${esc(e)}</option>`).join("");
}

async function renderHistoryPage() {
  if (!state.history) {
    $view.innerHTML = `<div class="spinner">Loading history…</div>`;
    state.history = await api("api/history");
    if (state.tab !== "history") return;
  }
  const { workouts, exercises } = state.history;
  if (!workouts.length) {
    $view.innerHTML = `${bioSection()}${bodySection()}${waterHistory()}<div class="empty">No completed workouts yet.<br>Press <strong>Complete workout</strong> at the end of Today to save one.</div>`;
    return;
  }
  if (exercises.length && !exercises.includes(state.progress.exercise)) state.progress = { exercise: exercises[0] };
  if (exercises.length && !state.prog[state.progress.exercise]) loadProgress(state.progress.exercise).catch(() => {});
  $view.innerHTML = `
    ${trendSection()}
    ${bioSection()}
    ${bodySection()}
    ${waterHistory()}
    ${exercises.length ? `<h2>Progress</h2>
    <div class="card">
      <div class="prog-pick">
        <input type="search" id="prog-q" placeholder="Find an exercise…" value="${esc(state.progQ)}" aria-label="Find an exercise" autocomplete="off">
        <select id="prog-select" data-act-change="progress" aria-label="Exercise">${progOptions(exercises)}</select>
      </div>
      <div id="chart" class="chart">${state.prog[state.progress.exercise] ? progressBody(state.prog[state.progress.exercise]) : `<div class="spinner">Loading…</div>`}</div>
    </div>` : ""}
    <h2>Completed workouts (${workouts.length})</h2>
    ${workouts.map(workoutCard).join("")}
    <button type="button" class="btn small" data-act="report">Make an HTML progress report (AI Coach)</button>`;
}

// --- Weight, blood pressure and water ----------------------------------------------------------------------------------

// A time-based line chart: series share one axis (same unit). refs = dashed reference lines (e.g. 120/80 for BP).
function timeChart(rows, series, { min, max, refs = [], unit = "", label = "" } = {}) {
  if (!rows.length) return "";
  const W = 340, P = 34, PR = 66, TOP = 10, H = 120;
  const t0 = rows[0].t, t1 = rows[rows.length - 1].t, span = Math.max(1, t1 - t0);
  const x = (t) => (rows.length === 1 ? P + (W - P - PR) / 2 : P + ((t - t0) / span) * (W - P - PR));
  const y = (v) => TOP + (1 - (v - min) / Math.max(1, max - min)) * H;
  const parts = series.map((s) => {
    const pts = rows.filter((r) => r[s.key] != null);
    const d = s.dots ? "" : pts.map((r, i) => `${i ? "L" : "M"}${x(r.t).toFixed(1)},${y(r[s.key]).toFixed(1)}`).join(" ");
    const dots = s.line ? "" : pts.map((r) => `<circle class="${s.dotCls}" cx="${x(r.t).toFixed(1)}" cy="${y(r[s.key]).toFixed(1)}" r="4"><title>${esc(`${formatDate(r.date)}: ${r[s.key]}${unit}`)}</title></circle>`).join("");
    const last = pts[pts.length - 1];
    return { d, dots, last, s };
  });
  // direct labels at each series' last point, nudged apart
  const labels = parts.filter((p) => p.last && p.s.label).map((p) => ({ y: y(p.last[p.s.key]) + 4, p }));
  labels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) if (labels[i].y - labels[i - 1].y < 12) labels[i].y = labels[i - 1].y + 12;
  return `<svg viewBox="0 0 ${W} ${TOP + H + 18}" role="img" aria-label="${esc(label)}">
    ${[min, max].map((v) => `<line class="grid" x1="${P}" x2="${W - PR}" y1="${y(v)}" y2="${y(v)}"/>
      <text x="${P - 4}" y="${y(v) + 4}" text-anchor="end" class="axis-text">${Math.round(v)}</text>`).join("")}
    ${refs.map((r) => `<line class="ref" x1="${P}" x2="${W - PR}" y1="${y(r.v)}" y2="${y(r.v)}"/>
      <text x="${P - 4}" y="${y(r.v) + 4}" text-anchor="end" class="axis-text">${r.v}</text>`).join("")}
    ${parts.map((p) => (p.d ? `<path class="${p.s.lineCls}" d="${p.d}"/>` : "") + p.dots).join("")}
    ${labels.map((l) => `<text x="${W - PR + 8}" y="${l.y}" class="axis-text">${esc(l.p.s.label)} ${Math.round(l.p.last[l.p.s.key] * 10) / 10}</text>`).join("")}
    <text x="${P}" y="${TOP + H + 14}" class="axis-text">${esc(formatDate(rows[0].date))}</text>
    ${rows.length > 1 ? `<text x="${W - PR}" y="${TOP + H + 14}" text-anchor="end" class="axis-text">${esc(formatDate(rows[rows.length - 1].date))}</text>` : ""}
  </svg>`;
}

const tsMs = (ts) => new Date(ts).getTime();

function weightChart(list) {
  if (!list.length) return "";
  const rows = list.map((r) => ({ t: tsMs(r.ts), date: r.date, w: r.v1 }));
  rows.forEach((r) => {   // 7-day average ending at each weigh-in
    const win = rows.filter((o) => o.t <= r.t && o.t > r.t - 7 * 864e5);
    r.avg = Math.round((win.reduce((a, o) => a + o.w, 0) / win.length) * 10) / 10;
  });
  const vals = rows.map((r) => r.w);
  const lo = Math.floor(Math.min(...vals) - 2), hi = Math.ceil(Math.max(...vals) + 2);
  return `<div class="legend"><span><i class="sw-effort" style="height:8px;width:8px;border-radius:50%"></i>Weigh-ins</span><span><i class="sw-a"></i>7-day average</span></div>
    ${timeChart(rows, [{ key: "w", dots: true, dotCls: "dot-muted" }, { key: "avg", line: true, lineCls: "ln-a", label: "Avg" }],
      { min: lo, max: hi, unit: " lb", label: "Weight over time, in pounds" })}`;
}

function bpChart(list) {
  if (!list.length) return "";
  const rows = list.map((r) => ({ t: tsMs(r.ts), date: r.date, sys: r.v1, dia: r.v2 }));
  const hi = Math.max(160, ...rows.map((r) => r.sys + 10));
  return `<div class="legend"><span><i class="sw-a"></i>Systolic (top)</span><span><i class="sw-b"></i>Diastolic (bottom)</span><span><i class="sw-ref"></i>120 / 80</span></div>
    ${timeChart(rows, [{ key: "sys", lineCls: "ln-a", dotCls: "dot-a", label: "Sys" }, { key: "dia", lineCls: "ln-b", dotCls: "dot-b", label: "Dia" }],
      { min: 50, max: Math.ceil(hi / 10) * 10, refs: [{ v: 120 }, { v: 80 }], unit: " mmHg", label: "Blood pressure over time" })}`;
}

function weightSummary(list) {
  if (!list.length) return "";
  const first = list[0], last = list[list.length - 1];
  const d = Math.round((last.v1 - first.v1) * 10) / 10;
  return `<p class="sub"><strong>${last.v1} lb</strong> on ${esc(formatDate(last.date))}${list.length > 1 ? ` · ${d > 0 ? "+" : ""}${d} lb since ${esc(formatDate(first.date))}` : ""}</p>`;
}

function bpSummary(list, category) {
  if (!list.length) return "";
  const last = list[list.length - 1];
  const avg = (k) => Math.round(list.reduce((a, r) => a + r[k], 0) / list.length);
  return `<p class="sub"><strong>${last.v1}/${last.v2}</strong>${last.v3 ? ` · pulse ${last.v3}` : ""} on ${esc(formatDate(last.date))}
    ${category ? `· <strong>${esc(category)}</strong>` : ""}${list.length > 1 ? `<br>Average of ${list.length} readings: ${avg("v1")}/${avg("v2")}` : ""}</p>`;
}

function bodySection() {
  const b = state.body;
  if (!b) {
    api("api/body?days=90").then((r) => { state.body = r; if (state.tab === "history") render(); }).catch(() => {});
    return "";
  }
  const f = state.bodyForm;
  const linked = b.sensors?.weight_entity || b.sensors?.sys_entity;
  const form = f === "weight" ? `<div class="composer" style="position:static;padding:0;margin-top:8px">
      <input id="body-weight" type="number" inputmode="decimal" step="0.1" class="code-input" placeholder="Weight in lb" aria-label="Weight in pounds">
      <button type="button" class="btn small" style="width:auto" data-act="body-save" data-v="weight">Save</button></div>`
    : f === "bp" ? `<div class="bp-form" style="margin-top:8px">
      <input id="bp-sys" type="number" inputmode="numeric" class="code-input" placeholder="Top (sys)" aria-label="Systolic">
      <input id="bp-dia" type="number" inputmode="numeric" class="code-input" placeholder="Bottom (dia)" aria-label="Diastolic">
      <input id="bp-pulse" type="number" inputmode="numeric" class="code-input" placeholder="Pulse" aria-label="Pulse">
      <button type="button" class="btn small" data-act="body-save" data-v="bp">Save</button></div>` : "";
  const recent = [...b.weight.map((r) => ({ ...r, kind: "weight" })), ...b.bp.map((r) => ({ ...r, kind: "bp" }))]
    .sort((a, z) => z.ts.localeCompare(a.ts)).slice(0, 20);
  return `<h2>Weight and blood pressure</h2>
    <div class="card chart">
      ${b.weight.length ? `${weightSummary(b.weight)}${weightChart(b.weight)}` : `<p class="sub" style="margin-top:0">No weigh-ins yet.</p>`}
      ${b.bp.length ? `<div style="margin-top:14px">${bpSummary(b.bp, b.bp_category)}${bpChart(b.bp)}</div>` : ""}
      ${linked ? `<p class="small muted">New readings from Home Assistant (your scale or BP monitor) come in by themselves every few minutes.</p>`
        : `<p class="small muted">Link your Withings scale in Settings › Scale and blood pressure, or add readings by hand.</p>`}
      <div class="row-actions"><button type="button" class="btn small" data-act="body-form" data-v="weight">+ Weight</button>
        <button type="button" class="btn small" data-act="body-form" data-v="bp">+ Blood pressure</button></div>
      ${form}
      ${recent.length ? `<details class="small"><summary>Recent readings</summary><ul class="plain" style="margin-top:8px">${recent.map((r) =>
        `<li>${esc(formatDate(r.date))} ${esc(r.ts.slice(11, 16))}: ${r.kind === "weight" ? `${r.v1} lb` : `${r.v1}/${r.v2}${r.v3 ? `, pulse ${r.v3}` : ""}`}
          <span class="muted">${r.source === "ha" ? "(Home Assistant)" : ""}</span>
          <button type="button" class="btn link small muted-link" data-act="body-del" data-v="${r.id}">Delete</button></li>`).join("")}</ul></details>` : ""}
    </div>`;
}

function waterHistory() {
  const w = state.waterHist;
  if (!w) {
    api("api/water").then((r) => { state.waterHist = r; if (state.tab === "history") render(); }).catch(() => {});
    return "";
  }
  if (!w.days.some((d) => d.oz)) return "";
  const W = 340, P = 30, H = 90, TOP = 8, n = w.days.length, max = Math.max(w.goal, ...w.days.map((d) => d.oz)) * 1.1;
  const bw = (W - P - 10) / n - 4;
  const y = (v) => TOP + (1 - v / max) * H;
  return `<h2>Water</h2><div class="card chart">
    <div class="legend"><span><i class="sw-a" style="height:8px;width:8px"></i>Water per day (oz)</span><span><i class="sw-ref"></i>Goal ${w.goal} oz</span></div>
    <svg viewBox="0 0 ${W} ${TOP + H + 18}" role="img" aria-label="Water per day for the last two weeks">
      <line class="grid" x1="${P}" x2="${W - 10}" y1="${y(0)}" y2="${y(0)}"/>
      <line class="ref" x1="${P}" x2="${W - 10}" y1="${y(w.goal)}" y2="${y(w.goal)}"/>
      <text x="${P - 4}" y="${y(w.goal) + 4}" text-anchor="end" class="axis-text">${w.goal}</text>
      ${w.days.map((d, i) => d.oz ? `<rect class="bar-a" x="${(P + i * (bw + 4) + 2).toFixed(1)}" y="${y(d.oz).toFixed(1)}" width="${bw.toFixed(1)}"
        height="${(y(0) - y(d.oz)).toFixed(1)}" rx="3"><title>${esc(`${formatDate(d.date)}: ${d.oz} oz`)}</title></rect>` : "").join("")}
      <text x="${P}" y="${TOP + H + 14}" class="axis-text">${esc(formatDate(w.days[0].date))}</text>
      <text x="${W - 10}" y="${TOP + H + 14}" text-anchor="end" class="axis-text">Today</text>
    </svg></div>`;
}

// --- Questions for the PT: jot them down during the week, tick them off at the visit -------------------------------------

function questionList(list, compact) {
  if (!list?.length) return compact ? "" : `<p class="sub">No questions yet.</p>`;
  return `<ul class="questions">${list.map((q) => `<li>
    <button type="button" class="qtick" data-act="q-asked" data-v="${q.id}" aria-label="Asked"></button>
    <span>${q.source === "ai" ? '<span class="tag-ai">Suggested</span>' : ""}${esc(q.text)}</span>
    ${compact ? "" : `<button type="button" class="btn link small muted-link noprint" data-act="q-del" data-v="${q.id}">Remove</button>`}</li>`).join("")}</ul>`;
}

function questionsSection() {
  const q = state.questions;
  if (!q) return `<div class="card muted">Loading questions…</div>`;
  const s = state.qSuggest;
  return `<h2>Questions for my PT</h2>
    <div class="card">
      <div class="composer noprint" style="position:static;padding:0"><input id="q-new" class="code-input" maxlength="300" placeholder="e.g. Can I add weight to the wall sits?" aria-label="New question">
        <button type="button" class="btn small" style="width:auto" data-act="q-add">Add</button></div>
      ${questionList(q.open, false)}
      <div class="row-actions noprint"><button type="button" class="btn small" data-act="q-suggest" ${s?.busy ? "disabled" : ""}>${s?.busy ? "Thinking…" : "Suggest questions from my data"}</button></div>
      ${s?.error ? `<div class="small warning noprint" style="margin-top:8px">${esc(s.error)}</div>` : ""}
      ${s?.items?.length ? `<div class="suggest noprint"><div class="sub">The coach suggests (tap to add):</div>
        ${s.items.map((x, i) => `<button type="button" class="btn small suggest-item" data-act="q-add-ai" data-i="${i}">+ ${esc(x)}</button>`).join("")}</div>` : ""}
      ${q.asked.length ? `<details class="small"><summary>Asked (${q.asked.length})</summary><ul class="plain" style="margin-top:8px">${q.asked.map((x) =>
        `<li><span class="muted">${esc(formatDate(x.asked_on))}:</span> ${esc(x.text)}${x.answer ? `<div><strong>PT:</strong> ${esc(x.answer)}</div>` : ""}
          <button type="button" class="btn link small muted-link noprint" data-act="q-undo" data-v="${x.id}">Not asked yet</button></li>`).join("")}</ul></details>` : ""}
    </div>`;
}

// --- PT visit report: one printable page to show at appointments -----------------------------------------------------

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const ptDays = (days) => (!days?.length ? "every day" : days.map((d) => DAY_NAMES[d]).join(", "));

async function renderReportPage() {
  const days = state.reportDays;
  if (!state.report || state.report.days !== days) {
    $view.innerHTML = `<div class="spinner">Putting your report together…</div>`;
    state.report = await api(`api/report/pt?days=${days}`);
    if (state.tab !== "report") return;
  }
  if (!state.questions) state.questions = { open: state.report.questions.open, asked: state.report.questions.asked };
  const r = state.report;
  const t = r.trends;
  const routine = r.routine_days
    ? `<table><thead><tr><th>Daily non-negotiable</th><th>Done</th></tr></thead><tbody>
        ${r.routine.map((x) => `<tr><td>${esc(x.name)}</td><td>${x.done} of ${x.of} workout days</td></tr>`).join("")}</tbody></table>`
    : `<p class="sub">Ticks on the daily non-negotiables are saved with each workout from this version on, so this fills in from your next workout.</p>`;
  $view.innerHTML = `
    <div class="report-head">
      <div><h2 style="margin:6px 0 2px">PT visit report</h2>
        <div class="small muted">${esc(formatDate(r.from))} – ${esc(formatDate(r.to))} · Joe's own logged scores (1 = fine, 10 = worst)</div></div>
      <button type="button" class="btn small noprint" data-act="print">🖨️ Print or save PDF</button>
    </div>
    <div class="chips noprint" style="margin:10px 0">${[14, 30, 60, 90].map((d) =>
      `<button type="button" class="chip${d === days ? " on" : ""}" data-act="report-days" data-v="${d}">Last ${d} days</button>`).join("")}</div>
    ${questionsSection()}
    <div class="card stat-grid">
      <div><div class="stat">${r.workouts}<small> / ${r.planned}</small></div><div class="sub">workouts done / training days planned</div></div>
      <div><div class="stat">${r.checkins}</div><div class="sub">morning check-ins</div></div>
      <div><div class="stat">${t.averages.kidney ?? "–"}</div><div class="sub">average kidney / flank</div></div>
      <div><div class="stat">${t.averages.pf ?? "–"}</div><div class="sub">average pelvic floor</div></div>
      ${r.snow_days ? `<div><div class="stat">${r.snow_days}</div><div class="sub">snow days</div></div>` : ""}
      ${r.second_sessions ? `<div><div class="stat">${r.second_sessions}</div><div class="sub">second sessions</div></div>` : ""}
      ${r.water.avg ? `<div><div class="stat">${r.water.avg}<small> oz</small></div><div class="sub">water a day (goal ${r.water.goal}, ${r.water.days_logged} days logged)</div></div>` : ""}
    </div>
    ${r.body.weight.length || r.body.bp.length ? `<h2>Weight and blood pressure</h2>
    <div class="card chart">${weightSummary(r.body.weight)}${weightChart(r.body.weight)}
      ${r.body.bp.length ? `<div style="margin-top:14px">${bpSummary(r.body.bp, r.body.bp_category)}${bpChart(r.body.bp)}</div>` : ""}</div>` : ""}
    <h2>Symptoms</h2>
    <div class="card chart">${trendBody(t)}</div>
    ${r.biofeedback.length ? `<h2>Pelvic floor biofeedback</h2>
    <div class="card chart">${bioChart(r.biofeedback, r.biofeedback[r.biofeedback.length - 1].unit)}${bioCompare(r.biofeedback, r.bio_measures)}
      <ul class="plain" style="margin-top:10px">${r.biofeedback.filter((x) => x.date >= r.from).reverse().map((x) => bioSessionRow(x, r.bio_measures, false)).join("")}</ul></div>` : ""}
    <h2>Daily routine</h2>
    <div class="card">${routine}</div>
    ${r.pt_exercises.length ? `<h2>PT-prescribed exercises</h2>
    <div class="card"><table><thead><tr><th>Exercise</th><th>Dose</th><th>When</th></tr></thead><tbody>
      ${r.pt_exercises.map((p) => `<tr><td>${esc(p.name)}</td><td>${esc(p.dose)}</td><td>${esc(ptDays(p.days))}</td></tr>`).join("")}</tbody></table></div>` : ""}
    <h2>Strength and holds</h2>
    <div class="card">${r.lifts.length ? `<table><thead><tr><th>Exercise</th><th>Sessions</th><th>First</th><th>Latest</th></tr></thead><tbody>
      ${r.lifts.map((l) => `<tr><td>${esc(l.exercise)}</td><td>${l.sessions}</td><td>${esc(l.first)}</td><td>${esc(l.latest)}${l.better ? " ↑" : ""}</td></tr>`).join("")}
      </tbody></table><p class="small muted">First and latest = heaviest weight with its reps, most reps, or longest hold in that session. ↑ = better than the first.</p>`
      : `<p class="sub">No sets logged in this period.</p>`}</div>
    ${r.prs.length ? `<h2>Personal records</h2><div class="card"><ul class="prs">${r.prs.map((x) =>
      `<li><span class="pr-mark">Record</span><span>${esc(formatDate(x.date))}: <strong>${esc(x.exercise)}</strong>, ${esc(x.text)}</span></li>`).join("")}</ul></div>` : ""}
    <h2>Exercises that bothered me</h2>
    <div class="card">${r.bothered.length ? `<ul class="plain">${r.bothered.map((b) =>
      `<li><strong>${esc(b.name)}</strong>: marked ${esc(formatDate(b.since))}, ${esc(b.status)}${b.status === "sitting out" ? ` until ${esc(formatDate(b.until))}` : ""}</li>`).join("")}</ul>`
      : `<p class="sub">Nothing marked in this period.</p>`}</div>
    ${r.questions.asked.length ? `<h2>Questions asked at visits</h2><div class="card"><ul class="plain">${r.questions.asked.map((x) =>
      `<li><span class="muted">${esc(formatDate(x.asked_on))}:</span> ${esc(x.text)}${x.answer ? `<div><strong>Answer:</strong> ${esc(x.answer)}</div>` : ""}</li>`).join("")}</ul></div>` : ""}
    ${r.notes.length ? `<h2>Notes</h2><div class="card"><ul class="plain">${r.notes.map((x) =>
      `<li><span class="muted">${esc(formatDate(x.date))}:</span> ${esc(x.text)}</li>`).join("")}</ul></div>` : ""}
    <p class="small muted">From the AI Workout Tracker. A personal training log, not a medical record.</p>`;
}

// --- Personal records: a small celebration when a workout beats your best ------------------------------------------------

const $trophy = document.getElementById("trophy");

function showTrophies(prs) {
  const bits = Array.from({ length: 18 }, (_, i) =>
    `<span style="left:${Math.round(Math.random() * 100)}%;animation-delay:${(Math.random() * 0.8).toFixed(2)}s"></span>`).join("");
  $trophy.innerHTML = `<div class="confetti" aria-hidden="true">${bits}</div>
    <div class="trophy-inner"><div class="trophy-cup" aria-hidden="true">${I.star}</div>
      <h3>New personal record${prs.length > 1 ? "s" : ""}!</h3>${prList(prs)}
      <button type="button" class="btn primary" data-trophy="close">Nice</button></div>`;
  $trophy.hidden = false;
  try { navigator.vibrate?.([80, 60, 80, 60, 160]); } catch { /* not supported */ }
}

$trophy.addEventListener("click", (e) => {
  if (e.target.closest("[data-trophy]") || e.target === $trophy) { $trophy.hidden = true; $trophy.innerHTML = ""; }
});

// --- Timers: hold countdowns and rest between sets -------------------------------------------------
// One timer at a time, shown in a bar above the tabs. It beeps and buzzes when time is up and keeps the screen on.

const $timer = document.getElementById("timer");
let timer = null;

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.25, 0.5].forEach((t) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.frequency.value = 880;
      g.gain.setValueAtTime(0.25, ctx.currentTime + t);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + t + 0.2);
      o.connect(g).connect(ctx.destination);
      o.start(ctx.currentTime + t);
      o.stop(ctx.currentTime + t + 0.2);
    });
  } catch { /* no audio */ }
  try { navigator.vibrate?.([250, 120, 250]); } catch { /* not supported */ }
}

async function keepAwake(on) {
  try {
    if (on && !timer?.lock && "wakeLock" in navigator) timer.lock = await navigator.wakeLock.request("screen");
    if (!on && timer?.lock) { timer.lock.release(); timer.lock = null; }
  } catch { /* not allowed */ }
}

function startTimer(t) {
  stopTimer(false);
  timer = { ...t, start: Date.now(), end: Date.now() + t.secs * 1000 };
  keepAwake(true);
  timer.tick = setInterval(drawTimer, 250);
  drawTimer();
}

function stopTimer(finished, held) {
  if (!timer) return;
  const t = timer;
  clearInterval(t.tick);
  keepAwake(false);
  timer = null;
  $timer.hidden = true;
  if (finished) {
    beep();
    if (t.onDone) t.onDone(held ?? t.secs);
  }
}

function drawTimer() {
  if (!timer) return;
  const left = Math.max(0, Math.ceil((timer.end - Date.now()) / 1000));
  if (left <= 0) return stopTimer(true);
  // "up" timers (ski tests: hold as long as you can) show the time held instead of the time left
  const shown = timer.up ? Math.floor((Date.now() - timer.start) / 1000) : left;
  const mm = Math.floor(shown / 60), ss = String(shown % 60).padStart(2, "0");
  $timer.hidden = false;
  $timer.className = `timerbar ${timer.kind}`;
  $timer.innerHTML = `<div class="timer-label">${esc(timer.label)}</div><div class="timer-time">${mm}:${ss}</div>
    <div class="timer-actions">${timer.kind === "hold"
      ? `<button type="button" data-timer="done">Done now</button><button type="button" data-timer="cancel">Cancel</button>`
      : `<button type="button" data-timer="plus">+15 s</button><button type="button" data-timer="skip">Skip</button>`}</div>`;
}

$timer.addEventListener("click", (e) => {
  const b = e.target.closest("[data-timer]");
  if (!b || !timer) return;
  const act = b.dataset.timer;
  if (act === "plus") { timer.end += 15000; drawTimer(); }
  else if (act === "skip" || act === "cancel") stopTimer(false);
  else if (act === "done") stopTimer(true, Math.max(1, Math.round((Date.now() - timer.start) / 1000)));
});

// --- Guided qigong: one spoken audio file, the picture follows the voice ---------------------------------------------

const $qg = document.getElementById("qg");
const qg = { key: null, steps: [], timeline: [], poll: null, current: -1, lock: null };

async function startQigong(seconds) {
  return startGuided("api/qigong/session", seconds, "Guided Baduanjin");
}

// Any guided session (the full Baduanjin, or today's cool-down): one spoken audio file, the picture follows along.
// mode "breath" (guided leaky can) shows a breathing circle instead, and onEnd runs when the audio finishes.
async function startGuided(url, seconds, title, opts = {}) {
  if (!state.voices) {
    try { state.voices = await api("api/voices"); state.voice = state.voices.selected; } catch { /* use the default voice */ }
  }
  clearTimeout(qg.poll);
  qg.mode = opts.mode || "pictures";
  qg.onEnd = opts.onEnd || null;
  showQg(`<div class="qg-wait"><h3>${esc(title)}</h3><p id="qg-status" class="sub">Getting the voice ready…</p>
    <button type="button" class="btn small" data-qg="close">Cancel</button></div>`);
  try {
    const r = await api(url, { method: "POST", body: JSON.stringify({ voice: state.voice || "lessac", seconds, ...(opts.body || {}) }) });
    qg.key = r.key;
    qg.steps = r.steps;
    pollQigong(r);
  } catch { showQg(`<div class="qg-wait"><p>Couldn't start the session.</p><button type="button" class="btn small" data-qg="close">Close</button></div>`); }
}

function pollQigong(job) {
  const el = document.getElementById("qg-status");
  if (job.status === "error") {
    if (el) el.textContent = `Couldn't make the audio (${job.error || "unknown error"}).`;
    return;
  }
  if (job.status === "ready") return playQigong();
  if (el) el.textContent = job.status === "speaking" ? `Preparing the voice… ${Math.round((job.progress || 0) * 100)}% (first time only)`
    : "Getting the voice ready… (a new voice downloads the first time)";
  qg.poll = setTimeout(async () => {
    try { pollQigong(await api(`api/tts/${qg.key}`)); } catch { if (el) el.textContent = "Lost connection."; }
  }, 1500);
}

async function playQigong() {
  try { qg.timeline = (await api(`api/tts/${qg.key}/timeline`)).timeline; } catch { qg.timeline = []; }
  qg.current = -1;
  const breath = qg.mode === "breath";
  showQg(`${breath ? `<div class="breath-stage"><div class="small muted" id="br-round">Getting ready</div>
      <div class="breath-wrap"><div class="breath-circle" id="br-circle"></div><div class="breath-word" id="br-word"></div></div>
      <div class="breath-count" id="br-count"></div></div>` : `<div class="qg-stage" id="qg-stage"></div>`}
    <audio id="qg-audio" controls autoplay src="api/tts/${esc(qg.key)}/audio" style="width:100%"></audio>
    <div class="row-actions" style="justify-content:${breath ? "center" : "space-between"}">
      ${breath ? "" : `<button type="button" class="btn small" data-qg="prev">◀ Back</button>
      <button type="button" class="btn small" data-qg="next">Next ${I.next}</button>`}
      <button type="button" class="btn small" data-qg="close">Close</button></div>`);
  const audio = document.getElementById("qg-audio");
  if (breath) {
    const loop = () => { drawBreath(audio); if (!audio.paused && !audio.ended) qg.raf = requestAnimationFrame(loop); };
    audio.addEventListener("play", loop);
    audio.addEventListener("seeked", () => drawBreath(audio));
  } else {
    audio.addEventListener("timeupdate", () => drawQigong(audio.currentTime));
  }
  audio.addEventListener("play", async () => { try { qg.lock = await navigator.wakeLock?.request("screen"); } catch { /* not allowed */ } });
  audio.addEventListener("ended", () => {
    qg.lock?.release();
    if (qg.onEnd) qg.onEnd(); else toast("Session complete");
  });
  if (breath) drawBreath(audio); else drawQigong(0);
}

// The circle grows on the in-breath and shrinks on the long out-breath, in step with the voice
function drawBreath(audio) {
  const t = audio.currentTime;
  const i = Math.max(0, qg.timeline.findIndex((s) => t >= s.start && t < s.end));
  const seg = qg.timeline[i] || { start: 0, end: 1 };
  const step = qg.steps[i] || {};
  const f = Math.min(1, Math.max(0, (t - seg.start) / Math.max(0.1, seg.end - seg.start)));
  const ease = (x) => 0.5 - Math.cos(Math.PI * x) / 2;
  const scale = step.kind === "in" ? 0.5 + 0.5 * ease(f) : step.kind === "out" ? 1 - 0.5 * ease(f) : 0.5;
  const circle = document.getElementById("br-circle");
  if (circle) circle.style.transform = `scale(${scale.toFixed(3)})`;
  if (i === qg.current) return;
  qg.current = i;
  const word = document.getElementById("br-word"), count = document.getElementById("br-count"), round = document.getElementById("br-round");
  const perRound = Math.max(...qg.steps.map((s) => s.breath || 0)) || 10;
  const rounds = Math.max(...qg.steps.map((s) => s.round || 0)) || 4;
  if (word) word.textContent = step.kind === "in" ? "Breathe in" : step.kind === "out" ? "Out, slowly" : step.kind === "rest" ? "Rest" : "";
  if (count) count.textContent = step.breath ? `Breath ${step.breath} of ${perRound} · ${(step.round - 1) * perRound + step.breath} of ${rounds * perRound}` : "";
  if (round) round.textContent = step.round ? `Round ${step.round} of ${rounds}` : step.label || "";
}

function drawQigong(t) {
  const i = Math.max(0, qg.timeline.findIndex((s) => t >= s.start && t < s.end));
  if (i === qg.current) return;
  qg.current = i;
  const step = qg.steps[i] || {};
  const moves = qg.steps.length - 2;
  const label = i === 0 ? "Getting ready" : i > moves ? "Finish" : `Step ${i} of ${moves}`;
  const stage = document.getElementById("qg-stage");
  if (stage) {
    stage.innerHTML = `<div class="small muted">${esc(label)}</div><h3 style="margin:4px 0 10px">${esc(step.name || "")}</h3>
      ${step.image ? `<img src="${esc(step.image)}" alt="${esc(step.name || "")}">` : `<div class="qg-breathe"></div>`}
      ${step.note ? `<p class="sub">${esc(step.note)}</p>` : ""}`;
  }
}

function showQg(html) {
  $qg.innerHTML = `<div class="qg-inner">${html}</div>`;
  $qg.hidden = false;
}

$qg.addEventListener("click", (e) => {
  const b = e.target.closest("[data-qg]");
  if (!b) return;
  const audio = document.getElementById("qg-audio");
  const act = b.dataset.qg;
  if (act === "close") {
    clearTimeout(qg.poll);
    cancelAnimationFrame(qg.raf);
    audio?.pause();
    qg.lock?.release();
    $qg.hidden = true;
    $qg.innerHTML = "";
  } else if (audio && qg.timeline.length) {
    const target = Math.min(qg.timeline.length - 1, Math.max(0, qg.current + (act === "next" ? 1 : -1)));
    audio.currentTime = qg.timeline[target].start + 0.05;
    drawQigong(audio.currentTime);
  }
});

// --- Week -------------------------------------------------------------------------------------

// Ski readiness: the same six tests every two weeks until opening day, so you can see the prep working
function skiFmt(t, v) { return v == null ? "–" : `${v % 1 ? v : Math.round(v)}${t.unit === "s" ? " s" : ""}`; }

function skiCard() {
  const s = state.ski;
  if (!s) {
    api("api/skitests").then((r) => { state.ski = r; if (state.tab === "week") render(); }).catch(() => {});
    return `<div class="card muted">Loading ski readiness…</div>`;
  }
  const res = s.results, first = res[0], last = res[res.length - 1];
  const table = res.length ? `<table><thead><tr><th>Test</th>${res.length > 1 ? `<th>${esc(formatDate(first.date))}</th>` : ""}<th>${esc(formatDate(last.date))}</th>${res.length > 1 ? "<th>Change</th>" : ""}</tr></thead><tbody>
    ${s.tests.map((t) => {
      const a = first.values[t.id], b = last.values[t.id];
      const ch = res.length > 1 && a != null && b != null ? b - a : null;
      return `<tr><td>${esc(t.name)}</td>${res.length > 1 ? `<td>${skiFmt(t, a)}</td>` : ""}<td>${skiFmt(t, b)}</td>
        ${res.length > 1 ? `<td>${ch == null ? "" : `${ch > 0 ? "+" : ""}${skiFmt(t, ch)}${ch > 0 ? " ↑" : ""}`}</td>` : ""}</tr>`;
    }).join("")}</tbody></table>` : "";
  const form = state.skiOpen ? `<div class="ski-form">
    <p class="small muted">Warm up first (the daily non-negotiables). Tap Timer to start one, then <strong>Done now</strong> the moment your form breaks: it fills in your time.</p>
    ${s.tests.map((t) => `<div class="ski-test">
      <div><strong>${esc(t.name)}</strong><div class="small muted">${esc(t.how)}</div></div>
      <div class="ski-row">
        <label><input type="number" inputmode="numeric" min="0" step="1" id="ski-${t.id}" data-ski="${t.id}" value="${esc(state.skiVals[t.id] ?? "")}" aria-label="${esc(t.name)}"><span class="unit">${esc(t.unit)}</span></label>
        <button type="button" class="btn small" data-act="ski-timer" data-v="${t.id}">${I.play}${t.count ? "30 s timer" : "Timer"}</button>
      </div></div>`).join("")}
    <div class="row-actions"><button type="button" class="btn primary" style="width:auto" data-act="ski-save">Save results</button>
      <button type="button" class="btn link small" data-act="ski-toggle">Cancel</button></div></div>` : "";
  return `<div class="card${s.due ? " season" : ""}"><strong>Ski readiness</strong>
    <div class="sub">${s.due ? "A check is due now." : `Next check ${esc(formatDate(s.next))}.`} Every ${s.every_days} days: wall sit, single-leg balance, skater steps and side plank.</div>
    ${table}
    ${state.skiOpen ? form : `<div class="row-actions"><button type="button" class="btn small" data-act="ski-toggle">${s.due ? "Do the check now (about 10 min)" : "Do a check anyway"}</button></div>`}
  </div>`;
}

async function renderWeek() {
  const off = state.weekOffset;
  if (!state.week || state.week.offset !== off) state.week = await api(`api/week?offset=${off}`);
  const w = state.week;
  const badge = { done: "done", today: "today", missed: "missed", past: "", upcoming: "" };
  const range = `${formatDate(w.days[0].date)} – ${formatDate(w.days[6].date)}`;
  const navs = [[0, "This week"], [1, "Next week"], [2, "In 2 weeks"], [3, "In 3 weeks"]];
  $view.innerHTML = `
    <div class="week-nav" style="margin-bottom:8px">
      ${navs.map(([v, l]) => `<button type="button" class="btn small" data-act="week-nav" data-v="${v}" ${off === v ? "disabled" : ""}>${l}</button>`).join("")}
    </div>
    <p class="small muted" style="margin:0 0 8px">${esc(range)} · <strong>${esc(w.phase)}</strong>${w.block_week ? ` · week ${w.block_week.n} of your 4-week plan` : ""}</p>
    ${w.block ? `<div class="card"><strong>Your 4-week plan</strong>${w.block.goal ? `<div class="sub">${esc(w.block.goal)}</div>` : ""}
      ${blockWeeks(w.block, true)}
      <div class="small muted" style="margin-top:6px">Each day still follows your morning check-in. Tap a week to see its days.</div>
      <div class="row-actions"><button type="button" class="btn link small" data-act="block-clear">End this plan</button></div></div>` : ""}
    ${w.replan ? `<div class="card season"><strong>You skipped a day, so I re-planned the week</strong>
      <div class="sub">Moved up: ${esc(w.replan.missed.join(", "))}.${w.replan.dropped.length ? ` Left out to keep your rest day: ${esc(w.replan.dropped.join(", "))}.` : ""}</div></div>` : ""}
    ${w.machines && !w.sports?.includes("triathlon") ? `<div class="card"><strong>Cardio machines</strong>
      ${Object.values(w.machines).map((m) => `<div class="sub" style="margin-top:4px"><span class="badge${m.ok ? " pt" : ""}">${m.ok ? "Open" : m.stepped_back ? "Paused" : "Locked"}</span> <strong>${esc(m.name)}</strong>:
        ${m.ok ? `in your plan, ${esc(m.minutes)} easy minutes` : esc(m.why)}</div>`).join("")}</div>` : ""}
    ${w.season ? `<div class="card season"><strong>${esc(w.season.phase)}</strong>${w.season.days > 0 ? ` · ${w.season.days} day${w.season.days === 1 ? "" : "s"} to opening day` : ""}
      <div class="sub">${esc(w.season.text)}</div></div>` : ""}
    ${w.season ? skiCard() : ""}
    ${w.days.map((d) => `<div class="card week-day ${d.status}">
      <div class="week-head"><strong>${esc(d.weekday)}</strong> <span class="muted">${esc(formatDate(d.date))}</span>
        <span class="badge">${esc(d.label)}</span>${badge[d.status] ? `<span class="badge${d.status === "missed" ? " bad" : ""}">${badge[d.status]}</span>` : ""}</div>
      ${d.theme_label ? `<div class="sub">${esc(d.focus === "cardio" ? "Cardio " : "")}${esc(d.theme_label)}${d.replanned ? " · moved up after a skipped day" : ""}</div>` : ""}
      ${d.cardio_text && d.focus === "cardio" ? `<div><strong>${esc(d.cardio_text)}</strong>${d.machine ? ` on the ${esc(d.machine)}` : ""}${d.long ? " (long and easy)" : ""}</div>` : ""}
      ${d.machine_locked ? `<div class="small muted">Your plan has a cardio machine here: walking until it unlocks.</div>` : ""}
      ${d.strength?.length ? `<div class="sub">${esc(d.strength.slice(0, 6).join(", "))}${d.strength.length > 6 ? "…" : ""}</div>` : ""}
      <div class="small muted">${esc(d.mind)}</div>
      ${d.changed ? `<div class="small" style="color:var(--accent)">Changed by your coach${d.note ? `: ${esc(d.note)}` : ""}</div>` : ""}
    </div>`).join("")}
    <div class="row-actions">
      <button type="button" class="btn small" data-act="week-ask">Ask the coach to adjust my week</button>
      <button type="button" class="btn small" data-act="block-ask">Plan my next 4 weeks</button>
      <button type="button" class="btn small" data-act="week-recap">Weekly recap</button>
      <button type="button" class="btn link small" data-act="week-reset">Undo coach changes</button>
    </div>
    <p class="small muted">Each day still adapts to how you feel: a high kidney score always turns the day into recovery.</p>`;
}

// --- Coach ------------------------------------------------------------------------------------

function connectCard() {
  const c = state.claude;
  if (!c || c.signed_in) return "";
  if (!c.cli) return `<div class="card warning">The Claude command-line tool isn't installed in this add-on, so the coach can't sign in.</div>`;
  const l = c.login;
  const failed = l && l.done && l.result && !c.signed_in;
  if (l && !l.done) {
    return `<div class="card">
      <h3>Connect Claude</h3>
      ${l.url ? `<p class="sub">1. Open the link and approve. 2. Paste the code it shows here.</p>
        <p><a class="btn primary" style="display:grid;place-items:center;text-decoration:none" href="${esc(l.url)}" target="_blank" rel="noopener">Open Claude sign-in</a></p>
        <div class="composer" style="position:static;padding:0"><input id="claude-code" class="code-input" placeholder="Paste code" autocomplete="off" aria-label="Sign-in code">
        <button type="button" class="btn primary" style="width:auto" data-act="claude-code">Connect</button></div>`
        : `<p class="sub">Getting a sign-in link…</p>`}
      <button type="button" class="btn link" data-act="claude-cancel">Cancel</button></div>`;
  }
  return `<div class="card warning">
    <p style="margin:0 0 8px">${failed ? esc(l.result) : "The coach needs to be connected to your Claude account."}</p>
    <button type="button" class="btn primary" data-act="claude-login">Connect Claude</button></div>`;
}

async function loadClaude() {
  try { state.claude = await api("api/claude"); } catch { /* keep the old state */ }
  if ((state.tab === "coach" || state.tab === "settings") && !document.activeElement?.matches?.("#claude-code, #coach-input")) render();
  clearTimeout(claudePoll);
  const l = state.claude && state.claude.login;
  if (l && !l.done) claudePoll = setTimeout(loadClaude, 2000);
}
let claudePoll;

// The coach can suggest changes to today's plan; nothing changes until you tap Apply.
function changesBlock(m, i) {
  let html = "";
  if (m.changes?.length && !m.dismissed) {
    html += `<div class="changes"><strong>Suggested changes to today's plan</strong>
      <ul>${m.changes.map((c) => `<li>${esc(c.label)}${c.why ? ` <span class="muted">(${esc(c.why)})</span>` : ""}</li>`).join("")}</ul>
      ${m.applied !== undefined ? `<div class="small muted">${m.applied ? "Applied to today's plan." : "Nothing was changed."}</div>`
        : `<div class="row-actions"><button type="button" class="btn small" data-act="apply-changes" data-i="${i}">Apply</button>
           <button type="button" class="btn small" data-act="dismiss-changes" data-i="${i}">No thanks</button></div>`}</div>`;
  }
  if (m.rejected?.length) html += `<div class="small muted" style="margin-top:6px">Skipped for safety: ${esc(m.rejected.join(" "))}</div>`;
  return html + blockBlock(m, i);
}

// Four weeks of labelled days, used in the coach's reply and on the Week tab.
function blockWeeks(b, onWeekTab) {
  return b.weeks.map((w, n) => {
    const inner = `<div><strong>Week ${n + 1}</strong> · ${esc(formatDate(w.start))} · ${esc(w.phase)}${w.current ? ' <span class="badge">now</span>' : ""}</div>
      ${w.focus ? `<div class="small muted">${esc(w.focus)}</div>` : ""}
      <div class="block-days">${w.days.map((d) => `<span class="block-day ${esc(d.focus)}"><b>${esc(d.weekday)}</b> ${esc(d.label)}</span>`).join("")}</div>`;
    return onWeekTab && w.offset >= 0 && w.offset <= 3
      ? `<button type="button" class="block-week${w.shown ? " shown" : ""}" data-act="week-nav" data-v="${w.offset}">${inner}</button>`
      : `<div class="block-week">${inner}</div>`;
  }).join("");
}

// The coach's 4-week plan: nothing changes until you tap Apply.
function blockBlock(m, i) {
  if (!m.block && !m.block_notes?.length) return "";
  let html = "";
  if (m.block) {
    const done = m.block_applied !== undefined;
    html += `<div class="changes"><strong>Suggested 4-week plan</strong>${m.block.goal ? `<div class="small">${esc(m.block.goal)}</div>` : ""}
      ${blockWeeks(m.block, false)}
      ${done ? `<div class="small muted">${m.block_applied ? "Applied: see the Week tab." : "Not applied."}</div>`
        : `<div class="row-actions"><button type="button" class="btn small" data-act="apply-block" data-i="${i}">Apply the 4 weeks</button>
           <button type="button" class="btn small" data-act="dismiss-block" data-i="${i}">No thanks</button></div>`}</div>`;
  }
  if (m.block_notes?.length) html += `<div class="small muted" style="margin-top:6px">Adjusted for safety: ${esc(m.block_notes.join(" "))}</div>`;
  return html;
}

const COACH_GREETING = { role: "assistant", content: "Hey Joe, how did the left flank feel during those wall sits today?" };

// The chat lives on the add-on, so the phone and the PC show the same conversation. This device brings it in, and
// picks up what the other device wrote (and whether it is waiting on a reply) while the Coach tab is open.
async function loadCoach() {
  try {
    let r = await api("api/coach/chat");
    // one time: the chat this device had saved on its own moves to the shared chat, if that is still empty
    const local = store.get("coach", null);
    if (!r.messages.length && Array.isArray(local) && local.some((m) => m.role === "user")) {
      try { r = await api("api/coach/chat/import", { method: "POST", body: JSON.stringify({ messages: local }) }); } catch { /* try again next time */ }
    }
    if (local) store.remove("coach");
    const sig = (list, busy) => JSON.stringify([list.map((m) => [m.id, m.applied, m.dismissed]), busy]);
    const changed = !state.coachLoaded || sig(r.messages, r.busy) !== sig(state.coach, state.coachRemoteBusy);
    state.coach = r.messages;
    state.coachRemoteBusy = r.busy;
    state.coachLoaded = true;
    return changed;
  } catch { return false; }
}

let coachPoll;
function pollCoach() {
  clearTimeout(coachPoll);
  if (state.tab !== "coach" || document.visibilityState !== "visible") return;
  coachPoll = setTimeout(async () => {
    if (state.tab === "coach" && !state.coachBusy && await loadCoach() && state.tab === "coach") renderCoach(true);
    pollCoach();
  }, 6000);
}

function renderCoach(keepScroll) {
  if (!state.claude) loadClaude();
  if (!state.coachLoaded) {
    $view.innerHTML = `<div class="spinner">Loading your chat…</div>`;
    loadCoach().then(() => { if (state.tab === "coach") renderCoach(); });
    return;
  }
  const typing = document.getElementById("coach-input");
  const hadFocus = typing && document.activeElement === typing;
  if (typing) state.coachDraft = typing.value;      // a refresh must not lose what you're typing
  const signedOut = state.claude && !state.claude.signed_in;
  const list = state.coach.length ? state.coach : [COACH_GREETING];
  const waiting = state.coachBusy || state.coachRemoteBusy;
  $view.innerHTML = `
    ${signedOut ? `<div class="card warning"><p style="margin:0 0 8px">The coach isn't connected to your Claude account yet.</p>
      <button type="button" class="btn primary" data-act="goto-settings">Connect in Settings</button></div>` : ""}
    <div class="chat">
      ${list.map((m, i) => `<div class="msg ${m.role}${m.error ? " error" : ""}">${esc(m.content)}${changesBlock(m, i)}</div>`).join("")}
      ${waiting ? `<div class="msg assistant muted">Coach is thinking…</div>` : ""}
    </div>
    <div class="composer">
      <textarea id="coach-input" enterkeyhint="send" placeholder="E.g. my kidney is tight today…" aria-label="Message the coach">${esc(state.coachDraft)}</textarea>
      <button type="button" class="btn primary" style="width:auto" data-act="send" ${state.coachBusy || signedOut ? "disabled" : ""}>Send</button>
    </div>
    ${state.coach.length ? `<div class="small muted" style="text-align:center"><button type="button" class="btn link small muted-link" data-act="coach-clear">Clear chat</button>
      · shared with your other devices</div>` : ""}`;
  if (hadFocus) { const t = document.getElementById("coach-input"); t.focus(); t.setSelectionRange(t.value.length, t.value.length); }
  if (!signedOut && !keepScroll) window.scrollTo({ top: document.body.scrollHeight });
  pollCoach();
}

async function sendCoach() {
  if (!state.coachLoaded) await loadCoach();       // the Weekly recap button sends before the chat has loaded
  const input = document.getElementById("coach-input");
  const message = (input ? input.value : state.coachDraft).trim();
  if (!message || state.coachBusy) return;
  state.coachDraft = "";
  if (input) input.value = "";       // renderCoach keeps what is typed, so empty the box first
  state.coach.push({ role: "user", content: message });   // shown at once; the saved copy replaces it below
  state.coachBusy = true;
  renderCoach();
  try {
    await api("api/coach", { method: "POST", body: JSON.stringify({ message }) });
  } catch {
    // the connection dropped: the add-on may still have answered, so look again before giving up
  }
  state.coachBusy = false;
  await loadCoach();
  const last = state.coach[state.coach.length - 1];
  if (last?.error) state.claude = null;  // re-check sign-in after a failure
  if (state.tab === "coach") renderCoach();
}

// --- Settings ---------------------------------------------------------------------------------
// One tab for everything you can change. New sections (sports, training goals) go in as more cards.

function haCard() {
  const h = state.ha;
  if (!h) {
    api("api/ha").then((r) => { state.ha = r; if (state.tab === "settings") renderSettings(); }).catch(() => { state.ha = { available: false }; });
    return `<div class="card muted">Checking Home Assistant…</div>`;
  }
  if (!h.available) return `<div class="card"><p class="sub" style="margin:0">Restart the add-on after this update to connect it to Home Assistant.</p></div>`;
  const r = h.reminder;
  return `<div class="card">
    <p class="sub" style="margin:0 0 8px"><strong>Sensors:</strong> <code>sensor.workout_today</code> and <code>sensor.workout_streak</code> stay up to date. Add them to any dashboard.</p>
    <label class="toggle"><input type="checkbox" id="ha-on" ${r.enabled ? "checked" : ""}> Morning check-in reminder to my phone</label>
    <div class="two-col" style="margin-top:8px">
      <input type="time" id="ha-time" class="code-input" value="${esc(r.time)}" aria-label="Reminder time">
      <select id="ha-service" aria-label="Phone">${h.services.length
        ? h.services.map((s) => `<option value="${esc(s)}"${s === r.service ? " selected" : ""}>${esc(s.replace(/^mobile_app_/, "").replace(/_/g, " "))}</option>`).join("")
        : `<option value="">No phone found</option>`}</select>
    </div>
    ${h.services.length ? "" : `<p class="small muted">Install the Home Assistant app on your phone and sign in, then come back here.</p>`}
    <p class="small muted">It only comes if you haven't checked in or worked out yet that day. Tapping it opens this app.</p>
    <div class="row-actions"><button type="button" class="btn small" data-act="ha-save">Save</button>
      <button type="button" class="btn small" data-act="ha-test" ${h.services.length ? "" : "disabled"}>Send a test</button></div>
  </div>`;
}

// At the PT office: a zone in Home Assistant around the office; arriving there sends the "ask about new exercises" reminder
function ptVisitCard() {
  const h = state.ha;
  if (!h || !h.available) return "";
  const v = h.pt_visit || {};
  const d = state.ptv ||= { enabled: v.enabled, address: v.address || "", label: v.label || "", lat: v.lat, lon: v.lon,
    radius: v.radius || 150, person: v.person || h.persons[0]?.id || "", service: v.service || h.services[0] || "", matches: null, msg: "" };
  const where = d.lat != null
    ? `<div class="small" style="margin-top:6px">${I.pin} ${esc(d.label || `${d.lat.toFixed(5)}, ${d.lon.toFixed(5)}`)}
        <a href="https://www.openstreetmap.org/?mlat=${d.lat}&mlon=${d.lon}#map=17/${d.lat}/${d.lon}" target="_blank" rel="noopener">map</a></div>`
    : "";
  return `<div class="card"><h3>Reminder at the PT office</h3>
    <label class="toggle"><input type="checkbox" data-ptv="enabled" ${d.enabled ? "checked" : ""}> When I arrive, remind me to ask about new exercises</label>
    <label class="sub" for="ptv-address" style="display:block;margin-top:8px">PT office address</label>
    <div class="composer" style="position:static;padding:0">
      <input id="ptv-address" class="code-input" data-ptv="address" value="${esc(d.address)}" placeholder="Street, town" autocomplete="street-address">
      <button type="button" class="btn small" style="width:auto" data-act="ptv-find">Find</button></div>
    ${d.matches ? (d.matches.length ? `<div class="small muted" style="margin-top:6px">Pick the right one:</div>
      ${d.matches.map((m, i) => `<button type="button" class="btn small" style="display:block;width:100%;text-align:left;margin-top:6px;height:auto;padding:8px 12px"
        data-act="ptv-pick" data-i="${i}">${esc(m.label)}</button>`).join("")}`
      : `<div class="small" style="margin-top:6px">No match. Try adding the town or postcode, or use your location while you're there.</div>`) : ""}
    <button type="button" class="btn link small" data-act="ptv-here">${I.pin}I'm at the office now: use my current location</button>
    ${where}
    <div class="sub" style="margin-top:8px">Counts as "there" within</div>
    <div class="chips wrap">${[100, 150, 300].map((r) => `<button type="button" class="chip${d.radius === r ? " on" : ""}" data-act="ptv-radius" data-v="${r}">${r} m</button>`).join("")}</div>
    <div class="two-col" style="margin-top:8px">
      <select data-ptv="person" aria-label="Whose phone">${h.persons.length ? h.persons.map((x) => `<option value="${esc(x.id)}"${x.id === d.person ? " selected" : ""}>${esc(x.name)}</option>`).join("") : `<option value="">No people in Home Assistant</option>`}</select>
      <select data-ptv="service" aria-label="Notify phone">${h.services.map((s) => `<option value="${esc(s)}"${s === d.service ? " selected" : ""}>${esc(s.replace(/^mobile_app_/, "").replace(/_/g, " "))}</option>`).join("")}</select>
    </div>
    <p class="small muted">Uses your phone's location from the Home Assistant app, checked every minute; it comes once per visit day and lists the PT exercises you're doing now.
      The address is looked up on OpenStreetMap. ${v.inside ? "<strong>You're at the PT office now.</strong>" : ""}</p>
    ${d.msg ? `<div class="small" style="color:var(--accent)">${esc(d.msg)}</div>` : ""}
    <div class="row-actions"><button type="button" class="btn small" data-act="ptv-save">Save</button>
      <button type="button" class="btn small" data-act="ptv-test" ${h.services.length ? "" : "disabled"}>Send a test</button></div></div>`;
}

function garminCard() {
  const g = state.garmin;
  if (!g) return `<div class="card muted">Checking Garmin…</div>`;
  const msg = state.garminMsg ? `<div class="small" style="margin-top:8px">${esc(state.garminMsg)}</div>` : "";
  if (g.connected) {
    return `<div class="card"><h3>Garmin connected</h3>
      <p class="sub">${g.last ? `Last sync ${esc(formatDate(g.last.date))}${g.last.resting_hr ? ` · resting heart rate ${esc(g.last.resting_hr)}` : ""}` : "No data yet. Tap Sync now."}.
        The coach reads resting heart rate, HRV, sleep and your latest activity. It syncs every few hours.
        Ski days and cardio your watch records show up on Today, ready to log with a tap (it looks for new ones every hour).</p>
      <label class="toggle" style="margin-top:8px"><input type="checkbox" id="garmin-adjust" data-act-change="garmin-adjust" ${state.settings?.garmin_adjust ? "checked" : ""}>
        Make days lighter when Garmin shows poor recovery</label>
      <p class="small muted" style="margin:2px 0 0">Compared with your own last two weeks: short sleep (under 6 h), low body battery (under 30), HRV well below your usual,
        or resting heart rate 5+ above your usual. One sign makes the day lighter, two or more make it a recovery day.</p>
      <div class="row-actions"><button type="button" class="btn small" data-act="garmin-sync">Sync now</button>
        <button type="button" class="btn small" data-act="garmin-disconnect">Disconnect</button></div>${msg}</div>`;
  }
  if (g.needs_mfa) {
    return `<div class="card"><h3>Enter the Garmin code</h3><p class="sub">Garmin sent a verification code to your email or phone.</p>
      <div class="composer" style="position:static;padding:0"><input id="garmin-code" class="code-input" inputmode="numeric" autocomplete="one-time-code" placeholder="Code">
      <button type="button" class="btn primary" style="width:auto" data-act="garmin-mfa">Verify</button></div>${msg}</div>`;
  }
  return `<div class="card"><h3>Connect Garmin</h3>
    <p class="sub">Your password is used once to sign in and is not saved. Only a login token stays on your Home Assistant.</p>
    <input id="garmin-email" type="email" class="code-input" style="width:100%;margin-bottom:8px" placeholder="Garmin email" autocomplete="username">
    <input id="garmin-pass" type="password" class="code-input" style="width:100%" placeholder="Garmin password" autocomplete="current-password">
    <div class="row-actions"><button type="button" class="btn primary" style="width:auto" data-act="garmin-connect">Connect Garmin</button></div>${msg}</div>`;
}

async function loadGarmin() {
  try { state.garmin = await api("api/garmin"); } catch { state.garmin = { connected: false }; }
  if (state.tab === "settings" && !document.activeElement?.matches?.("input, textarea")) render();
}

// Exercises your PT gives you: added here, they show up on Today on the days you pick
function ptSection(list) {
  const f = state.ptForm;
  const form = f ? `<div class="pt-form">
    <label class="sub" for="pt-name">Exercise name</label>
    <input id="pt-name" class="code-input" style="width:100%" maxlength="80" data-pt="name" value="${esc(f.name)}" placeholder="e.g. Leaky can breathing">
    <label class="sub" for="pt-dose">Dose</label>
    <input id="pt-dose" class="code-input" style="width:100%" maxlength="80" data-pt="dose" value="${esc(f.dose)}" placeholder="e.g. 40 breaths · 3 x 10 · 3 x 30 s hold">
    <div class="small muted">Put seconds in the dose (like "3 x 30 s hold") and it gets a timer.</div>
    <label class="sub" for="pt-cues">How to do it (one step per line)</label>
    <textarea id="pt-cues" data-pt="cues" placeholder="What your PT told you">${esc(f.cues)}</textarea>
    <div class="sub" style="margin-top:8px">Where it goes</div>
    <div class="chips wrap">${[["warmup", "Daily non-negotiables (tick box)"], ["strength", "With strength (sets)"]].map(([v, l]) =>
      `<button type="button" class="chip${f.section === v ? " on" : ""}" data-act="pt-section" data-v="${v}">${l}</button>`).join("")}</div>
    ${f.section === "strength" ? `<label class="sub" for="pt-sets">Sets (a dose like "2 x 12" sets this for you)</label>
      <input id="pt-sets" type="number" min="1" max="10" class="code-input" style="width:90px" data-pt="sets" value="${esc(f.sets)}">` : ""}
    <div class="sub" style="margin-top:8px">Which days</div>
    <div class="chips wrap"><button type="button" class="chip${f.days.length ? "" : " on"}" data-act="pt-day" data-v="all">Every day</button>
      ${DAY_NAMES.map((d, i) => `<button type="button" class="chip${f.days.includes(i) ? " on" : ""}" data-act="pt-day" data-v="${i}">${d}</button>`).join("")}</div>
    <div class="row-actions"><button type="button" class="btn primary" style="width:auto" data-act="pt-save">Save</button>
      <button type="button" class="btn link small" data-act="pt-cancel">Cancel</button></div></div>` : "";
  return `<h2>From your PT</h2>
    <div class="card">
      <p class="sub" style="margin:0 0 8px">Exercises your physio gives you. They show up on Today on the days you pick, with a PT tag, and go in the PT report.</p>
      ${list.map((p, i) => `<div class="paused-row"><span><strong>${esc(p.name)}</strong>
        <span class="small muted" style="display:block">${esc(p.dose || "no dose set")} · ${esc(ptDays(p.days))} · ${p.section === "strength" ? `${p.sets} sets with strength` : "daily non-negotiables"}</span></span>
        <span style="white-space:nowrap"><button type="button" class="btn link small" data-act="pt-edit" data-i="${i}">Edit</button>
        <button type="button" class="btn link small muted-link" data-act="pt-remove" data-i="${i}">Remove</button></span></div>`).join("")}
      ${f ? form : `<div class="row-actions"><button type="button" class="btn small" data-act="pt-edit" data-i="-1">${I.plus}Add an exercise from my PT</button></div>`}
    </div>`;
}

function bioSettingsCard(s) {
  const b = s.biofeedback || {};
  return `<h2>Pelvic floor biofeedback</h2>
    <div class="card">
      <label class="toggle"><input type="checkbox" data-act-change="bio-enabled" ${b.enabled ? "checked" : ""}> Track my manometric biofeedback sessions</label>
      <p class="small muted" style="margin:2px 0 0">Log the readings from each session with your pelvic PT (resting tone, peak squeeze, hold, relaxing time).
        History charts them, the PT report includes them, and Today reminds you when the next one is due.</p>
      ${b.enabled ? `<div class="sub" style="margin-top:10px">Pressure unit (what your PT's screen shows)</div>
        <div class="chips wrap">${(s.bio_units || []).map((u) => `<button type="button" class="chip${b.unit === u ? " on" : ""}" data-act="bio-setting" data-k="unit" data-v="${esc(u)}">${esc(u)}</button>`).join("")}</div>
        <div class="sub" style="margin-top:10px">Sessions every</div>
        <div class="chips wrap">${[7, 14, 21, 28].map((d) => `<button type="button" class="chip${b.every_days === d ? " on" : ""}" data-act="bio-setting" data-k="every_days" data-v="${d}">${d === 7 ? "week" : `${d / 7} weeks`}</button>`).join("")}</div>
        <div class="row-actions"><button type="button" class="btn small" data-act="bio-go">Log a session</button></div>` : ""}
    </div>`;
}

function waterSettingsCard(s) {
  const w = s.water || { goal: 80, nudge: true, time: "14:00" };
  return `<h2>Water</h2>
    <div class="card">
      <label class="sub" for="water-goal">Daily goal (oz). Use what your doctor recommends for your kidney.</label>
      <input id="water-goal" type="number" min="16" max="300" step="4" class="code-input" style="width:120px" value="${esc(w.goal)}">
      <label class="toggle" style="margin-top:8px"><input type="checkbox" id="water-nudge" ${w.nudge ? "checked" : ""}> Nudge my phone if I'm under half by</label>
      <input id="water-time" type="time" class="code-input" style="width:140px" value="${esc(w.time)}" aria-label="Nudge time">
      <p class="small muted">Uses the phone picked for the morning reminder. Home Assistant also gets <code>sensor.workout_water_today</code>.</p>
      <div class="row-actions"><button type="button" class="btn small" data-act="water-save">Save</button></div>
    </div>`;
}

// Scale and BP monitor through Home Assistant (e.g. its Withings integration): pick the sensors once
function bodySensorsCard() {
  const b = state.bodySensors;
  if (!b) {
    api("api/body/sensors").then((r) => { state.bodySensors = r; if (state.tab === "settings") renderSettings(); }).catch(() => { state.bodySensors = { available: false }; });
    return `<h2>Scale and blood pressure</h2><div class="card muted">Checking Home Assistant…</div>`;
  }
  if (!b.available) {
    return `<h2>Scale and blood pressure</h2><div class="card"><p class="sub" style="margin:0">Needs the connection to Home Assistant. You can still add weight and blood pressure by hand in History.</p></div>`;
  }
  const o = b.options || {}, c = b.chosen || {};
  const guess = (list, word) => (list || []).find((x) => x.id.includes(word))?.id || "";
  const pick = (id, list, sel, empty) => `<select id="${id}" style="width:100%"><option value="">${empty}</option>${(list || []).map((x) =>
    `<option value="${esc(x.id)}"${x.id === sel ? " selected" : ""}>${esc(x.name)} (${esc(x.state)} ${esc(x.unit || "")})</option>`).join("")}</select>`;
  const none = !(o.weight?.length || o.bp?.length);
  const st = b.status || {};
  const when = (ts) => { if (!ts) return "none yet"; const d = new Date(ts); return `${formatDate(ts.slice(0, 10))}, ${d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`; };
  const linkedNow = c.weight_entity || c.sys_entity;
  const statusLine = !linkedNow ? "" : `<div class="small" style="margin:8px 0 0"><strong>${st.weight || st.bp ? "Connected" : "Linked, waiting for a reading"}</strong>
      · last weigh-in copied: ${esc(when(st.weight))} · last blood pressure: ${esc(when(st.bp))}${st.last_check ? ` · checked ${esc(when(st.last_check))}` : ""}</div>`;
  return `<h2>Scale and blood pressure</h2>
    <div class="card">
      <p class="sub" style="margin:0 0 8px">Readings from your Withings scale and BP monitor come in through Home Assistant's Withings integration.
        ${none ? `<strong>No scale or BP sensors found yet.</strong> In Home Assistant go to Settings › Devices &amp; services › Add integration › Withings,
          sign in to Withings there, then come back and reopen this page.` : "Pick the sensors once; new readings are copied in every few minutes and kept here for good."}</p>
      ${none ? "" : `<label class="sub">Weight</label>${pick("bs-weight", o.weight, c.weight_entity ?? guess(o.weight, "weight"), "Not linked")}
        <div class="two-col" style="margin-top:8px">
          <div><label class="sub">Systolic (top)</label>${pick("bs-sys", o.bp, c.sys_entity ?? guess(o.bp, "systolic"), "Not linked")}</div>
          <div><label class="sub">Diastolic (bottom)</label>${pick("bs-dia", o.bp, c.dia_entity ?? guess(o.bp, "diastolic"), "Not linked")}</div></div>
        <label class="sub" style="display:block;margin-top:8px">Pulse (optional)</label>${pick("bs-pulse", o.pulse, c.pulse_entity ?? guess(o.pulse, "pulse"), "Not linked")}
        ${statusLine}
        ${state.bodyMsg ? `<div class="small" style="margin-top:8px;color:var(--accent)">${esc(state.bodyMsg)}</div>` : ""}
        <div class="row-actions"><button type="button" class="btn small" data-act="sensors-save">Save and copy readings</button></div>`}
    </div>`;
}

const isInstalled = () => window.matchMedia?.("(display-mode: standalone)").matches || navigator.standalone === true;

function installCard() {
  if (isInstalled()) return `<div class="card"><h3>Installed</h3><p class="sub">You're using the home-screen app.</p></div>`;
  const a = state.install;
  if (!a) {
    api("api/install").then((r) => { state.install = r; if (state.tab === "settings") renderSettings(); }).catch(() => { state.install = { url: null }; if (state.tab === "settings") renderSettings(); });
    return `<div class="card muted">Checking…</div>`;
  }
  if (!a.url) {
    return `<div class="card"><p class="sub" style="margin:0">To install it, publish the add-on's port first: in Home Assistant go to Settings › Add-ons › AI Workout Tracker ›
      Configuration, and under <strong>Network</strong> enter <strong>8501</strong>. Save, restart the add-on, then come back here.</p></div>`;
  }
  return `<div class="card">
    <p class="sub" style="margin:0 0 8px">Gives you a Workouts icon on your phone that opens full screen, straight to Today, without the Home Assistant frame.</p>
    <ol class="steps">
      <li>On your phone, on home Wi-Fi, open <a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.url)}</a>
        <button type="button" class="btn link small" data-act="copy" data-v="${esc(a.url)}">Copy</button>${a.fallback ? `<br><span class="small muted">If that doesn't open, try ${esc(a.fallback)}</span>` : ""}</li>
      <li><strong>iPhone (Safari):</strong> Share ⬆️ › Add to Home Screen.<br><strong>Android (Chrome):</strong> ⋮ › Add to Home screen.</li>
    </ol>
    <p class="small muted">It works at home or over a VPN to home. Away from home, use the Home Assistant app as usual. This address has no login of its own,
      so anyone on your home Wi-Fi could open it (that's already true with the port published). On Android, Chrome may keep its address bar on a plain http address.</p>
  </div>`;
}

// Settings, History and the PT report re-render from several places; each time, add their links to sections
async function renderSettings() { await renderSettingsPage(); addContents(); }
async function renderHistory() { await renderHistoryPage(); addContents(); }
async function renderReport() { await renderReportPage(); addContents(); }

async function renderSettingsPage() {
  if (!state.garmin) loadGarmin();
  if (!state.claude) loadClaude();
  if (!state.settings) state.settings = await api("api/settings");
  const s = state.settings;
  const mine = new Set(s.equipment);
  const c = state.claude;
  const sports = new Set(s.sports);
  $view.innerHTML = `
    ${ptSection(s.pt_exercises || [])}
    ${bioSettingsCard(s)}
    ${waterSettingsCard(s)}
    ${bodySensorsCard()}
    <h2>Sports</h2>
    <div class="card">
      <p class="sub" style="margin:0 0 10px">What you're training for. Your daily extras and the coach follow this. Everything still goes through your kidney and pelvic-floor safety filter.</p>
      <div class="chips wrap">${s.sport_options.map((o) =>
        `<button type="button" class="chip${sports.has(o.id) ? " on" : ""}" data-act="sport" data-v="${esc(o.id)}" aria-pressed="${sports.has(o.id)}">${esc(o.label)}</button>`).join("")}</div>
      <label class="sub" for="season" style="display:block;margin-top:12px">Snow season starts (optional)</label>
      <input type="date" id="season" class="code-input" style="width:100%" value="${esc(s.season_start)}">
      <div class="row-actions"><button type="button" class="btn small" data-act="save-season">Save date</button></div>
    </div>
    ${s.paused?.length ? `<h2>Paused exercises</h2>
    <div class="card">
      <p class="sub" style="margin:0 0 8px">Exercises you marked "Bothered me". They sit out until the date, then come back with a go-lighter reminder.</p>
      ${s.paused.map((x) => `<div class="paused-row"><span>${esc(x.name)} <span class="muted small">until ${esc(formatDate(x.until))}</span></span>
        <button type="button" class="btn small" data-act="unpause" data-name="${esc(x.name)}">Bring back</button></div>`).join("")}
    </div>` : ""}
    ${s.machines ? `<h2>Peloton and rower</h2>
    <div class="card">
      <p class="sub" style="margin:0 0 8px">They come back into your plan on their own once your scores stay low. Your PT can overrule that here.</p>
      ${Object.entries(s.machines).map(([k, m]) => `<div style="margin:10px 0 4px"><strong>${esc(m.name)}</strong>
        <span class="muted small">${m.ok ? `unlocked, ${esc(m.minutes)} min` : "locked"}</span></div>
        <div class="small muted">${esc(m.why)}</div>
        <div class="chips wrap" style="margin-top:6px">${[["auto", "Automatic"], ["cleared", "PT cleared it"], ["not_yet", "Not yet"]].map(([v, l]) =>
          `<button type="button" class="chip${m.override === v ? " on" : ""}" data-act="machine" data-m="${k}" data-v="${v}">${l}</button>`).join("")}</div>`).join("")}
    </div>` : ""}
    <h2>Equipment</h2>
    <div class="card">
      <p class="sub" style="margin:0 0 10px">Daily plans only use what's ticked. Barbell moves stay out of your plans for your kidney either way.</p>
      <div class="chips wrap">${s.equipment_options.map((o) =>
        `<button type="button" class="chip${mine.has(o) ? " on" : ""}" data-act="equip" data-v="${esc(o)}" aria-pressed="${mine.has(o)}">${esc(o)}</button>`).join("")}</div>
    </div>
    <div class="card">
      <label class="sub" for="gear-notes">Gear details (the coach reads this: weights, plates, tensions)</label>
      <textarea id="gear-notes" style="min-height:150px">${esc(s.gear_notes)}</textarea>
      <p class="sub" style="margin:12px 0 6px">Weights you own. Suggested weights only go up to one of these, one step at a time.</p>
      <label class="sub" for="w-dumbbell">Dumbbells (lb, separated by commas)</label>
      <input id="w-dumbbell" class="code-input" style="width:100%" inputmode="decimal" value="${esc((s.weights?.dumbbell || []).join(", "))}">
      <label class="sub" for="w-kettlebell">Kettlebells (lb)</label>
      <input id="w-kettlebell" class="code-input" style="width:100%" inputmode="decimal" value="${esc((s.weights?.kettlebell || []).join(", "))}">
      <div class="two-col" style="align-items:end">
        <div><label class="sub" for="w-bar">Smallest jump on the barbell or EZ bar (lb)</label>
          <input id="w-bar" class="code-input" style="width:100%" type="number" min="1" max="25" step="0.5" value="${esc(s.weights?.bar_step ?? 5)}"></div>
        <div><label class="sub" for="w-cable">Cable machine step (lb)</label>
          <input id="w-cable" class="code-input" style="width:100%" type="number" min="1" max="25" step="0.5" value="${esc(s.weights?.cable_step ?? 5)}"></div>
      </div>
      <div class="row-actions"><button type="button" class="btn small" data-act="save-gear">Save gear details</button></div>
    </div>
    <h2>Yoga pictures</h2>
    ${s.media_private ? `<div class="card"><h3>Private bucket details saved</h3><p class="sub">Pictures load from your private bucket through this add-on. Tap the button to check that it really works.</p>
      <div class="row-actions"><button type="button" class="btn small" data-act="media-test">Test connection</button></div>
      <div id="media-test-result" class="small" style="margin-top:8px">${esc(state.mediaTest || "")}</div></div>`
    : `<div class="card">
      <p class="sub" style="margin:0 0 10px">For a private bucket, fill in the bucket settings (endpoint, name, key) in this add-on's Configuration tab, the same as for the Trading Terminal. Or, for a public folder, paste its address:</p>
      <label class="sub" for="media-url">Address of the folder holding the yoga pictures (starts with https://)</label>
      <input type="url" id="media-url" class="code-input" style="width:100%" value="${esc(s.media_base_url)}" placeholder="https://…/workout/yoga">
      <div class="row-actions"><button type="button" class="btn small" data-act="save-media">Save</button></div>
    </div>`}
    <h2>Install as an app</h2>
    ${installCard()}
    <h2>Home Assistant</h2>
    ${haCard()}
    ${ptVisitCard()}
    <h2>Garmin</h2>
    ${garminCard()}
    <h2>AI Coach</h2>
    ${c && c.signed_in
      ? `<div class="card"><h3>Claude connected</h3><p class="sub">The coach uses your Claude subscription.</p>
         <button type="button" class="btn small" data-act="claude-logout">Disconnect Claude</button></div>`
      : connectCard() || `<div class="card muted">Checking Claude…</div>`}
    `;
}

// --- Mind & Body: yoga, qigong ----------------------------------------------------------------

function findMind(name) {
  const pools = [state.mind?.yoga, state.mind?.qigong, state.plan?.cooldown?.cards];
  for (const pool of pools) { const hit = (pool || []).find((e) => e.name === name); if (hit) return hit; }
  return null;
}

function mindCard(e) {
  const key = `m:${e.name}`;
  const open = state.open.has(key);
  return `<div class="card" data-card="${esc(key)}">
    <button type="button" class="result" data-act="toggle" data-key="${esc(key)}" aria-expanded="${open}">
      <h3>${esc(e.name)}</h3>
      <div class="stats">
        ${e.category ? `<span class="badge">${esc(e.category)}</span>` : ""}
        ${e.level ? `<span class="badge">${esc(e.level)}</span>` : ""}
        ${e.cooldown ? `<span class="badge">cool-down</span>` : ""}
        ${e.safe ? "" : `<span class="badge bad">not in auto picks</span>`}
      </div>
    </button>
    ${open ? howTo(e) + photoActions(e) : ""}
  </div>`;
}

// Your own photo of a pose: offered on poses with no picture, and replaceable or removable once added
function photoActions(e) {
  if (!e.slug) return "";
  if (e.own_photo) {
    return `<div class="row-actions"><button type="button" class="btn small" data-act="pose-photo" data-v="${esc(e.slug)}">${I.camera}Replace my photo</button>
      <button type="button" class="btn link small muted-link" data-act="pose-photo-remove" data-v="${esc(e.slug)}">Remove my photo</button></div>`;
  }
  if (e.images?.length) return "";
  return `<div class="row-actions"><button type="button" class="btn small" data-act="pose-photo" data-v="${esc(e.slug)}">${I.camera}Add your photo</button></div>
    <p class="small muted" style="margin-top:0">Take one of yourself in the pose, or pick one from your photos. It's kept on your Home Assistant.</p>`;
}

// A phone photo is several MB; shrink it to 1000 px on its long side as a JPEG before it is sent
async function shrinkPhoto(file, size = 1000) {
  let img;
  try { img = await createImageBitmap(file, { imageOrientation: "from-image" }); }
  catch {
    img = await new Promise((ok, fail) => {
      const el = new Image();
      el.onload = () => ok(el);
      el.onerror = fail;
      el.src = URL.createObjectURL(file);
    });
  }
  const w = img.width || img.naturalWidth, h = img.height || img.naturalHeight;
  const k = Math.min(1, size / Math.max(w, h));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(w * k);
  canvas.height = Math.round(h * k);
  canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.85);
}

// After a pose photo changes: Mind & Body and today's cool-down both show it
async function afterPosePhoto() {
  state.mind = null;
  if (state.plan?.cooldown?.cards?.length) await refreshPlan().catch(() => {});
  render();
}

// Meditation: guided audio streamed from The Holistic Care, plus a script Claude writes and the phone reads aloud.
const speech = { queue: [], on: false };

function stopSpeaking() {
  speech.on = false;
  speech.queue = [];
  try { window.speechSynthesis.cancel(); } catch { /* not supported */ }
}

function speakScript(text) {
  if (!("speechSynthesis" in window)) { toast("This browser can't read aloud"); return; }
  stopSpeaking();
  speech.on = true;
  speech.queue = text.split(/\n+/).map((p) => p.trim()).filter(Boolean);
  const next = () => {
    if (!speech.on || !speech.queue.length) { speech.on = false; return; }
    const u = new SpeechSynthesisUtterance(speech.queue.shift().replace(/\.{3}/g, ", , ,"));
    u.rate = 0.82;
    u.onend = () => setTimeout(next, 2500);   // a breath between paragraphs
    u.onerror = () => { speech.on = false; };
    window.speechSynthesis.speak(u);
  };
  next();
}

// Natural voices (Piper) made on the add-on. The phone's own voice is only a fallback.
function voicePicker() {
  const v = state.voices;
  if (!v) return "";
  return `<div class="voice-pick">
    <select id="voice" aria-label="Voice" data-act-change="voice">${v.voices.map((o) =>
      `<option value="${esc(o.id)}"${o.id === state.voice ? " selected" : ""}>${esc(o.label)} · ${esc(o.blurb)}${o.ready ? "" : " (downloads first time)"}</option>`).join("")}</select>
    <button type="button" class="btn small" data-act="voice-preview">${I.play}Hear this voice</button>
  </div>`;
}

function audioBlock() {
  const a = state.audio;
  if (!a) return "";
  if (a.status === "ready") return `<audio controls autoplay src="api/tts/${esc(a.key)}/audio" style="width:100%;margin-top:10px"></audio>`;
  if (a.status === "error") return `<div class="warning" style="margin-top:8px">Couldn't make the audio (${esc(a.error || "unknown error")}).</div>`;
  const first = !state.voices?.voices.find((o) => o.id === state.voice)?.ready;
  return `<div class="sub" id="tts-status" style="margin-top:10px">${a.status === "speaking" ? `Preparing audio… ${Math.round((a.progress || 0) * 100)}%`
    : first ? "Downloading the voice (about 60 MB, first time only)…" : "Getting ready…"}</div>`;
}

let audioPoll;
async function startAudio(text, preview = false) {
  clearTimeout(audioPoll);
  try {
    state.audio = await api("api/tts", { method: "POST", body: JSON.stringify({ voice: state.voice, text, preview }) });
  } catch { state.audio = { status: "error", error: "couldn't reach the add-on" }; }
  render();
  pollAudio();
}

function pollAudio() {
  clearTimeout(audioPoll);
  const a = state.audio;
  if (!a || a.status === "ready" || a.status === "error") return;
  audioPoll = setTimeout(async () => {
    try { state.audio = await api(`api/tts/${a.key}`); } catch { state.audio = { status: "error", error: "lost connection" }; }
    const el = document.getElementById("tts-status");
    if (state.audio.status === "ready" || state.audio.status === "error" || !el) { if (state.tab === "mind") render(); }
    else el.textContent = state.audio.status === "speaking" ? `Preparing audio… ${Math.round((state.audio.progress || 0) * 100)}%` : el.textContent;
    pollAudio();
  }, 1500);
}

function meditationSection() {
  const md = state.med;
  const f = state.medFilter;
  if (!md) return `<h2>Meditation</h2><div class="spinner">Loading…</div>`;
  const list = md.practices.filter((p) => f === "all" || p.category === f);
  const shown = list.slice(0, state.medShown);
  return `<h2>Meditation</h2>
    <div class="card">
      <h3>A session written for you</h3>
      <p class="sub">Claude writes a calm script (slow breathing, long exhales, no straining) and your phone reads it aloud.</p>
      ${voicePicker()}
      <div class="two-col">
        <select id="med-minutes" aria-label="Length">${[3, 5, 10].map((m) => `<option value="${m}"${m === state.medMinutes ? " selected" : ""}>${m} minutes</option>`).join("")}</select>
        <input class="code-input" id="med-focus" placeholder="Focus (optional)" value="${esc(state.medFocus)}" aria-label="Focus">
      </div>
      <div class="row-actions">
        <button type="button" class="btn small" data-act="med-script" ${state.medBusy ? "disabled" : ""}>${state.medBusy ? "Writing…" : "Write my session"}</button>
        ${state.medScript && state.audio?.status === "error" ? `<button type="button" class="btn small" data-act="med-read">${I.play}Read with phone voice</button>
          <button type="button" class="btn small" data-act="med-stop">■ Stop</button>` : ""}
      </div>
      ${audioBlock()}
      ${state.medError ? `<div class="warning" style="margin-top:8px">${esc(state.medError)}</div>` : ""}
      ${state.medScript ? `<pre class="notes">${esc(state.medScript)}</pre>` : ""}
    </div>
    ${md.error ? `<div class="card warning">${esc(md.error)}</div>` : `
    <div class="chips" style="margin:8px 0">${[{ id: "all", label: "All" }, ...md.categories].map((c) =>
      `<button type="button" class="chip${f === c.id ? " on" : ""}" data-act="med-filter" data-v="${esc(c.id)}">${esc(c.label)}</button>`).join("")}</div>
    ${shown.map((p) => `<div class="card">
      <h3>${esc(p.title)}</h3>
      <div class="stats"><span class="badge">${esc(p.label)}</span>${p.minutes ? `<span class="badge">~${p.minutes} min</span>` : ""}</div>
      <p class="sub">${esc(p.excerpt || "")}</p>
      <audio controls preload="none" src="${esc(p.audio_url)}" style="width:100%"></audio>
    </div>`).join("")}
    ${list.length > shown.length ? `<button type="button" class="btn small" data-act="med-more">Show more</button>` : ""}
    <p class="small muted">${esc(md.credit)}</p>`}`;
}

async function renderMindBody() {
  if (!state.mind) state.mind = await api("api/mindbody");
  if (!state.voices) {
    api("api/voices").then((v) => { state.voices = v; state.voice = v.selected; if (state.tab === "mind") render(); }).catch(() => {});
  }
  if (!state.med) {
    api("api/meditation").then((r) => { if (!r.error) state.med = r; else state.med = { ...r, practices: [] }; if (state.tab === "mind") render(); })
      .catch(() => { state.med = { practices: [], categories: [], error: "Couldn't reach the meditation library." }; if (state.tab === "mind") render(); });
  }
  const m = state.mind;
  const f = state.mindFilter;
  const yoga = m.yoga.filter((e) => (f === "all" || (f === "cooldown" && e.cooldown) || (f === "pictures" && e.images.length))
    && (!state.mindQ || e.name.toLowerCase().includes(state.mindQ)));
  $view.innerHTML = `
    ${meditationSection()}
    <h2>Qigong</h2>
    <div class="card">
      <h3>Guided Baduanjin session</h3>
      <p class="sub">All eight moves in their kidney-safe form, read by your chosen voice with time to do each one, and the picture follows along. About 8 to 14 minutes depending on the pace you pick.</p>
      <div class="chips wrap">${[[30, "30 s per move"], [45, "45 s per move"], [60, "60 s per move"]].map(([s, l]) =>
        `<button type="button" class="chip" data-act="qigong-start" data-v="${s}">${I.play}${l}</button>`).join("")}</div>
    </div>
    <p class="small muted" style="margin-top:0">Baduanjin (eight pieces of brocade), adjusted for your kidney: head-only turns, hips square, folds only as far as is comfortable.</p>
    ${m.qigong.map(mindCard).join("")}
    <h2>Yoga</h2>
    <div class="filters">
      <input type="search" id="mind-q" placeholder="Search poses…" value="${esc(state.mindQ)}" aria-label="Search yoga poses">
      <div class="chips">${[["all", "All"], ["cooldown", "Cool-down"], ["pictures", "With pictures"]].map(([v, l]) =>
        `<button type="button" class="chip${f === v ? " on" : ""}" data-act="mind-filter" data-v="${v}">${l}</button>`).join("")}</div>
    </div>
    ${yoga.length ? yoga.map(mindCard).join("") : `<div class="empty">No poses match.</div>`}
    ${m.media_base ? "" : `<p class="small muted">Pictures are off: set the media address in Settings.</p>`}
    <footer class="credits">Yoga pictures: Yoga Posture Dataset on Kaggle (CC0). ${esc(m.qigong_credit || "")} General wellness guidance, not medical advice.</footer>`;
}

// --- Library ----------------------------------------------------------------------------------

const FOCUS = [["", "All"], ["legs", "Legs"], ["upper back", "Upper back"], ["core", "Core"], ["mobility", "Mobility"], ["balance", "Balance"]];

async function searchLibrary(append = false) {
  const L = state.lib;
  L.offset = append ? L.offset + 25 : 0;
  const params = new URLSearchParams({
    q: L.q, focus: L.focus, muscle: L.muscle, equipment: L.equipment,
    pictures: L.pictures, filtered: L.filtered, offset: L.offset, limit: 25,
  });
  const data = await api(`api/library?${params}`);
  L.data = data;
  L.results = append ? L.results.concat(data.results) : data.results;
  if (state.tab === "library") renderLibraryResults();
}

function libraryCard(e, i) {
  const key = `l:${e.name}`;
  const open = state.open.has(key);
  return `<div class="card">
    <button type="button" class="result" data-act="toggle" data-key="${esc(key)}" data-lib="${i}" aria-expanded="${open}">
      <h3>${esc(e.name)}</h3>
      <div class="stats">
        <span class="badge">${esc(e.equipment)}</span>
        ${e.level ? `<span class="badge">${esc(e.level)}</span>` : ""}
        ${e.safe ? "" : `<span class="badge bad">filtered out</span>`}
      </div>
    </button>
    ${open ? howTo(e) : ""}
  </div>`;
}

function renderLibraryResults() {
  const L = state.lib;
  const box = document.getElementById("lib-results");
  if (!box || !L.data) return;
  const d = L.data;
  for (const [id, options, value] of [["lib-muscle", d.muscles, L.muscle], ["lib-equipment", d.equipment, L.equipment]]) {
    const sel = document.getElementById(id);
    if (sel && sel.options.length <= 1) {
      sel.insertAdjacentHTML("beforeend", options.map((o) => `<option${o === value ? " selected" : ""}>${esc(o)}</option>`).join(""));
    }
  }
  const ninjas = state.status?.ninjas;
  document.getElementById("lib-counts").innerHTML =
    `${d.all.toLocaleString()} exercises · ${d.safe.toLocaleString()} safe for you · ${(d.all - d.safe).toLocaleString()} filtered out for your kidney, pelvic floor or core`
    + (ninjas ? `<br>API Ninjas: ${ninjas.exercises.toLocaleString()} collected so far (${ninjas.complete ? "all collected" : "still collecting in the background"})` : "");
  box.innerHTML = `<p><strong>${d.total.toLocaleString()} matches</strong></p>`
    + L.results.map(libraryCard).join("")
    + (L.results.length < d.total ? `<button type="button" class="btn small" data-act="more">Show more</button>` : "");
}

function renderLibrary() {
  const L = state.lib;
  $view.innerHTML = `
    <div class="filters">
      <input type="search" id="lib-q" placeholder="Search, e.g. glute bridge" value="${esc(L.q)}" aria-label="Search exercises">
      <div class="chips">${FOCUS.map(([v, label]) => `<button type="button" class="chip${L.focus === v ? " on" : ""}" data-act="focus" data-v="${esc(v)}">${label}</button>`).join("")}</div>
      <div class="two-col">
        <select id="lib-muscle" aria-label="Muscle"><option value="">Any muscle</option></select>
        <select id="lib-equipment" aria-label="Equipment"><option value="">Any equipment</option></select>
      </div>
      <div class="two-col">
        <label class="toggle"><input type="checkbox" id="lib-pictures" ${L.pictures ? "checked" : ""}> With pictures</label>
        <label class="toggle"><input type="checkbox" id="lib-filtered" ${L.filtered ? "checked" : ""}> Show filtered-out</label>
      </div>
      <div id="lib-counts" class="small muted"></div>
    </div>
    <div id="lib-results"><div class="spinner">Loading…</div></div>
    <footer class="credits">${esc(state.status?.credits || "")}</footer>`;
  if (L.data) renderLibraryResults();
  else searchLibrary().catch(() => toast("Couldn't load the library"));
}

// --- Events -----------------------------------------------------------------------------------

const actions = {
  toggle(el) {
    const key = el.dataset.key;
    state.open.has(key) ? state.open.delete(key) : state.open.add(key);
    if (key.startsWith("p:")) {      // an exercise's progress, inside its card on Today
      const name = key.slice(2);
      if (state.open.has(key) && !state.prog[name]) loadProgress(name).catch(() => toast("Couldn't load its progress"));
      rerenderCard(`s:${name}`);
    } else if (key.startsWith("w:") || key.startsWith("s:")) rerenderCard(key);
    else if (key.startsWith("m:")) {   // redraw just this card so a playing meditation isn't interrupted
      const card = $view.querySelector(`[data-card="${CSS.escape(key)}"]`);
      const e = findMind(key.slice(2));
      if (card && e) card.outerHTML = mindCard(e); else render();
    } else render();
  },
  check(el) {
    const name = el.dataset.name;
    state.checks[name] = !state.checks[name];
    rerenderCard(`w:${name}`);
    scheduleSave();
  },
  "warmup-timer"(el) {
    const name = el.dataset.name;
    const ex = state.plan.warmup.find((e) => e.name === name);
    if (!ex) return;
    startTimer({
      kind: "hold", label: name, secs: Number(ex.hold_secs) || 60,
      onDone() {
        state.checks[name] = true;
        rerenderCard(`w:${name}`);
        scheduleSave();
      },
    });
  },
  done(el) {
    const name = el.dataset.name;
    const i = Number(el.dataset.i);
    const s = state.sets[name][i];
    const ex = exerciseFor(name);
    if (!s.done && ex.hold) {
      // a hold: run its countdown; it ticks itself off when time is up
      const secs = Number(ex.hold_secs) || 30;
      const finish = (held) => {
        s.done = true;
        s.reps = held;
        rerenderCard(`s:${name}`);
        scheduleSave();
        if (state.sets[name].some((x) => !x.done)) startTimer({ kind: "rest", label: "Rest", secs: Number(ex.rest_secs) || 45 });
      };
      if (ex.each_side) {
        // one side at a time: left, a few seconds to switch, then right
        startTimer({
          kind: "hold", label: `${name}: hold ${i + 1}, LEFT side`, secs,
          onDone(left) {
            startTimer({
              kind: "rest", label: "Switch to your right side", secs: 5,
              onDone() {
                startTimer({ kind: "hold", label: `${name}: hold ${i + 1}, RIGHT side`, secs, onDone: (right) => finish(Math.min(left, right)) });
              },
            });
          },
        });
      } else {
        startTimer({ kind: "hold", label: `${name}: hold ${i + 1}`, secs, onDone: finish });
      }
      return;
    }
    s.done = !s.done;
    rerenderCard(`s:${name}`);
    scheduleSave();
    if (s.done) startTimer({ kind: "rest", label: "Rest", secs: Number(ex.rest_secs) || 60 });
  },
  "same-last"(el) {
    // fill the sets you haven't ticked with exactly what you did last time
    const name = el.dataset.name;
    const last = exerciseFor(name).progress?.sets || [];
    if (!last.length) return;
    state.sets[name].forEach((s, i) => {
      if (s.done) return;
      const l = last[Math.min(i, last.length - 1)];
      s.weight = l.weight ?? "";
      s.reps = l.reps ?? "";
    });
    rerenderCard(`s:${name}`);
    scheduleSave();
  },
  "bio-go"() {
    state.bioForm = { date: state.plan?.date || "", values: {}, notes: "" };
    state.bio = null;
    history.replaceState(null, "", "#history");
    showTab("history");
    setTimeout(() => document.getElementById("bio-form")?.scrollIntoView({ block: "start" }), 600);
  },
  async "pt-add-go"() {
    // straight to the "add a PT exercise" form in Settings, set up as a daily tick-box every day
    state.ptForm = { i: -1, name: "", dose: "", cues: "", section: "warmup", days: [], sets: 3 };
    history.replaceState(null, "", "#settings");
    showTab("settings");
    setTimeout(() => { document.getElementById("pt-name")?.scrollIntoView({ block: "center" }); document.getElementById("pt-name")?.focus(); }, 700);
  },
  async "ptv-find"(el) {
    const d = state.ptv;
    if ((d.address || "").trim().length < 5) { toast("Type the full address"); return; }
    el.disabled = true; el.textContent = "Finding…";
    try {
      const r = await api("api/ha/ptvisit/find", { method: "POST", body: JSON.stringify({ address: d.address }) });
      d.matches = r.matches;
      d.msg = r.error || "";
      if (r.matches.length === 1) Object.assign(d, { lat: r.matches[0].lat, lon: r.matches[0].lon, label: r.matches[0].label, matches: null });
    } catch { d.msg = "Couldn't look it up."; }
    renderSettings();
  },
  "ptv-pick"(el) {
    const d = state.ptv, m = d.matches[Number(el.dataset.i)];
    Object.assign(d, { lat: m.lat, lon: m.lon, label: m.label, matches: null, msg: "" });
    renderSettings();
  },
  async "ptv-here"() {
    const d = state.ptv;
    if (!d.person) { toast("Pick whose phone first"); return; }
    try {
      const r = await api("api/ha/ptvisit/here", { method: "POST", body: JSON.stringify({ person: d.person }) });
      Object.assign(d, { lat: r.lat, lon: r.lon, label: `Where you are now (±${Math.round(r.accuracy)} m)`, matches: null, msg: "" });
    } catch { d.msg = "Home Assistant doesn't have a location for that phone. Check the app's location permission."; }
    renderSettings();
  },
  "ptv-radius"(el) { state.ptv.radius = Number(el.dataset.v); renderSettings(); },
  async "ptv-save"() {
    const d = state.ptv;
    try {
      state.ha = await api("api/ha/ptvisit", { method: "POST", body: JSON.stringify({
        enabled: Boolean(d.enabled), address: d.address, label: d.label, lat: d.lat, lon: d.lon, radius: d.radius,
        person: d.person, service: d.service }) });
      state.ptv = null;
      toast("Saved");
      renderSettings();
    } catch (err) {
      state.ptv.msg = err.status === 400 ? (JSON.parse(err.message || "{}").detail || "Check the address and phone") : "Couldn't save";
      renderSettings();
    }
  },
  async "ptv-test"() {
    try {
      const r = await api("api/ha/ptvisit/test", { method: "POST" });
      toast(r.ok ? "Test sent. Check your phone." : `Couldn't send: ${r.error}`);
    } catch { toast("Pick your phone and save first"); }
  },
  async water(el) {
    el.disabled = true;
    try {
      const w = await api("api/water", { method: "POST", body: JSON.stringify({ oz: Number(el.dataset.v) }) });
      state.plan.water = { goal: w.goal, total: w.total, pct: w.pct };
      state.waterHist = null;
      const card = $view.querySelector('[data-card="water"]');
      if (card) card.outerHTML = waterCard(state.plan); else render();
      if (w.total >= w.goal && w.total - Number(el.dataset.v) < w.goal) toast("Water goal reached");
    } catch { toast("Couldn't add it"); el.disabled = false; }
  },
  async "water-undo"() {
    try {
      const w = await api("api/water/undo", { method: "POST" });
      state.plan.water = { goal: w.goal, total: w.total, pct: w.pct };
      const card = $view.querySelector('[data-card="water"]');
      if (card) card.outerHTML = waterCard(state.plan);
    } catch { toast("Couldn't undo"); }
  },
  async "water-save"() {
    try {
      state.settings = await api("api/settings", { method: "PUT", body: JSON.stringify({ water: {
        goal: Number(document.getElementById("water-goal").value) || 80, nudge: document.getElementById("water-nudge").checked,
        time: document.getElementById("water-time").value || "14:00" } }) });
      refreshPlan().catch(() => {});
      toast("Saved");
    } catch { toast("Couldn't save"); }
  },
  breathe(el) {
    const name = state.plan?.warmup.find((e) => /leaky can/i.test(e.name))?.name;
    startGuided("api/breathing/session", 0, "Core canister breathing", {
      mode: "breath", body: { pace: el.dataset.v },
      onEnd() {
        if (name && state.plan) { state.checks[name] = true; if (state.tab === "today") rerenderCard(`w:${name}`); scheduleSave(); }
        toast("40 breaths done, ticked off");
      },
    });
  },
  async "q-add"() {
    const box = document.getElementById("q-new");
    const text = box?.value.trim();
    if (!text) return;
    try { state.questions = await api("api/questions", { method: "POST", body: JSON.stringify({ text }) }); render(); refreshPlan().catch(() => {}); }
    catch { toast("Couldn't add it"); }
  },
  async "q-add-ai"(el) {
    const s = state.qSuggest;
    const [text] = s.items.splice(Number(el.dataset.i), 1);
    try { state.questions = await api("api/questions", { method: "POST", body: JSON.stringify({ text, source: "ai" }) }); }
    catch { toast("Couldn't add it"); }
    render();
    refreshPlan().catch(() => {});
  },
  async "q-suggest"() {
    state.qSuggest = { busy: true };
    render();
    try {
      const r = await api("api/questions/suggest", { method: "POST" });
      state.qSuggest = { items: r.suggestions || [], error: r.error };
    } catch { state.qSuggest = { error: "Couldn't reach the coach." }; }
    if (state.tab === "report") render();
  },
  async "q-asked"(el) {
    const answer = prompt("Marked as asked. What did your PT say? (optional)") ;
    if (answer === null) return;   // cancelled
    try {
      state.questions = await api(`api/questions/${el.dataset.v}/asked`, { method: "POST", body: JSON.stringify({ answer }) });
      if (state.plan) state.plan.questions = state.questions.open;
      render();
    } catch { toast("Couldn't update it"); }
  },
  async "q-undo"(el) {
    try { state.questions = await api(`api/questions/${el.dataset.v}/asked`, { method: "POST", body: JSON.stringify({ undo: true }) }); render(); refreshPlan().catch(() => {}); }
    catch { toast("Couldn't update it"); }
  },
  async "q-del"(el) {
    try { state.questions = await api(`api/questions/${el.dataset.v}`, { method: "DELETE" }); render(); refreshPlan().catch(() => {}); }
    catch { toast("Couldn't remove it"); }
  },
  "body-form"(el) { state.bodyForm = state.bodyForm === el.dataset.v ? null : el.dataset.v; render();
    setTimeout(() => document.getElementById(el.dataset.v === "weight" ? "body-weight" : "bp-sys")?.focus(), 50); },
  async "body-save"(el) {
    const v = (id) => num(document.getElementById(id)?.value);
    const body = el.dataset.v === "weight" ? { kind: "weight", weight: v("body-weight") }
      : { kind: "bp", systolic: v("bp-sys"), diastolic: v("bp-dia"), pulse: v("bp-pulse") };
    try {
      state.body = await api("api/body", { method: "POST", body: JSON.stringify(body) });
      state.bodyForm = null;
      render();
      toast("Saved");
    } catch { toast(el.dataset.v === "weight" ? "Enter your weight in pounds" : "Enter both numbers, like 122 and 78"); }
  },
  async "body-del"(el) {
    if (!confirm("Delete this reading?")) return;
    try { state.body = await api(`api/body/${el.dataset.v}`, { method: "DELETE" }); render(); } catch { toast("Couldn't delete it"); }
  },
  async "sensors-save"(el) {
    el.disabled = true; el.textContent = "Copying readings…";
    try {
      const r = await api("api/body/sensors", { method: "POST", body: JSON.stringify({
        weight_entity: document.getElementById("bs-weight")?.value || "", sys_entity: document.getElementById("bs-sys")?.value || "",
        dia_entity: document.getElementById("bs-dia")?.value || "", pulse_entity: document.getElementById("bs-pulse")?.value || "" }) });
      state.bodySensors = r;
      state.bodyMsg = r.message;
      state.body = null;
    } catch { state.bodyMsg = "Couldn't save."; }
    renderSettings();
  },
  "bio-new"() { state.bioForm = { date: state.plan?.date || "", values: {}, notes: "" }; render(); },
  "bio-cancel"() { state.bioForm = null; render(); },
  "bio-edit"(el) {
    const r = state.bio.results.find((x) => x.date === el.dataset.v);
    if (!r) return;
    state.bioForm = { date: r.date, values: { ...r.values }, notes: r.notes, editing: r.date };
    render();
    setTimeout(() => document.getElementById("bio-form")?.scrollIntoView({ block: "start" }), 100);
  },
  async "bio-save"(el) {
    const f = state.bioForm;
    const values = {};
    for (const [k, v] of Object.entries(f.values)) if (num(v) != null) values[k] = num(v);
    el.disabled = true;
    try {
      if (f.editing && f.editing !== f.date) await api(`api/biofeedback/${encodeURIComponent(f.editing)}`, { method: "DELETE" });
      state.bio = await api("api/biofeedback", { method: "POST", body: JSON.stringify({ date: f.date, values, notes: f.notes }) });
      state.bioForm = null;
      state.report = null;
      refreshPlan().catch(() => {});
      render();
      toast("Biofeedback session saved");
    } catch (err) {
      toast(err.status === 400 ? "Enter at least one reading (and a date that isn't in the future)" : "Couldn't save the session");
      el.disabled = false;
    }
  },
  async "bio-delete"(el) {
    if (!confirm(`Delete the session on ${formatDate(el.dataset.v)}?`)) return;
    try {
      state.bio = await api(`api/biofeedback/${encodeURIComponent(el.dataset.v)}`, { method: "DELETE" });
      refreshPlan().catch(() => {});
      render();
    } catch { toast("Couldn't delete it"); }
  },
  async "bio-snooze"() {
    try {
      await api("api/biofeedback/snooze", { method: "POST", body: JSON.stringify({ days: 3 }) });
      await refreshPlan();
      toast("I'll remind you in 3 days");
    } catch { toast("Couldn't snooze it"); }
  },
  async "bio-setting"(el) {
    const v = el.dataset.k === "every_days" ? Number(el.dataset.v) : el.dataset.v;
    await saveBioSettings({ [el.dataset.k]: v });
  },
  "ski-go"() { state.skiOpen = true; history.replaceState(null, "", "#week"); showTab("week"); },
  "ski-toggle"() { state.skiOpen = !state.skiOpen; render(); },
  "ski-timer"(el) {
    const t = state.ski?.tests.find((x) => x.id === el.dataset.v);
    if (!t) return;
    startTimer({
      kind: "hold", secs: t.timer, up: !t.count,
      label:t.count ? `${t.name}: count your landings` : `${t.name}: tap Done now when your form breaks`,
      onDone(held) {
        if (t.count) { toast("Time! Type how many landings you counted."); document.getElementById(`ski-${t.id}`)?.focus(); return; }
        state.skiVals[t.id] = held;
        const box = document.getElementById(`ski-${t.id}`);
        if (box) box.value = held;
      },
    });
  },
  async "ski-save"(el) {
    const values = {};
    for (const t of state.ski.tests) {
      const v = num(document.getElementById(`ski-${t.id}`)?.value);
      if (v != null) values[t.id] = v;
    }
    if (!Object.keys(values).length) { toast("Enter at least one result"); return; }
    el.disabled = true;
    try {
      state.ski = await api("api/skitests", { method: "POST", body: JSON.stringify({ values }) });
      state.skiOpen = false;
      state.skiVals = {};
      refreshPlan().catch(() => {});
      render();
      toast("Ski readiness saved");
    } catch { toast("Couldn't save the results"); el.disabled = false; }
  },
  "trend-days"(el) { state.trendDays = Number(el.dataset.v); render(); },
  "report-days"(el) { state.reportDays = Number(el.dataset.v); render(); },
  print() { window.print(); },
  copy(el) {
    const v = el.dataset.v;
    (navigator.clipboard?.writeText(v) || Promise.reject()).then(() => toast("Copied"), () => prompt("Copy this address:", v));
  },
  "pt-edit"(el) {
    const i = Number(el.dataset.i);
    const p = (state.settings.pt_exercises || [])[i] || { name: "", dose: "", cues: [], section: "warmup", days: [], sets: 3 };
    state.ptForm = { i, name: p.name, dose: p.dose, cues: (p.cues || []).join("\n"), section: p.section, days: [...(p.days || [])], sets: p.sets || 3 };
    renderSettings();
  },
  "pt-cancel"() { state.ptForm = null; renderSettings(); },
  "pt-section"(el) { state.ptForm.section = el.dataset.v; renderSettings(); },
  "pt-day"(el) {
    const f = state.ptForm;
    if (el.dataset.v === "all") f.days = [];
    else {
      const d = Number(el.dataset.v);
      f.days = f.days.includes(d) ? f.days.filter((x) => x !== d) : [...f.days, d].sort();
      if (f.days.length === 7) f.days = [];
    }
    renderSettings();
  },
  async "pt-save"() {
    const f = state.ptForm;
    if (!f.name.trim()) { toast("Give it a name"); return; }
    const item = { name: f.name.trim(), dose: f.dose.trim(), cues: f.cues.split("\n").map((c) => c.trim()).filter(Boolean),
      section: f.section, days: f.days, sets: Number(f.sets) || 3 };
    const list = [...(state.settings.pt_exercises || [])];
    if (f.i >= 0) list[f.i] = item; else list.push(item);
    await savePt(list, f.i >= 0 ? "Saved" : `Added: it's on Today ${ptDays(item.days) === "every day" ? "every day" : `on ${ptDays(item.days)}`}`);
  },
  async "pt-remove"(el) {
    const list = [...(state.settings.pt_exercises || [])];
    const [gone] = list.splice(Number(el.dataset.i), 1);
    if (!gone || !confirm(`Remove "${gone.name}"?`)) return;
    await savePt(list, "Removed");
  },
  "add-set"(el) {
    const sets = state.sets[el.dataset.name];
    const last = sets[sets.length - 1] || { weight: "", reps: "" };
    sets.push({ weight: last.weight, reps: last.reps, done: false });
    rerenderCard(`s:${el.dataset.name}`);
    scheduleSave();
  },
  "remove-set"(el) {
    state.sets[el.dataset.name].splice(Number(el.dataset.i), 1);
    rerenderCard(`s:${el.dataset.name}`);
    scheduleSave();
  },
  "add-exercise"() {
    const name = (prompt("Exercise name") || "").trim();
    if (!name) return;
    if (!state.sets[name]) {
      state.sets[name] = [{ weight: "", reps: "", done: false }];
      state.extras.push(name);
    }
    render();
    scheduleSave();
  },
  complete(el) { completeWorkout(el, Number(el.dataset.session || 1)); },
  send() { sendCoach(); },
  goto(el) { history.replaceState(null, "", `#${el.dataset.v}`); showTab(el.dataset.v); },
  // From More straight to a section of a page: open the page, then scroll to the heading once it has drawn
  "goto-sec"(el) {
    const tab = el.dataset.v, sec = el.dataset.sec.toLowerCase();
    history.replaceState(null, "", `#${tab}`);
    showTab(tab);
    let tries = 0;
    const find = () => {
      const h = [...$view.querySelectorAll("h2")].find((x) => x.textContent.trim().toLowerCase().startsWith(sec));
      if (h) h.scrollIntoView({ behavior: "smooth", block: "start" });
      else if (tries++ < 20) setTimeout(find, 150);
    };
    setTimeout(find, 150);
  },
  jump(el, e) {
    e.preventDefault();       // the address bar's #tab must stay as it is
    document.getElementById(el.dataset.v)?.scrollIntoView({ behavior: "smooth", block: "start" });
  },
  "week-nav"(el) { state.weekOffset = Number(el.dataset.v); render(); },
  "week-ask"() {
    state.coachDraft = "Look at my week and suggest any changes, thinking about my sports and how I've been feeling.";
    history.replaceState(null, "", "#coach");
    showTab("coach");
  },
  "block-ask"() {
    state.coachDraft = "Plan my next 4 weeks as a block, starting next Monday: which days are strength (and which muscle group), "
      + "cardio and rest, and the phase of each week, thinking about my sports and how I've been feeling.";
    history.replaceState(null, "", "#coach");
    showTab("coach");
  },
  async "block-clear"() {
    if (!confirm("End the 4-week plan and go back to the usual week?")) return;
    await api("api/block/clear", { method: "POST" });
    state.week = null;
    await refreshPlan();
    render();
    toast("Back to the usual week");
  },
  "week-recap"() {
    // the coach writes it from your logged workouts, symptoms, Garmin data and the plan
    state.coachDraft = "Write my weekly recap: what I did this week compared with the plan, how my kidney and pelvic floor "
      + "scores trended, any personal bests, and the one or two things to change next week. Keep it short.";
    history.replaceState(null, "", "#coach");
    showTab("coach");
    setTimeout(() => sendCoach(), 50);
  },
  async "week-reset"() {
    if (!confirm("Remove the coach's changes to this week and next?")) return;
    await api("api/week/reset", { method: "POST" });
    state.week = null;
    await refreshPlan();
    render();
    toast("Back to the usual week");
  },
  "guided-cooldown"(el) {
    startGuided("api/cooldown/guided", Number(el.dataset.v) || 45, state.plan?.cooldown?.title || "Cool-down");
  },
  "qigong-start"(el) {
    if (!state.voice && state.voices?.selected) state.voice = state.voices.selected;
    startQigong(Number(el.dataset.v));
  },
  "mind-filter"(el) { state.mindFilter = el.dataset.v; render(); },
  "med-filter"(el) { state.medFilter = el.dataset.v; state.medShown = 10; render(); },
  "med-more"() { state.medShown += 10; render(); },
  "med-read"() { speakScript(state.medScript); },
  "voice-preview"() { startAudio("", true); },
  "med-stop"() { stopSpeaking(); },
  async "med-script"() {
    state.medMinutes = Number(document.getElementById("med-minutes").value);
    state.medFocus = document.getElementById("med-focus").value;
    state.medBusy = true; state.medError = ""; render();
    try {
      const r = await api("api/meditation/script", { method: "POST", body: JSON.stringify({ minutes: state.medMinutes, focus: state.medFocus }) });
      if (r.error) state.medError = `Couldn't write the session: ${r.error}`; else state.medScript = r.script;
    } catch { state.medError = "Couldn't reach the coach."; }
    state.medBusy = false; render();
    if (state.medScript && !state.medError) startAudio(state.medScript);
  },
  "goto-settings"() { history.replaceState(null, "", "#settings"); showTab("settings"); },
  async "garmin-connect"(el) {
    const email = document.getElementById("garmin-email").value.trim();
    const password = document.getElementById("garmin-pass").value;
    if (!email || !password) { state.garminMsg = "Enter your Garmin email and password."; renderSettings(); return; }
    el.disabled = true; el.textContent = "Connecting…";
    try {
      const r = await api("api/garmin/connect", { method: "POST", body: JSON.stringify({ email, password }) });
      state.garmin = r;
      state.garminMsg = r.error || (r.needs_mfa ? "" : "Connected.");
    } catch { state.garminMsg = "Couldn't reach the add-on."; }
    renderSettings();
  },
  async "garmin-mfa"(el) {
    const code = document.getElementById("garmin-code").value.trim();
    if (!code) return;
    el.disabled = true;
    try {
      const r = await api("api/garmin/mfa", { method: "POST", body: JSON.stringify({ code }) });
      state.garmin = r;
      state.garminMsg = r.error || "Connected.";
    } catch { state.garminMsg = "Couldn't reach the add-on."; }
    renderSettings();
  },
  async "garmin-sync"(el) {
    el.disabled = true; el.textContent = "Syncing…";
    try {
      const r = await api("api/garmin/sync", { method: "POST" });
      state.garmin = r;
      state.garminMsg = r.message;
    } catch { state.garminMsg = "Couldn't reach the add-on."; }
    renderSettings();
  },
  async "garmin-disconnect"() {
    if (!confirm("Disconnect Garmin? Saved Garmin numbers stay, but nothing new will sync.")) return;
    state.garmin = await api("api/garmin/disconnect", { method: "POST" });
    state.garminMsg = "";
    renderSettings();
  },
  async "media-test"(el) {
    el.disabled = true;
    el.textContent = "Testing…";
    try {
      const r = await api("api/media/test", { method: "POST" });
      state.mediaTest = r.message;
    } catch { state.mediaTest = "Couldn't reach the add-on."; }
    el.disabled = false;
    el.textContent = "Test connection";
    const out = document.getElementById("media-test-result");
    if (out) out.textContent = state.mediaTest;
  },
  async "save-media"() {
    try {
      state.settings = await api("api/settings", { method: "PUT", body: JSON.stringify({ media_base_url: document.getElementById("media-url").value }) });
      state.mind = null;
      toast("Saved");
    } catch { toast("That address must start with https://"); }
  },
  async sport(el) {
    const s = state.settings;
    const next = new Set(s.sports);
    next.has(el.dataset.v) ? next.delete(el.dataset.v) : next.add(el.dataset.v);
    s.sports = [...next];
    el.classList.toggle("on", next.has(el.dataset.v));
    try {
      state.settings = await api("api/settings", { method: "PUT", body: JSON.stringify({ sports: s.sports }) });
      if (saveTimer) await saveDraft();
      refreshPlan().catch(() => {});
      toast("Saved");
    } catch { toast("Couldn't save"); }
    renderSettings();
  },
  async "save-season"() {
    try {
      state.settings = await api("api/settings", { method: "PUT", body: JSON.stringify({ season_start: document.getElementById("season").value }) });
      toast("Saved");
    } catch { toast("Couldn't save that date"); }
  },
  async "apply-changes"(el) {
    const m = state.coach[Number(el.dataset.i)];
    if (!m || !m.changes) return;
    el.disabled = true;
    try {
      const r = await api("api/plan/changes", { method: "POST", body: JSON.stringify({ changes: m.changes }) });
      m.applied = r.applied;
      api(`api/coach/chat/${m.id}/state`, { method: "POST", body: JSON.stringify({ applied: r.applied }) }).catch(() => {});
      state.week = null;
      if (saveTimer) await saveDraft();
      await refreshPlan();
      toast(r.applied ? "Today's plan updated" : "Nothing was changed");
    } catch { toast("Couldn't update the plan"); el.disabled = false; return; }
    renderCoach(true);
  },
  async "apply-block"(el) {
    const m = state.coach[Number(el.dataset.i)];
    if (!m || !m.block) return;
    el.disabled = true;
    try {
      const r = await api("api/plan/block", { method: "POST", body: JSON.stringify({ block: m.block }) });
      m.block_applied = !!r.ok;
      if (r.rejected?.length) m.block_notes = r.rejected;
      if (m.id) api(`api/coach/chat/${m.id}/state`, { method: "POST", body: JSON.stringify({ block_applied: !!r.ok }) }).catch(() => {});
      state.week = null;
      if (saveTimer) await saveDraft();
      await refreshPlan();
      toast(r.ok ? "Your 4-week plan is on the Week tab" : "The plan couldn't be applied");
    } catch { toast("Couldn't apply the plan"); el.disabled = false; return; }
    renderCoach(true);
  },
  "dismiss-block"(el) {
    const m = state.coach[Number(el.dataset.i)];
    if (m) {
      m.block_applied = false;
      if (m.id) api(`api/coach/chat/${m.id}/state`, { method: "POST", body: JSON.stringify({ block_applied: false }) }).catch(() => {});
    }
    renderCoach(true);
  },
  "dismiss-changes"(el) {
    const m = state.coach[Number(el.dataset.i)];
    if (m) {
      m.dismissed = true;
      if (m.id) api(`api/coach/chat/${m.id}/state`, { method: "POST", body: JSON.stringify({ dismissed: true }) }).catch(() => {});
    }
    renderCoach(true);
  },
  async "coach-clear"() {
    if (!confirm("Clear the whole chat on all your devices?")) return;
    try { await api("api/coach/chat", { method: "DELETE" }); state.coach = []; renderCoach(); } catch { toast("Couldn't clear it"); }
  },
  async "ha-save"() {
    try {
      state.ha = await api("api/ha/reminder", { method: "POST", body: JSON.stringify({
        enabled: document.getElementById("ha-on").checked, time: document.getElementById("ha-time").value || "07:30",
        service: document.getElementById("ha-service").value }) });
      toast("Saved");
      renderSettings();
    } catch { toast("Couldn't save. Use a time like 07:30."); }
  },
  async "ha-test"() {
    try {
      const r = await api("api/ha/test", { method: "POST" });
      toast(r.ok ? "Test sent. Check your phone." : `Couldn't send: ${r.error}`);
    } catch { toast("Save the reminder with your phone picked first"); }
  },
  async machine(el) {
    try {
      const st = await api("api/machines", { method: "POST", body: JSON.stringify({ machine: el.dataset.m, value: el.dataset.v }) });
      state.settings.machines = st;
      state.week = null;
      if (saveTimer) await saveDraft();
      refreshPlan().catch(() => {});
      renderSettings();
      toast("Saved");
    } catch { toast("Couldn't save"); }
  },
  async swap(el) {
    el.disabled = true;
    try {
      const r = await api("api/plan/swap", { method: "POST", body: JSON.stringify({ name: el.dataset.name }) });
      if (!r.ok) { toast(r.message); el.disabled = false; return; }
      if (saveTimer) await saveDraft();
      await refreshPlan();
      toast(`Swapped for ${r.name}`);
    } catch { toast("Couldn't swap it"); el.disabled = false; }
  },
  async bothered(el) {
    const name = el.dataset.name;
    if (!confirm(`Pause "${name}" for 2 weeks?\n\nIt comes back after that with a reminder to go lighter. You can bring it back sooner in Settings.`)) return;
    try {
      const r = await api("api/exercise/pause", { method: "POST", body: JSON.stringify({ name }) });
      if (saveTimer) await saveDraft();
      state.settings = null;
      await refreshPlan();
      toast(`Paused until ${formatDate(r.until)}`);
    } catch { toast("Couldn't pause it"); }
  },
  async unpause(el) {
    try {
      await api("api/exercise/unpause", { method: "POST", body: JSON.stringify({ name: el.dataset.name }) });
      state.settings = null;
      refreshPlan().catch(() => {});
      render();
      toast("It's back in your plans");
    } catch { toast("Couldn't bring it back"); }
  },
  "pose-photo"(el) {
    const slug = el.dataset.v;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (!file) return;
      el.disabled = true;
      toast("Saving your photo…");
      try {
        const data = await shrinkPhoto(file);
        await api("api/mindbody/photo", { method: "POST", body: JSON.stringify({ slug, data }) });
        toast("Photo saved");
        await afterPosePhoto();
      } catch (err) {
        toast(err.status === 400 ? (() => { try { return JSON.parse(err.message).detail; } catch { return "Couldn't save that photo"; } })() : "Couldn't save that photo");
        el.disabled = false;
      }
    });
    input.click();
  },
  async "pose-photo-remove"(el) {
    if (!confirm("Remove your photo of this pose?")) return;
    try {
      await api(`api/mindbody/photo/${encodeURIComponent(el.dataset.v)}`, { method: "DELETE" });
      toast("Photo removed");
      await afterPosePhoto();
    } catch { toast("Couldn't remove it"); }
  },
  "snow-toggle"() { state.snowOpen = !state.snowOpen; if (!state.snowOpen) state.snow = null; render(); },
  "garmin-snow"(el) {
    const p = state.plan, o = p.garmin_acts.snow[Number(el.dataset.i)];
    state.snow = { sport: o.kind === "skiing" ? "skiing" : "snowboarding", hours: Math.max(0.5, Math.round(o.minutes / 30) / 2), rpe: 6,
      kidney: p.checkin?.kidney ?? p.last_scores?.kidney ?? 1, pelvic_floor: p.checkin?.pelvic_floor ?? p.last_scores?.pelvic_floor ?? 1,
      notes: "", date: o.date, garmin_ids: o.ids };
    state.snowOpen = true;
    render();
  },
  async "garmin-ignore"(el) {
    try {
      await api("api/garmin/activities/ignore", { method: "POST", body: JSON.stringify({ ids: el.dataset.v.split(",") }) });
      if (saveTimer) await saveDraft();
      await refreshPlan();
    } catch { toast("Couldn't save that"); }
  },
  async "garmin-check"(el) {
    el.disabled = true;
    el.textContent = "Checking…";
    try {
      const r = await api("api/garmin/activities/check", { method: "POST" });
      toast(r.message);
      if (saveTimer) await saveDraft();
      await refreshPlan();
    } catch {
      toast("Couldn't reach Garmin. Try again in a few minutes.");
      el.disabled = false;
      el.textContent = "Check Garmin";
    }
  },
  "garmin-cardio"(el) {
    const id = el.dataset.v;
    state.cardioGarmin = state.cardioGarmin.includes(id) ? state.cardioGarmin.filter((x) => x !== id) : [...state.cardioGarmin, id];
    store.set(`garmin-cardio-${state.plan.date}`, state.cardioGarmin);
    const box = $view.querySelector(".garmin-acts");
    if (box) box.outerHTML = garminCardio(state.plan); else render();
  },
  "snow-sport"(el) { state.snow.sport = el.dataset.v; render(); },
  async "snow-save"(el) {
    const s = state.snow;
    el.disabled = true;
    try {
      await api("api/snowday", { method: "POST", body: JSON.stringify({ ...s, hours: Number(s.hours) || 3 }) });
      state.snowOpen = false;
      state.snow = null;
      state.history = null;
      state.week = null;
      if (saveTimer) await saveDraft();
      await refreshPlan();
      toast("Snow day saved to History");
    } catch (err) {
      let why = "Couldn't save the snow day";
      try { if (err.status === 400 || err.status === 409) why = JSON.parse(err.message).detail; } catch { /* keep the plain message */ }
      toast(why);
      el.disabled = false;
      if (err.status === 409) { state.snowOpen = false; state.snow = null; refreshPlan().catch(() => {}); }
    }
  },
  "checkin-edit"() { state.ckEdit = true; state.ck = null; render(); },
  "checkin-cancel"() { state.ckEdit = false; state.ck = null; render(); },
  async "checkin-save"(el) {
    el.disabled = true;
    try {
      await api("api/checkin", { method: "POST", body: JSON.stringify({ kidney: state.ck.kidney, pelvic_floor: state.ck.pelvic_floor }) });
      state.ckEdit = false;
      state.ck = null;
      if (saveTimer) await saveDraft();
      await refreshPlan();
      toast("Check-in saved. Today's plan is updated.");
    } catch { toast("Couldn't save the check-in"); el.disabled = false; }
  },
  "second-toggle"() { state.secondOpen = !state.secondOpen; render(); },
  async "second-add"(el) {
    el.disabled = true;
    try {
      const r = await api("api/plan/session2", { method: "POST", body: JSON.stringify({ kind: el.dataset.v, minutes: 20 }) });
      state.secondOpen = false;
      if (saveTimer) await saveDraft();
      await refreshPlan();
      toast(r.ok ? `Second session added (${r.added})` : (r.message || "Couldn't add a second session"));
      if (r.rejected?.length) toast(`Skipped: ${r.rejected[0]}`);
    } catch { toast("Couldn't add a second session"); el.disabled = false; }
  },
  async "reset-plan"() {
    if (!confirm("Remove all of today's coach changes?")) return;
    await api("api/plan/reset", { method: "POST" });
    await refreshPlan();
    toast("Back to the original plan");
  },
  async "save-gear"() {
    try {
      const val = (id) => document.getElementById(id).value;
      state.settings = await api("api/settings", { method: "PUT", body: JSON.stringify({
        gear_notes: val("gear-notes"),
        weights: { dumbbell: val("w-dumbbell"), kettlebell: val("w-kettlebell"), bar_step: val("w-bar"), cable_step: val("w-cable") },
      }) });
      const w = state.settings.weights || {};   // show the lists as saved (sorted, numbers only)
      document.getElementById("w-dumbbell").value = (w.dumbbell || []).join(", ");
      document.getElementById("w-kettlebell").value = (w.kettlebell || []).join(", ");
      toast("Saved");
    } catch { toast("Couldn't save"); }
  },
  async equip(el) {
    const s = state.settings;
    const v = el.dataset.v;
    const next = new Set(s.equipment);
    next.has(v) ? next.delete(v) : next.add(v);
    next.add("bodyweight");
    s.equipment = [...next];
    el.classList.toggle("on", next.has(v));
    try {
      state.settings = await api("api/settings", { method: "PUT", body: JSON.stringify({ equipment: s.equipment }) });
      if (saveTimer) await saveDraft();   // keep any sets already typed, then rebuild today's plan
      refreshPlan().catch(() => {});
      toast("Saved");
    } catch { toast("Couldn't save"); }
    renderSettings();
  },
  async "claude-login"() { state.claude = await api("api/claude/login", { method: "POST" }); render(); loadClaude(); },
  async "claude-code"() {
    const code = document.getElementById("claude-code").value.trim();
    if (!code) return;
    state.claude = await api("api/claude/code", { method: "POST", body: JSON.stringify({ code }) });
    render();
    toast(state.claude.signed_in ? "Claude connected" : "Checking the code…");
    loadClaude();
  },
  async "claude-cancel"() { state.claude = await api("api/claude/cancel", { method: "POST" }); render(); },
  async "claude-logout"() { state.claude = await api("api/claude/logout", { method: "POST" }); render(); },
  focus(el) {
    state.lib.focus = el.dataset.v;
    $view.querySelectorAll(".chip").forEach((c) => c.classList.toggle("on", c.dataset.v === state.lib.focus));
    searchLibrary();
  },
  more() { searchLibrary(true); },
  async report(el) {
    el.disabled = true;
    el.textContent = "Making the report (a few minutes)…";
    try {
      const res = await api("api/report", { method: "POST" });
      toast(res.ok ? `Report saved to ${res.path}` : `Report failed: ${res.error}`);
    } catch { toast("Couldn't make the report"); }
    el.disabled = false;
    el.textContent = "Make an HTML progress report (AI Coach)";
  },
};

async function saveBioSettings(patch) {
  try {
    state.settings = await api("api/settings", { method: "PUT", body: JSON.stringify({ biofeedback: { ...state.settings.biofeedback, ...patch } }) });
    state.bio = null;
    refreshPlan().catch(() => {});
    toast("Saved");
  } catch { toast("Couldn't save"); }
  renderSettings();
}

async function savePt(list, message) {
  try {
    state.settings = await api("api/settings", { method: "PUT", body: JSON.stringify({ pt_exercises: list }) });
    state.ptForm = null;
    if (saveTimer) await saveDraft();
    refreshPlan().catch(() => {});
    toast(message);
  } catch { toast("Couldn't save"); }
  renderSettings();
}

$view.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (el && actions[el.dataset.act]) actions[el.dataset.act](el, e);
});

// Enter sends the message to the coach; Shift+Enter makes a new line
$view.addEventListener("keydown", (e) => {
  if (e.target.id === "coach-input" && e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    sendCoach();
  }
});

let searchTimer;
$view.addEventListener("input", (e) => {
  const t = e.target;
  if (t.dataset.field) {
    const sets = state.sets[t.dataset.name], i = Number(t.dataset.i), f = t.dataset.field;
    const old = String(sets[i][f] ?? "");
    sets[i][f] = t.value;
    // the sets after this one that still matched it follow along, so a new weight is typed once
    for (let j = i + 1; j < sets.length && !sets[j].done && String(sets[j][f] ?? "") === old; j++) {
      sets[j][f] = t.value;
      const box = $view.querySelector(`input[data-field="${f}"][data-name="${CSS.escape(t.dataset.name)}"][data-i="${j}"]`);
      if (box) box.value = t.value;
    }
    scheduleSave();
  } else if (t.dataset.ptv && state.ptv) {
    state.ptv[t.dataset.ptv] = t.type === "checkbox" ? t.checked : t.value;
  } else if (t.dataset.bio && state.bioForm) {
    const k = t.dataset.bio;
    if (k === "date" || k === "notes") state.bioForm[k] = t.value;
    else state.bioForm.values[k] = t.value;
  } else if (t.dataset.pt && state.ptForm) {
    state.ptForm[t.dataset.pt] = t.value;
  } else if (t.dataset.ski) {
    state.skiVals[t.dataset.ski] = t.value;
  } else if (t.dataset.finish) {
    state.finish[t.dataset.finish] = t.value;
    const label = document.getElementById(`val-${t.dataset.finish}`);
    if (label) label.textContent = `${t.value}/10`;
    store.set(finishKey(), state.finish);
  } else if (t.dataset.snow) {
    const key = t.dataset.snow;
    state.snow[key] = key === "notes" ? t.value : Number(t.value);
    const label = document.getElementById(`snowval-${key}`);
    if (label) label.textContent = `${t.value}/10`;
  } else if (t.dataset.ck) {
    state.ck[t.dataset.ck] = Number(t.value);
    const label = document.getElementById(`ckval-${t.dataset.ck}`);
    if (label) label.textContent = `${t.value}/10`;
  } else if (t.id === "mind-q") {
    state.mindQ = t.value.trim().toLowerCase();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { render(); const q = document.getElementById("mind-q"); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }, 250);
  } else if (t.id === "prog-q") {
    state.progQ = t.value;
    const sel = document.getElementById("prog-select");
    const q = t.value.trim().toLowerCase();
    const first = (state.history?.exercises || []).find((e) => e.toLowerCase().includes(q));
    if (q && first && !state.progress.exercise.toLowerCase().includes(q)) {
      state.progress.exercise = first;
      const el = document.getElementById("chart");
      if (state.prog[first] && el) el.innerHTML = progressBody(state.prog[first]);
      else loadProgress(first).catch(() => {});
    }
    if (sel) sel.innerHTML = progOptions(state.history?.exercises || []);
  } else if (t.id === "lib-q") {
    state.lib.q = t.value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => searchLibrary(), 300);
  }
});

$view.addEventListener("change", (e) => {
  const t = e.target;
  if (t.dataset.actChange === "progress") {
    state.progress.exercise = t.value;
    const el = document.getElementById("chart");
    if (state.prog[t.value] && el) el.innerHTML = progressBody(state.prog[t.value]);
    else { if (el) el.innerHTML = `<div class="spinner">Loading…</div>`; loadProgress(t.value).catch(() => toast("Couldn't load that exercise")); }
  }
  else if (t.dataset.actChange === "garmin-adjust") {
    api("api/settings", { method: "PUT", body: JSON.stringify({ garmin_adjust: t.checked }) })
      .then(async (s) => {
        state.settings = s;
        if (saveTimer) await saveDraft();
        refreshPlan().catch(() => {});
        toast(t.checked ? "On: Garmin can make days lighter" : "Off");
      })
      .catch(() => toast("Couldn't save"));
  }
  else if (t.dataset.actChange === "bio-enabled") saveBioSettings({ enabled: t.checked });
  else if (t.dataset.actChange === "voice") {
    state.voice = t.value;
    state.audio = null;
    api("api/settings", { method: "PUT", body: JSON.stringify({ voice: t.value }) }).catch(() => toast("Couldn't save the voice"));
    render();
  }
  else if (t.id === "lib-muscle") { state.lib.muscle = t.value; searchLibrary(); }
  else if (t.id === "lib-equipment") { state.lib.equipment = t.value; searchLibrary(); }
  else if (t.id === "lib-pictures") { state.lib.pictures = t.checked; searchLibrary(); }
  else if (t.id === "lib-filtered") { state.lib.filtered = t.checked; searchLibrary(); }
});

window.addEventListener("online", () => {
  sendOutbox();
  if (saveTimer || (state.plan && store.get(unsentKey(state.plan.date), null))) saveDraft();
});
window.addEventListener("offline", () => setSaveState("No connection: changes stay on this phone"));

// Save right away when the phone locks or the app goes to the background
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden" && saveTimer) saveDraft();
  if (document.visibilityState === "visible" && state.tab === "coach" && state.coachLoaded && !state.coachBusy) {
    loadCoach().then((changed) => { if (changed && state.tab === "coach") renderCoach(true); });
    pollCoach();
  }
  if (document.visibilityState === "visible") sendOutbox();
  if (document.visibilityState === "visible" && state.plan) {
    api("api/plan").then((p) => { if (p.date !== state.plan.date) { loadPlan(p); render(); } }).catch(() => {});
  }
});

// --- Tabs -------------------------------------------------------------------------------------

function render() {
  const views = { more: renderMore, today: renderToday, week: renderWeek, history: renderHistory, report: renderReport, coach: renderCoach, library: renderLibrary, mind: renderMindBody, settings: renderSettings };
  letterhead();
  Promise.resolve(views[state.tab]()).then(addContents).catch(() => {
    $view.innerHTML = `<div class="empty">Couldn't load this page. Pull down to refresh or try again.</div>`;
  });
}

// Swipe order. The bottom bar shows five; History, Library and Settings live under Records.
const TAB_ORDER = ["today", "week", "coach", "mind", "history", "report", "library", "settings"];
const MORE_TABS = ["history", "report", "library", "settings"];
const VALID_TABS = [...TAB_ORDER, "more"];

function renderMore() {
  // Each page and the sections on it (as their headings read), so a section is one tap from here
  const items = [
    ["history", I.history, "History", "Past workouts and how your numbers have moved.",
      ["How you've felt", "Weight and blood pressure", "Progress", "Completed workouts"]],
    ["report", I.report, "PT report", "One printable page to take to your PT.",
      ["Questions for my PT", "Symptoms", "Daily routine", "Strength and holds"]],
    ["library", I.library, "Library", "Every exercise, with pictures and how-to.", []],
    ["settings", I.settings, "Settings", "Set the app up the way you train.",
      ["From your PT", "Equipment", "Water", "Scale and blood pressure", "Sports", "Paused exercises", "Home Assistant", "Garmin", "AI Coach", "Install as an app"]],
  ];
  $view.innerHTML = `<div class="more-list">${items.map(([tab, icon, name, sub, secs]) => `<div class="more-item">
      <span class="more-icon" aria-hidden="true">${icon}</span>
      <span><button type="button" class="btn link more-name" style="padding:0;min-height:0" data-act="goto" data-v="${tab}">${name}</button>
        <span class="sub" style="display:block">${sub}</span>
        ${secs.length ? `<span class="chips wrap" style="margin-top:8px">${secs.map((s) => `<button type="button" class="chip" data-act="goto-sec" data-v="${tab}" data-sec="${esc(s)}">${esc(s)}</button>`).join("")}</span>` : ""}</span>
    </div>`).join("")}</div>`;
}

// Long pages (Settings, History, PT report) get a row of links to their sections at the top
function addContents() {
  if (!["settings", "history", "report"].includes(state.tab) || $view.querySelector(".contents")) return;
  const heads = [...$view.querySelectorAll("h2")];
  if (heads.length < 4) return;
  heads.forEach((h, i) => { h.id ||= `sec-${i}`; });
  const nav = document.createElement("nav");
  nav.className = "contents noprint";
  nav.setAttribute("aria-label", "On this page");
  nav.innerHTML = heads.map((h) => `<a href="#${h.id}" data-act="jump" data-v="${h.id}">${esc(h.textContent.trim())}</a>`).join("");
  $view.prepend(nav);
}

// Swipe left/right anywhere on the page to move between tabs (ignored on sliders, text boxes, audio and sideways-scrolling strips)
let swipe = null;
document.addEventListener("touchstart", (e) => {
  const t = e.target;
  const blocked = e.touches.length !== 1 || t.closest("input, textarea, select, audio, .chips, .gallery, pre, [data-noswipe]");
  swipe = blocked ? null : { x: e.touches[0].clientX, y: e.touches[0].clientY, t: Date.now() };
}, { passive: true });
document.addEventListener("touchend", (e) => {
  if (!swipe) return;
  const t = e.changedTouches[0];
  const dx = t.clientX - swipe.x, dy = t.clientY - swipe.y, quick = Date.now() - swipe.t < 700;
  swipe = null;
  if (!quick || Math.abs(dx) < 70 || Math.abs(dx) < Math.abs(dy) * 1.8) return;
  const here = TAB_ORDER.indexOf(state.tab);
  const i = here + (dx < 0 ? 1 : -1);
  if (here < 0 || i < 0 || i >= TAB_ORDER.length) return;
  history.replaceState(null, "", `#${TAB_ORDER[i]}`);
  showTab(TAB_ORDER[i]);
}, { passive: true });

function showTab(tab) {
  if (!VALID_TABS.includes(tab)) tab = "today";
  state.tab = tab;
  const highlight = MORE_TABS.includes(tab) ? "more" : tab;
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === highlight));
  if (tab === "history") { state.history = null; state.trends = null; state.bio = null; state.body = null; state.waterHist = null; }   // always fresh
  if (tab === "report") { state.report = null; state.questions = null; }
  if (tab === "settings") { state.bodySensors = null; state.bodyMsg = ""; }
  if (tab === "coach" && state.coachLoaded) {   // pick up what the other device wrote since you were last here
    loadCoach().then((changed) => { if (changed && state.tab === "coach") renderCoach(true); });
  }
  if (tab === "week") state.ski = null;
  render();
  window.scrollTo({ top: 0 });
}

document.querySelector(".tabs").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-tab]");
  if (b) history.replaceState(null, "", `#${b.dataset.tab}`), showTab(b.dataset.tab);
});

// The letterhead: back to Records from its pages, and tapping a score reopens this morning's check-in
$back.addEventListener("click", () => { history.replaceState(null, "", "#more"); showTab("more"); });
document.querySelector(".top").addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (!el || el === $back || !actions[el.dataset.act]) return;
  actions[el.dataset.act](el, e);
  window.scrollTo({ top: 0, behavior: "smooth" });
});

// Installed on the home screen (opened at the add-on's own address, not inside Home Assistant): register the service
// worker that makes it installable and shows a friendly page when Home Assistant can't be reached
if ("serviceWorker" in navigator && window.top === window && !location.pathname.includes("ingress")) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}

api("api/status").then((s) => { state.status = s; if (state.tab === "coach" || state.tab === "library") render(); }).catch(() => {});
showTab(location.hash.slice(1) || "today");
refreshPlan().then(sendOutbox).catch(() => {
  $view.innerHTML = `<div class="empty">Couldn't load today's plan. Check that the add-on is running, then reload.</div>`;
});
