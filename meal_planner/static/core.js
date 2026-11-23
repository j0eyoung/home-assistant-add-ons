"use strict";
// Shared helpers for every tab: API calls, icons, sheets, toasts with Undo, the offline queue, formatting.

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const view = $("#view");
const SLOTS = ["breakfast", "lunch", "dinner"];
const SLOT_LABEL = { breakfast: "Breakfast", lunch: "Lunch", dinner: "Dinner" };
const STORE_ORDER = ["costco", "costco_business", "king_soopers", "other"];
const STORE_LABEL = { costco: "Costco", costco_business: "Costco Business Center", king_soopers: "King Soopers", other: "Other" };
const STORE_SHORT = { costco: "Costco", costco_business: "Costco Biz", king_soopers: "King Soopers", other: "Other" };
const S = { tab: "plan", busy: false, seq: 0, pickFor: null };   // app state shared by the tabs

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// Per-phone conveniences (last tab, store, offline copy of the list). Storage can be missing: never required.
const local = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
};

// ---------------------------------------------------------------- API
// Errors from the add-on carry .status; a network failure or timeout has none (the phone is offline).
async function api(path, method = "GET", body, timeoutMs = 60000) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  let r;
  try {
    r = await fetch("api/" + path, {
      method, signal: ctl.signal, headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new Error(e.name === "AbortError" ? "That took too long. Check your connection and try again." : "Can't reach the planner. Check your connection.");
  } finally { clearTimeout(timer); }
  if (!r.ok) {
    let msg = r.statusText || "Error " + r.status;
    try {
      const d = (await r.json()).detail;
      msg = typeof d === "string" ? d : Array.isArray(d) ? d.map(x => x.msg).join("; ") : msg;
    } catch (e) {}
    const err = new Error(msg); err.status = r.status; throw err;
  }
  return r.json();
}

// ---------------------------------------------------------------- Icons (drawn, 24px grid, 1.75 stroke)
const ICONS = {
  calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  card: '<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="M3 9.5h18M7 13h10M7 16h6"/>',
  bag: '<path d="M5.5 8h13l-1 12.5h-11z"/><path d="M9 10.5V7a3 3 0 0 1 6 0v3.5"/>',
  jar: '<path d="M8 3.5h8v3H8z"/><path d="M7 6.5h10a1.5 1.5 0 0 1 1.5 1.5v11a2 2 0 0 1-2 2h-9a2 2 0 0 1-2-2V8A1.5 1.5 0 0 1 7 6.5z"/><path d="M5.5 11.5h13"/>',
  pot: '<path d="M4.5 10h15v5.5a4.5 4.5 0 0 1-4.5 4.5H9a4.5 4.5 0 0 1-4.5-4.5z"/><path d="M2.5 10h2M19.5 10h2M9.5 6.5c0-1.2 1.2-1.3 1.2-2.5M13.5 6.5c0-1.2 1.2-1.3 1.2-2.5"/>',
  swap: '<path d="M7 4 4 7l3 3M4 7h12.5M17 20l3-3-3-3M20 17H7.5"/>',
  more: '<circle cx="5.5" cy="12" r="1.3" class="f"/><circle cx="12" cy="12" r="1.3" class="f"/><circle cx="18.5" cy="12" r="1.3" class="f"/>',
  check: '<path d="M5 12.5 9.5 17 19 7.5"/>',
  x: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  "chev-left": '<path d="M14.5 5.5 8 12l6.5 6.5"/>',
  "chev-right": '<path d="M9.5 5.5 16 12l-6.5 6.5"/>',
  "chev-down": '<path d="M5.5 9.5 12 16l6.5-6.5"/>',
  user: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20.5c0-3.9 3.1-7 7-7s7 3.1 7 7"/>',
  star: '<path d="M12 3.6l2.5 5.3 5.8.7-4.3 4 1.1 5.8L12 16.6l-5.1 2.8L8 13.6l-4.3-4 5.8-.7z"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
  timer: '<circle cx="12" cy="13.5" r="7.5"/><path d="M12 13.5V9.5M9.5 2.5h5M18.5 6.5l1.5-1.5"/>',
  barcode: '<path d="M4 6v12M7 6v12M9.5 6v12M13 6v12M15.5 6v12M18 6v12M20.5 6v12"/>',
  receipt: '<path d="M6 3h12v18l-2-1.4-2 1.4-2-1.4-2 1.4-2-1.4L6 21z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
  camera: '<path d="M4 8h3l2-2.5h6L17 8h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.5"/>',
  send: '<path d="M4 12 20 4l-6 16-2.6-6.4z"/><path d="M11.4 13.6 20 4"/>',
  refresh: '<path d="M19.5 11A7.5 7.5 0 1 0 17.3 16.8"/><path d="M20 4.5v6.5h-6.5"/>',
  box: '<path d="M4.5 10h15v8a2.5 2.5 0 0 1-2.5 2.5H7A2.5 2.5 0 0 1 4.5 18z"/><path d="M3 6.5h18V10H3zM10 14h4"/>',
  move: '<path d="M4 12h14M13.5 7.5 18 12l-4.5 4.5"/>',
  trash: '<path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l1 13.5h9l1-13.5"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>',
  sparkle: '<path d="M12 3.5c.6 4.4 2.6 6.4 7 7-4.4.6-6.4 2.6-7 7-.6-4.4-2.6-6.4-7-7 4.4-.6 6.4-2.6 7-7z"/><path d="M19 3v3M17.5 4.5h3"/>',
  "cloud-off": '<path d="M3.5 3.5l17 17"/><path d="M8.2 8.2A4.5 4.5 0 0 0 6.5 17h10M11 6.1A5.5 5.5 0 0 1 17.4 10 3.5 3.5 0 0 1 20 16"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  download: '<path d="M12 4v11M7 10.5l5 5 5-5M5 20h14"/>',
  list: '<path d="M9 6.5h11M9 12h11M9 17.5h11"/><circle cx="4.5" cy="6.5" r="1.1" class="f"/><circle cx="4.5" cy="12" r="1.1" class="f"/><circle cx="4.5" cy="17.5" r="1.1" class="f"/>',
  pause: '<path d="M9 6v12M15 6v12"/>',
  play: '<path d="M8 5.5v13l10.5-6.5z"/>',
};
const icon = (name, cls = "") => `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICONS[name] || ""}</svg>`;

// ---------------------------------------------------------------- Formatting
const pad = n => String(n).padStart(2, "0");
const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const parseISO = s => new Date(s + "T12:00");
const addDays = (s, n) => { const d = parseISO(s); d.setDate(d.getDate() + n); return iso(d); };
const todayISO = () => iso(new Date());
const fmtDay = (s, o) => parseISO(s).toLocaleDateString(undefined, o);
const dayLabel = s => s === todayISO() ? "Today" : s === addDays(todayISO(), 1) ? "Tomorrow" : fmtDay(s, { weekday: "long" });
const daysLeft = s => Math.round((parseISO(s) - parseISO(todayISO())) / 864e5);
const expiryText = s => { const n = daysLeft(s); return n < -1 ? `Expired ${-n} days ago` : n === -1 ? "Expired yesterday" : n === 0 ? "Expires today" : n === 1 ? "1 day left" : n <= 30 ? `${n} days left` : "Best before " + fmtDay(s, { month: "short", day: "numeric" }); };
const num = v => Math.round(Number(v) || 0);
const money = v => v ? "$" + (+v).toFixed(2) : "";
const people = n => n === 1 ? "1 person" : `${n} people`;
// "2026-11-24|lunch" or {date, slot} -> "Tue lunch" / "today's lunch"
function whenText(k) {
  const [d, s] = typeof k === "string" ? k.split("|") : [k.date, k.slot];
  const t = todayISO();
  const dl = d === t ? "today's" : d === addDays(t, 1) ? "tomorrow's" : d === addDays(t, -1) ? "yesterday's" : fmtDay(d, { weekday: "short" });
  return `${dl} ${s}`;
}

const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

const FR = [[1 / 8, "⅛"], [1 / 4, "¼"], [1 / 3, "⅓"], [1 / 2, "½"], [2 / 3, "⅔"], [3 / 4, "¾"]];
function fmtQty(q) {
  q = +q || 0;
  if (q <= 0) return "";
  if (q >= 20) return String(Math.round(q));
  const w = Math.floor(q), f = q - w;
  if (f < 0.06) return w ? String(w) : String(+q.toFixed(2));
  if (f > 0.94) return String(w + 1);
  const hit = FR.find(([v]) => Math.abs(f - v) < 0.04);
  return hit ? (w || "") + hit[1] : String(+q.toFixed(q < 1 ? 2 : 1));
}
const PLURAL = { cup: "cups", can: "cans", jar: "jars", bag: "bags", pack: "packs", bottle: "bottles", carton: "cartons",
  head: "heads", pint: "pints", quart: "quarts", gallon: "gallons", box: "boxes", bunch: "bunches", loaf: "loaves" };
// Small amounts read better in the next unit down: 1/16 cup -> 1 tbsp, 1/3 tbsp -> 1 tsp, 0.2 lb -> 3 oz
const DOWN = { gallon: [0.25, "cup", 16], quart: [0.5, "cup", 4], pint: [0.5, "cup", 2], cup: [0.25, "tbsp", 16],
  tbsp: [1, "tsp", 3], lb: [0.25, "oz", 16], kg: [0.1, "g", 1000], l: [0.1, "ml", 1000] };
const amount = (q, u) => {
  q = +q || 0;
  for (let d = DOWN[u]; d && q > 0 && q < d[0] * 0.94; d = DOWN[u]) { q *= d[2]; u = d[1]; }   // 6% slack for rounding
  if (u === "g" || u === "ml") q = Math.round(q);
  const n = fmtQty(q); if (!n) return "";
  const unit = u === "floz" ? "fl oz" : (q > 1.04 && PLURAL[u]) || u || "";
  return unit ? `${n} ${unit}` : n;
};

// Photo or, when there is none (or it fails to load), the meal's initial on a tinted plate.
function photo(url, name, cls = "") {
  const ph = `<span class="ph ${cls}" aria-hidden="true">${esc((String(name || "?").trim()[0] || "?").toUpperCase())}</span>`;
  return url ? `<img class="${cls}" src="${esc(url)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" data-ph="${esc(ph)}" onerror="this.outerHTML=this.dataset.ph">` : ph;
}

const haptic = ms => { try { navigator.vibrate && navigator.vibrate(ms); } catch (e) {} };

// ---------------------------------------------------------------- Toast (with an optional action, e.g. Undo)
function toast(msg, o = {}) {
  const t = $("#toast");
  t.innerHTML = `<span>${esc(msg)}</span>${o.action ? `<button type="button" class="toast-act">${esc(o.action)}</button>` : ""}`;
  if (o.action) $(".toast-act", t).onclick = () => { t.classList.remove("show"); o.onAction(); };
  t.classList.add("show");
  clearTimeout(toast.t);
  const ms = o.ms ?? (o.action ? 6000 : 3500);
  if (ms) toast.t = setTimeout(() => t.classList.remove("show"), ms);
}

// Run one server action at a time. keep: on failure leave the page as it is so typed text survives.
async function act(fn, okMsg, { keep = false } = {}) {
  if (S.busy) { toast("Still working on the last thing…"); return false; }
  S.busy = true;
  document.body.classList.add("busy");
  let ok = false;
  try { await fn(); ok = true; if (okMsg) toast(okMsg); } catch (e) { toast(e.message, { ms: 6000 }); }
  S.busy = false;
  document.body.classList.remove("busy");
  if (ok || !keep) render({ keepScroll: true });
  return ok;
}

// Do it in 5 seconds unless Undo is tapped. Leaving the page does it now.
const pending = new Map();
function later(key, label, run, undo) {
  flushLater(key);
  const p = { run, timer: setTimeout(() => { pending.delete(key); run(); }, 5000) };
  pending.set(key, p);
  toast(label, { action: "Undo", ms: 4800, onAction: () => {
    if (pending.get(key) !== p) return;      // already done: too late to undo
    clearTimeout(p.timer); pending.delete(key); undo();
  } });
}
function flushLater(key) {
  for (const [k, p] of [...pending]) if (!key || k === key) { clearTimeout(p.timer); pending.delete(k); p.run(); }
}
document.addEventListener("visibilitychange", () => { if (document.hidden) flushLater(); });

// ---------------------------------------------------------------- Bottom sheets
const sheets = [];
function sheet({ title = "", body = "", foot = "", cls = "", label = "", onClose } = {}) {
  const wrap = document.createElement("div");
  wrap.className = "sheet-wrap";
  wrap.innerHTML = `<div class="scrim" data-close></div>
    <section class="sheet ${cls}" role="dialog" aria-modal="true" aria-label="${esc(label || title.replace(/<[^>]+>/g, ""))}" tabindex="-1">
      <div class="grab" aria-hidden="true"></div>
      ${title ? `<header class="sheet-head"><h2>${title}</h2><button type="button" class="icon-btn quiet" data-close aria-label="Close">${icon("x")}</button></header>` : ""}
      <div class="sheet-body">${body}</div>
      ${foot.trim() ? `<footer class="sheet-foot">${foot}</footer>` : ""}
    </section>`;
  document.body.appendChild(wrap);
  document.body.classList.add("has-sheet");
  const el = $(".sheet", wrap), back = document.activeElement;
  const h = {
    el, wrap,
    close() {
      if (!wrap.isConnected || wrap.classList.contains("out")) return;
      wrap.classList.add("out");
      sheets.splice(sheets.indexOf(h), 1);
      if (!sheets.length) document.body.classList.remove("has-sheet");
      setTimeout(() => wrap.remove(), 240);
      if (back && back.isConnected) try { back.focus({ preventScroll: true }); } catch (e) {}
      onClose && onClose();
    },
  };
  wrap.addEventListener("click", e => { if (e.target.closest("[data-close]")) h.close(); });
  sheets.push(h);
  requestAnimationFrame(() => requestAnimationFrame(() => { wrap.classList.add("in"); markScrollers(wrap); }));
  setTimeout(() => { const f = $("[autofocus]", el); (f || el).focus({ preventScroll: true }); }, 60);
  dragToClose(el, h.close);
  return h;
}
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && sheets.length) { e.preventDefault(); sheets[sheets.length - 1].close(); }
});

function dragToClose(el, close) {
  let y0 = null, dy = 0;
  const start = e => {                       // only from the grab handle or the title, so lists still scroll
    if (!e.target.closest(".grab, .sheet-head, .drag-zone") || e.target.closest("button, input, textarea, select")) return;
    y0 = e.touches[0].clientY; dy = 0; el.style.transition = "none";
  };
  el.addEventListener("touchstart", start, { passive: true });
  el.addEventListener("touchmove", e => {
    if (y0 === null) return;
    dy = Math.max(0, e.touches[0].clientY - y0);
    el.style.transform = `translateY(${dy}px)`;
  }, { passive: true });
  el.addEventListener("touchend", () => {
    if (y0 === null) return;
    y0 = null; el.style.transition = ""; el.style.transform = "";
    if (dy > 90) close();
  });
}

function confirmSheet(title, text, yes, danger = true) {
  return new Promise(resolve => {
    let answered = false;
    const h = sheet({
      title: esc(title), body: `<p class="lede">${esc(text)}</p>`, cls: "small",
      foot: `<button type="button" class="btn line" data-close>Cancel</button><button type="button" class="btn ${danger ? "danger" : "primary"}" data-yes>${esc(yes)}</button>`,
      onClose: () => !answered && resolve(false),
    });
    $("[data-yes]", h.el).onclick = () => { answered = true; h.close(); resolve(true); };
  });
}

// −  2  +  ; onChange(value) on every tap
function stepper(value, { min = 1, max = 30, label = "Amount" } = {}) {
  return `<div class="stepper" role="group" aria-label="${esc(label)}"><button type="button" data-step="-1" aria-label="Fewer">${icon("minus")}</button>
    <output aria-live="polite">${value}</output><button type="button" data-step="1" aria-label="More">${icon("plus")}</button></div>`;
}
function wireStepper(root, { min = 1, max = 30, value, onChange }) {
  const out = $("output", root);
  let v = value;
  const sync = () => {
    out.textContent = v;
    $("[data-step='-1']", root).disabled = v <= min;
    $("[data-step='1']", root).disabled = v >= max;
  };
  root.addEventListener("click", e => {
    const b = e.target.closest("[data-step]"); if (!b) return;
    v = Math.max(min, Math.min(max, v + +b.dataset.step)); sync(); haptic(8); onChange(v);
  });
  sync();
}

// Horizontal swipe on a list row: past 84px it commits. Returns nothing; the row keeps working as a tap target.
function swipeable(row, { left, right }) {
  const sw = $(".sw", row);
  let x0, y0, dx = 0, on = false, locked = false;
  row.addEventListener("touchstart", e => { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; dx = 0; on = false; locked = false; }, { passive: true });
  row.addEventListener("touchmove", e => {
    if (x0 == null || locked) return;
    const mx = e.touches[0].clientX - x0, my = e.touches[0].clientY - y0;
    if (!on) {
      if (Math.abs(my) > 10 && Math.abs(my) > Math.abs(mx)) { locked = true; return; }
      if (Math.abs(mx) < 12) return;
      on = true; row.classList.add("dragging");
    }
    dx = mx > 0 ? (right ? mx : 0) : (left ? mx : 0);
    row.classList.toggle("to-right", dx > 0);
    row.classList.toggle("to-left", dx < 0);
    row.classList.toggle("armed", Math.abs(dx) > 84);
    sw.style.transform = `translateX(${dx}px)`;
  }, { passive: true });
  row.addEventListener("touchend", () => {
    if (!on) { x0 = null; return; }
    row.classList.remove("dragging");
    const go = Math.abs(dx) > 84 ? (dx < 0 ? left : right) : null;
    row.dataset.swiped = "1"; setTimeout(() => delete row.dataset.swiped, 350);   // swallow the click that follows
    if (go) { haptic(12); sw.style.transform = `translateX(${dx < 0 ? -110 : 110}%)`; setTimeout(go, 180); }
    else { sw.style.transform = ""; row.classList.remove("to-left", "to-right", "armed"); }
    x0 = null; on = false;
  });
}

// Horizontal scrollers fade on the right until they're scrolled to the end (or don't overflow at all)
const HX = ".seg.scroll, .hscroll, .filters, .pick-days";
const atEnd = el => el.classList.toggle("at-end", el.scrollLeft + el.clientWidth >= el.scrollWidth - 4);
function markScrollers(root = document) { $$(HX, root).forEach(atEnd); }
document.addEventListener("scroll", e => { if (e.target.matches && e.target.matches(HX)) atEnd(e.target); }, true);
window.addEventListener("resize", () => markScrollers());

// ---------------------------------------------------------------- Offline queue for the shopping list
// Ticks and removals are applied on the phone at once and sent in order; with no signal they wait.
let queue = local.get("mp:queue", []);
let flushing = false;
const queueListeners = new Set();
function enqueue(op) {
  queue = queue.filter(o => !(o.id === op.id && (o.kind === op.kind || op.kind === "delete")));
  queue.push(op);
  local.set("mp:queue", queue);
  queueListeners.forEach(f => f());
  flushQueue();
}
async function flushQueue() {
  if (flushing || !queue.length) return;
  flushing = true;
  let offline = false;
  try {
    while (queue.length) {
      const op = queue[0];
      try {
        if (op.kind === "check") await api(`grocery/${op.id}/check?checked=${op.checked}${op.pantry ? "&to_pantry=true" : ""}`, "POST", null, 10000);
        else if (op.kind === "delete") await api("grocery/" + op.id, "DELETE", null, 10000);
      } catch (e) {
        if (!e.status) { offline = true; break; }     // no signal: keep it and try again later
      }
      queue.shift();
      local.set("mp:queue", queue);
    }
  } finally {
    flushing = false;
    S.offline = offline;
    queueListeners.forEach(f => f());
  }
}
window.addEventListener("online", flushQueue);
setInterval(() => { if (queue.length) flushQueue(); }, 20000);
