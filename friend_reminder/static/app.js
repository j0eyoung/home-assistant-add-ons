"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const view = $("#view");
let S = null;               // the last api/state
let busy = false;           // one action at a time
let renderSeq = 0;          // a slow refresh must never paint over a newer one
let snoozedOpen = false;    // keep the Snoozed section as the user left it across refreshes

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const plural = (n, one, many = one + "s") => `${n} ${n === 1 ? one : many}`;
const byId = id => (S ? S.friends.find(f => f.id === id) : undefined);

// Errors come back as {detail}: a string, or a list of pydantic problems.
function detail(d) {
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d.map(x => {
      const msg = String((x && x.msg) || "").replace(/^Value error, /, "");
      const field = x && Array.isArray(x.loc) ? x.loc[x.loc.length - 1] : "";
      return typeof field === "string" && field !== "body" ? `${field}: ${msg}` : msg;
    }).join("; ");
  }
  return "";
}

// Every URL is relative ("api/state"): the page lives under Home Assistant's per-install ingress path.
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
    throw new Error(e.name === "AbortError" ? "That took too long. Try again." : "Could not reach the add-on.");
  } finally { clearTimeout(timer); }
  if (!r.ok) {
    if (r.status === 401) {
      if (S && S.panel_url) $("#back").hidden = false;
      throw new Error("Your Home Assistant session for this page ended. Go back to Home Assistant and open Friends again.");
    }
    let msg = r.statusText || "HTTP " + r.status;
    try { msg = detail((await r.json()).detail) || msg; } catch (e) {}
    throw new Error(msg);
  }
  try { return await r.json(); } catch (e) { throw new Error("Unexpected reply from the add-on. Reload the page."); }
}

// The toast shows inside the open sheet when there is one (a modal sheet covers the page's own toast).
function toast(msg, ms = 3500) {
  const t = $("dialog[open] .toast") || $("#toast");
  $$(".toast.show").forEach(x => { if (x !== t) x.classList.remove("show"); });
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast.t);
  if (ms) toast.t = setTimeout(() => t.classList.remove("show"), ms);
}

// Run one action at a time. keep: on failure, leave the page as it is so typed text survives.
async function act(fn, okMsg, { keep = false, btn = null, label = "" } = {}) {
  if (busy) { toast("Still working on the last thing…"); return false; }
  busy = true;
  document.body.classList.add("busy");
  const old = btn ? btn.textContent : "";
  if (btn) { btn.disabled = true; if (label) btn.textContent = label; }
  let ok = false;
  try { await fn(); ok = true; if (okMsg) toast(okMsg); } catch (e) { toast(e.message); }
  busy = false;
  document.body.classList.remove("busy");
  if (btn) { btn.disabled = false; if (label) btn.textContent = old; }
  if (ok || !keep) await render();
  return ok;
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch (e) { /* fall back below */ }
  const prev = document.activeElement;
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.cssText = "position:fixed;top:0;left:0;opacity:0";
  (document.querySelector("dialog[open]") || document.body).appendChild(ta);   // a modal sheet makes the rest of the page inert
  ta.focus();
  ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (e) {}
  ta.remove();
  if (prev && prev.focus) prev.focus();
  return ok;
}

async function copyOpener(text) {
  toast((await copyText(text)) ? "Copied." : "Could not copy. Press and hold the text to copy it.");
}

// ---------------------------------------------------------------- wording and dates
const fmt = iso => {
  if (!iso) return "";
  const d = new Date(String(iso).slice(0, 10) + "T12:00");
  if (isNaN(d)) return String(iso);
  const sameYear = S && d.getFullYear() === +S.today.slice(0, 4);
  return d.toLocaleDateString(undefined, sameYear ? { month: "short", day: "numeric" } : { month: "short", day: "numeric", year: "numeric" });
};

function cadence(d) {
  d = +d;
  if (d === 1) return "daily";
  if (d === 7) return "weekly";
  if (d === 30) return "monthly";
  if (d === 365) return "yearly";
  if (d % 30 === 0) return `every ${d / 30} months`;
  if (d % 7 === 0 && d <= 56) return `every ${d / 7} weeks`;
  return `every ${d} days`;
}

const firstLine = t => (String(t || "").split(/\r?\n/).find(l => l.trim()) || "").trim();

function since(f) {
  if (f.talked_today) return `Talked today · ${cadence(f.interval)}`;
  if (f.never_logged) return `Not logged yet · ${cadence(f.interval)}`;
  return `${plural(f.days_since, "day")} since you talked · ${cadence(f.interval)}`;
}

const tierKeys = () => Object.keys(S.tiers);
const tierLong = k => `${S.tiers[k].label} · ${cadence(S.tiers[k].days)}`;
const tierOptions = (sel, long = true) => tierKeys().map(k =>
  `<option value="${esc(k)}"${k === sel ? " selected" : ""}>${esc(long ? tierLong(k) : S.tiers[k].label)}</option>`).join("");

const isTop = () => { try { return window.top === window; } catch (e) { return false; } };

// ---------------------------------------------------------------- birthday entry (month + day + optional year)
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad2 = n => String(n).padStart(2, "0");

function bdayHTML(p, val) {
  const m = /^(?:(\d{4})-)?(\d{2})-(\d{2})$/.exec(val || "");
  const [y, mo, d] = m ? [m[1] || "", +m[2], +m[3]] : ["", 0, 0];
  const months = MONTHS.map((n, i) => `<option value="${i + 1}"${mo === i + 1 ? " selected" : ""}>${n}</option>`).join("");
  const days = Array.from({ length: 31 }, (_, i) => `<option value="${i + 1}"${d === i + 1 ? " selected" : ""}>${i + 1}</option>`).join("");
  return `<fieldset class="fld"><legend>Birthday</legend>
    <div class="bd-row">
      <select id="${p}-bm" aria-label="Birthday month"><option value="">Month</option>${months}</select>
      <select id="${p}-bd" aria-label="Birthday day"><option value="">Day</option>${days}</select>
      <input id="${p}-by" type="number" inputmode="numeric" min="1900" max="${new Date().getFullYear()}" placeholder="Year" aria-label="Birthday year (optional)" value="${esc(y)}">
    </div>
    <small class="hint">The year is optional. Clear the month and day to remove a birthday.</small></fieldset>`;
}

// null = no birthday; otherwise "MM-DD" or "YYYY-MM-DD". Throws a plain-English Error when it makes no sense.
function readBday(p) {
  const mo = $(`#${p}-bm`).value, d = $(`#${p}-bd`).value, y = $(`#${p}-by`).value.trim();
  if (!mo && !d) {
    if (y) throw new Error("Pick a month and day for the birthday, or clear the year.");
    return null;
  }
  if (!mo || !d) throw new Error("Pick both a month and a day for the birthday.");
  if (y && !/^\d{4}$/.test(y)) throw new Error("The birthday year looks like 1990.");
  const yy = y ? +y : 2000;                                   // 2000 is a leap year, so Feb 29 is allowed
  if (yy > new Date().getFullYear()) throw new Error("The birthday year is in the future.");
  const dt = new Date(yy, +mo - 1, +d);
  if (dt.getMonth() !== +mo - 1 || dt.getDate() !== +d) throw new Error("That birthday date does not exist.");
  return (y ? y + "-" : "") + pad2(mo) + "-" + pad2(d);
}

// ---------------------------------------------------------------- friend form (edit sheet and the add form)
function fieldsHTML(p, f, full) {
  const v = k => esc(f[k] ?? "");
  const tier = f.tier && S.tiers[f.tier] ? f.tier : "good";
  return `
    <label class="fld"><span>Name</span><input id="${p}-name" maxlength="80" autocomplete="off" value="${v("name")}"></label>
    <label class="fld"><span>Phone</span><input id="${p}-phone" type="tel" maxlength="40" autocomplete="off" value="${v("phone")}"></label>
    ${full ? `<label class="fld"><span>Email</span><input id="${p}-email" type="email" maxlength="120" autocomplete="off" value="${v("email")}"></label>` : ""}
    <label class="fld"><span>How close</span><select id="${p}-tier">${tierOptions(tier)}</select></label>
    ${full ? `<label class="fld"><span>Custom interval in days (optional)</span>
      <input id="${p}-interval" type="number" inputmode="numeric" min="1" max="730" value="${v("interval_days")}" placeholder="${S.tiers[tier].days}">
      <small class="hint">Leave empty to use the interval of the tier above.</small></label>` : ""}
    <label class="fld"><span>Last talked</span><input id="${p}-last" type="date" max="${esc(S.today)}" value="${esc((f.last_contact || "").slice(0, 10))}"></label>
    ${bdayHTML(p, f.birthday)}
    <label class="fld"><span>Notes</span><textarea id="${p}-notes" maxlength="2000" rows="4" placeholder="New job, sick parent, kid's birthday…">${esc(f.notes)}</textarea></label>`;
}

// The form's values as the API wants them (empty = null). Throws an Error to toast when something is off.
function readFriend(p, full) {
  const val = k => $(`#${p}-${k}`).value.trim();
  const name = val("name");
  if (!name) { $(`#${p}-name`).focus(); throw new Error("A friend needs a name."); }
  const out = { name, phone: val("phone") || null, tier: $(`#${p}-tier`).value, last_contact: val("last") || null, birthday: readBday(p), notes: $(`#${p}-notes`).value.trim() };
  if (full) {
    out.email = val("email") || null;
    const iv = val("interval");
    if (iv && !(/^\d+$/.test(iv) && +iv >= 1 && +iv <= 730)) throw new Error("The custom interval is a whole number of days, 1 to 730.");
    out.interval_days = iv ? +iv : null;
  }
  return out;
}

// ---------------------------------------------------------------- the page
function reachCard(f) {
  const score = Number(f.score) || 0;
  const pct = Math.min(score, 2) / 2 * 100;                 // the bar stops at 2.0; the tick in the middle is "due" (1.0)
  const level = score >= 2 ? "high" : score >= 1 ? "over" : "";
  const note = firstLine(f.notes);
  const soon = !f.birthday_today && f.birthday_in != null && f.birthday_in > 0 && f.birthday_in <= 7;
  const tools = [];
  if (f.opener) tools.push(`<button type="button" class="btn" data-copy="${f.id}">Copy</button>`);
  if (S.settings.claude) tools.push(`<button type="button" class="btn" data-draft="${f.id}">Draft opener</button>`);
  return `<article class="card friend${f.birthday_today ? " bday" : ""}">
    <button type="button" class="head" data-edit="${f.id}" aria-haspopup="dialog">
      <span class="line"><span class="sr">Edit </span><span class="nm">${esc(f.name)}</span><span class="chip">${esc(f.tier_label)}</span>${f.birthday_today ? '<span class="chip bd"><span aria-hidden="true">🎂</span> Birthday today</span>' : ""}</span>
      <span class="sub">${esc(since(f))}</span>
      <span class="meter ${level}"><i style="width:${pct.toFixed(1)}%"></i><span class="sr">Overdue score ${esc((Math.round(score * 10) / 10).toString())}, due at 1.</span></span>
      ${soon ? `<span class="hint">Birthday in ${plural(f.birthday_in, "day")}</span>` : ""}
      ${note ? `<span class="note1 muted">${esc(note)}</span>` : ""}
    </button>
    ${f.opener || tools.length ? `<div class="opener-box">${f.opener ? `<p class="opener">${esc(f.opener)}</p>` : ""}${tools.length ? `<div class="row">${tools.join("")}</div>` : ""}</div>` : ""}
    <div class="actions">
      <button type="button" class="btn primary" data-act="done" data-id="${f.id}">Done</button>${f.due ? `
      <button type="button" class="btn" data-act="snooze" data-id="${f.id}">Snooze</button>
      <button type="button" class="btn" data-act="skip" data-id="${f.id}">Skip</button>` : ""}
    </div>
  </article>`;
}

const miniRow = (f, right) => `<button type="button" class="mini" data-edit="${f.id}" aria-haspopup="dialog">
  <span class="sr">Edit </span><span class="nm">${esc(f.name)}</span><span class="chip">${esc(f.tier_label)}</span><span class="nx">${esc(right)}</span></button>`;

function settingsCard() {
  const s = S.settings;
  let nudges;
  if (s.notify_service) {
    nudges = `<p>Nudges: ${s.nudges_per_day} a day at ${esc(s.nudge_time)} to <b>${esc(s.notify_service)}</b></p>`;
  } else if (!s.in_home_assistant) {
    nudges = `<p><b>Nudges are off.</b> This is not running inside Home Assistant, so there is no phone to send them to.</p>`;
  } else {
    const phones = s.phones || [];
    nudges = `<p><b>Nudges are off.</b> No phone is chosen. Open this add-on's Configuration tab in Home Assistant and set <b>notify_service</b>${
      phones.length ? ` to one of these phones: ${phones.map(esc).join(", ")}.` : ` (for example mobile_app_your_phone). No phone with the Home Assistant app was found yet.`}</p>`;
  }
  const ln = S.last_nudge;
  const last = ln && ln.date ? `${esc(fmt(ln.date))}: ${esc((ln.names || []).join(", ") || "nobody")}` : "none yet";
  const claude = s.claude
    ? `<p>Claude openers: on (${esc(s.model)})</p>`
    : `<p>Claude openers: off. Add your Anthropic API key in the add-on's Configuration tab to draft openers.</p>`;
  return `<h2 class="sec">Settings</h2>
    <section class="card${s.notify_service ? "" : " warn"}" aria-label="Settings">
      ${nudges}${claude}
      <p>Last nudge: ${last}</p>
      <button type="button" class="btn" id="test-nudge"${s.notify_service ? "" : " disabled"}>Send a test nudge</button>
      <p class="hint">Sends the top of your list to your phone so you can try the Done, Snooze and Skip buttons.</p>
      <p class="muted">Friend Reminder v${esc(S.version)}</p>
    </section>`;
}

function paint() {
  const fr = S.friends;
  const reach = fr.filter(f => f.birthday_today || (f.due && !f.snoozed));
  const snoozed = fr.filter(f => !f.birthday_today && f.due && f.snoozed);
  const rest = fr.filter(f => !reach.includes(f) && !snoozed.includes(f));
  $("#status").textContent = !fr.length ? "No friends yet"
    : `${reach.length ? `${reach.length} to reach out` : "All caught up"} · ${plural(fr.length, "friend")}`;
  $("#add-btn").disabled = false;
  const back = $("#back");
  const url = S.panel_url;
  back.hidden = !(isTop() && url && /^\/(?!\/)/.test(url));
  if (!back.hidden) back.href = url;

  let html = "";
  if (!fr.length) {
    html += `<section class="card"><h3>No friends yet</h3>
      <p>Friend Reminder nudges you to get in touch with people you have not talked to in a while. Add the friends you want to keep up with and choose how close each one is.</p>
      <button type="button" class="btn primary" id="empty-add">Add friends</button></section>`;
  } else {
    html += `<h2 class="sec">Reach out</h2>`;
    html += reach.length
      ? `<p class="help">Snooze asks again in ${plural(S.snooze_days, "day")}. Skip skips this round (one full interval) without resetting the clock. Done means you talked today.</p>${reach.map(reachCard).join("")}`
      : `<p class="card muted">Nobody is due right now.</p>`;
    if (snoozed.length) {
      html += `<details id="snoozed" class="card"${snoozedOpen ? " open" : ""}><summary>Snoozed (${snoozed.length})</summary>
        ${snoozed.map(f => miniRow(f, `until ${fmt(f.snoozed_until)}`)).join("")}</details>`;
    }
    if (rest.length) html += `<h2 class="sec">Everyone else</h2><div class="card list">${rest.map(f => miniRow(f, `next: ${fmt(f.next_due)}`)).join("")}</div>`;
  }
  view.innerHTML = html + settingsCard();
}

async function render() {
  const seq = ++renderSeq;
  try {
    const st = await api("state");
    if (seq !== renderSeq) return;
    S = st;
    paint();
  } catch (e) {
    if (seq !== renderSeq) return;
    if (S) toast(e.message);
    else {
      $("#status").textContent = "Could not load";
      view.innerHTML = `<section class="card warn"><p>${esc(e.message)}</p><button type="button" class="btn" id="retry">Try again</button></section>`;
    }
  }
}

view.addEventListener("toggle", e => { if (e.target.id === "snoozed") snoozedOpen = e.target.open; }, true);

const ACTIONS = {
  done: f => `Logged: you talked to ${f.name}.`,
  snooze: f => `${f.name}: asking again in ${plural(S.snooze_days, "day")}.`,
  skip: f => `${f.name}: skipped this round (${plural(f.interval, "day")}).`,
};

async function draftOpener(f, btn, notesFieldId) {
  await act(async () => {
    // The draft is written from the saved notes, so save notes typed in the sheet first.
    if (notesFieldId) {
      const notes = $(notesFieldId).value.trim();
      if (notes !== (f.notes || "").trim()) {
        await api(`friends/${f.id}`, "PUT", { notes });
        f.notes = notes;
      }
    }
    const r = await api(`friends/${f.id}/opener`, "POST", null, 120000);
    if (notesFieldId) setEditOpener(r.opener);
  }, "Opener drafted.", { btn, label: "Drafting…" });
}

view.addEventListener("click", e => {
  const el = e.target.closest("button");
  if (!el || !view.contains(el)) return;
  if (el.dataset.edit) return openEdit(+el.dataset.edit);
  if (el.dataset.act) {
    const f = byId(+el.dataset.id);
    if (!f) return;
    return void act(() => api(`friends/${f.id}/${el.dataset.act}`, "POST"), ACTIONS[el.dataset.act](f));
  }
  if (el.dataset.copy) { const f = byId(+el.dataset.copy); return void (f && copyOpener(f.opener)); }
  if (el.dataset.draft) { const f = byId(+el.dataset.draft); return void (f && draftOpener(f, el)); }
  if (el.id === "empty-add") return void openAdd();
  if (el.id === "retry") return void render();
  if (el.id === "test-nudge") {
    return void act(async () => {
      const r = await api("nudge/test", "POST");
      toast(`Test nudge sent to ${r.sent_to} about ${r.friend}.`, 6000);
    }, null, { btn: el, label: "Sending…" });
  }
});

// ---------------------------------------------------------------- edit sheet
let editId = null;
let editOpener = "";

function setEditOpener(text) {
  editOpener = text || "";
  const p = $("#ed-opener-text");
  if (p) { p.textContent = editOpener || "No opener yet."; p.classList.toggle("muted", !editOpener); }
  const c = $("#ed-copy");
  if (c) c.hidden = !editOpener;
}

function openEdit(id) {
  const f = byId(id);
  if (!f) return;
  editId = id;
  $("#ed-title").textContent = `Edit ${f.name}`;
  const opener = f.opener || S.settings.claude ? `<div class="fld"><span>Opener</span>
      <div class="opener-box"><p class="opener" id="ed-opener-text"></p>
      <div class="row"><button type="button" class="btn" id="ed-copy">Copy</button>${S.settings.claude ? '<button type="button" class="btn" id="ed-draft">Draft opener</button>' : ""}</div></div></div>` : "";
  $("#ed-form").innerHTML = fieldsHTML("ed", f, true) + opener + `
    <div class="fld"><span>Talked on…</span>
      <div class="row nowrap"><input id="ed-talk" type="date" max="${esc(S.today)}" value="${esc(S.today)}" aria-label="Date you talked">
      <button type="button" class="btn" id="ed-talked">Log it</button></div>
      <small class="hint">Restarts the clock from that day.</small></div>`;
  setEditOpener(f.opener);
  const dlg = $("#ed-dlg");
  if (!dlg.open) dlg.showModal();
  $("#ed-form").scrollTop = 0;
}

$("#ed-form").addEventListener("change", e => {
  if (e.target.id === "ed-tier") $("#ed-interval").placeholder = S.tiers[e.target.value].days;
});

$("#ed-form").addEventListener("click", e => {
  const el = e.target.closest("button");
  const f = byId(editId);
  if (!el || !f) return;
  if (el.id === "ed-copy") return void copyOpener(editOpener);
  if (el.id === "ed-draft") return void draftOpener(f, el, "#ed-notes");
  if (el.id === "ed-talked") {
    const date = $("#ed-talk").value;
    if (!date) return toast("Pick the date you talked.");
    act(async () => {
      const r = await api(`friends/${f.id}/done`, "POST", { date });
      $("#ed-dlg").close();
      toast(r.last_contact && r.last_contact.slice(0, 10) > date
        ? "You already have a later date logged, so nothing changed."
        : `Logged: you talked to ${f.name} on ${fmt(date)}.`);
    }, null, { keep: true, btn: el });
  }
});

$("#ed-form").addEventListener("submit", e => {
  e.preventDefault();
  const f = byId(editId);
  if (!f) return;
  let body;
  try { body = readFriend("ed", true); } catch (err) { return toast(err.message); }
  act(async () => {
    await api(`friends/${f.id}`, "PUT", body);
    $("#ed-dlg").close();
    toast("Saved.");
  }, null, { keep: true, btn: $("#ed-save") });
});

$("#ed-delete").addEventListener("click", e => {
  const f = byId(editId);
  if (!f || !confirm(`Delete ${f.name}? This cannot be undone.`)) return;
  act(async () => {
    await api(`friends/${f.id}`, "DELETE");
    $("#ed-dlg").close();
    toast(`Deleted ${f.name}.`);
  }, null, { keep: true, btn: e.currentTarget });
});

$$("dialog [data-close]").forEach(b => b.addEventListener("click", () => b.closest("dialog").close()));

// ---------------------------------------------------------------- Contact Picker
const pickerApi = () => "contacts" in navigator && "ContactsManager" in window;
let pickerProps = null;       // what getProperties() says this browser can share
let pickerPropsError = "";
const propsReady = (async () => {
  if (!pickerApi() || typeof navigator.contacts.getProperties !== "function") return;
  try { pickerProps = await navigator.contacts.getProperties(); } catch (e) { pickerPropsError = `${e.name}: ${e.message}`; }
})();

function browserKind() {
  const ua = navigator.userAgent || "";
  if (/; wv\)/.test(ua)) return "android-webview";
  if (/Chrome\//.test(ua) && !/Edg\/|OPR\/|SamsungBrowser\//.test(ua)) return /Android/.test(ua) ? "chrome-android" : "chrome-desktop";
  return "other";
}

// Only ask for what the browser says it can share (name is required). Called inside the tap handler, so it must stay synchronous.
function pickProps() {
  if (!Array.isArray(pickerProps)) return ["name", "tel"];
  const want = ["name", "tel", "email"].filter(p => pickerProps.includes(p));
  if (!want.includes("name")) want.unshift("name");
  return want;
}

const FULL_LINK = `<a href="./#add" target="_top">Open full screen to pick contacts</a>`;

function diagReport(result) {
  return {
    checks: {
      secure_context: !!window.isSecureContext, api_present: pickerApi(), top_frame: isTop(),
      properties: pickerProps, properties_error: pickerPropsError || undefined,
      browser: browserKind(), protocol: location.protocol,
    },
    ua: navigator.userAgent, result, at: new Date().toISOString(),
  };
}

// Fire and forget: the server keeps the last report so the result can be read back later.
const sendDiag = (result, say) => api("diag", "POST", { report: diagReport(result) })
  .then(() => { if (say) toast("Check saved."); }, e => { if (say) toast(e.message); });

function renderPickerUi() {
  const can = pickerApi();
  $("#pick-btn").disabled = !can;
  const notes = [];
  if (!can && browserKind() === "android-webview") notes.push("The Home Assistant app cannot open your contacts. Import a contacts file below, or add friends one at a time.");
  else if (!window.isSecureContext) notes.push("The contact picker needs a secure (https) address, like your Nabu Casa address. It will not work on http://homeassistant.local:8123. Meanwhile, import a contacts file below.");
  else if (!can) notes.push("This browser does not have the contact picker. Import a contacts file below, or add friends one at a time.");
  if (can && !isTop()) notes.push(`This page is inside Home Assistant's frame, and browsers usually refuse to open the picker from a frame. ${FULL_LINK}`);
  $("#pick-note").innerHTML = notes.map(n => `<p>${n}</p>`).join("");
}

function renderChecks() {
  const secure = !!window.isSecureContext, has = pickerApi(), top = isTop(), kind = browserKind();
  const props = Array.isArray(pickerProps) ? pickerProps : null;
  const rows = [
    ["Secure page", secure, secure ? "The browser treats this page as secure (https, or this computer itself)."
      : "The page is not on https. The picker needs one, like your Nabu Casa address, not http://homeassistant.local:8123."],
    ["Contact Picker present", has, has ? "This browser offers the Contact Picker."
      : "This browser has no Contact Picker. Chrome on Android has one; the Home Assistant app's built-in browser usually does not."],
    ["Top frame", top, top ? "The page is open on its own, which the picker requires."
      : "The page is inside another page. Home Assistant shows add-ons in a frame, and the picker refuses to open from a frame."],
    ["Details it can share", !!props && props.includes("name") && props.includes("tel"),
      props ? `The browser can share: ${props.join(", ")}.`
        : !has ? "Cannot check without the Contact Picker."
        : pickerPropsError ? `The browser would not say what it can share (${pickerPropsError}).`
        : "This browser cannot say what it can share, so only names and phone numbers are requested."],
    ["Browser", kind === "chrome-android",
      kind === "chrome-android" ? "Chrome on Android, which is the browser known to have the picker."
        : kind === "chrome-desktop" ? "Chrome on a computer. The picker only exists in Chrome on Android phones."
        : kind === "android-webview" ? "Android WebView: this is the Home Assistant companion app. Its built-in browser usually cannot use the picker; Chrome can."
        : "Some other browser. Chrome on Android is the one known to have the picker."],
  ];
  $("#pick-check").innerHTML = `<ul class="checks">${rows.map(([label, ok, text]) =>
    `<li><span class="mark" aria-hidden="true">${ok ? "✅" : "❌"}</span><div class="txt"><b>${esc(label)}</b> <span class="sr">${ok ? "passed" : "failed"}.</span><br><span class="muted">${esc(text)}</span></div></li>`).join("")}</ul>
    ${top ? "" : `<p>${FULL_LINK}</p>`}`;
}

let picked = [];

function renderPicked() {
  const box = $("#pick-list");
  if (!picked.length) { box.innerHTML = ""; return; }
  box.innerHTML = `<div class="pick-head"><label class="row"><input type="checkbox" id="pick-all"> Select all</label></div>
    ${picked.map((c, i) => `<div class="pick-row">
      <label><input type="checkbox" data-pi="${i}"${c.on ? " checked" : ""}><span class="txt"><span>${esc(c.name)}</span><span class="muted">${esc(c.phone || c.email || "No phone")}</span></span></label>
      <select data-pt="${i}" aria-label="How close is ${esc(c.name)}">${tierOptions(c.tier, false)}</select></div>`).join("")}
    <button type="button" class="btn primary" id="pick-add"></button>`;
  syncPicked();
}

function syncPicked() {
  const n = picked.filter(c => c.on).length;
  const all = $("#pick-all");
  all.checked = n === picked.length;
  all.indeterminate = n > 0 && n < picked.length;
  const b = $("#pick-add");
  b.textContent = `Add ${plural(n, "friend")}`;
  b.disabled = n === 0;
}

$("#pick-list").addEventListener("change", e => {
  const t = e.target;
  if (t.id === "pick-all") { picked.forEach(c => { c.on = t.checked; }); $$("[data-pi]", $("#pick-list")).forEach(x => { x.checked = t.checked; }); }
  else if (t.dataset.pi !== undefined) picked[+t.dataset.pi].on = t.checked;
  else if (t.dataset.pt !== undefined) picked[+t.dataset.pt].tier = t.value;
  syncPicked();
});

$("#pick-list").addEventListener("click", e => {
  if (e.target.id !== "pick-add") return;
  const items = picked.filter(c => c.on).map(c => ({
    name: cut(c.name, 80), phone: c.phone ? cut(c.phone, 40) : null, email: c.email ? cut(c.email, 120) : null, tier: c.tier,
  }));
  if (!items.length) return;
  act(async () => {
    const r = await api("friends", "POST", { friends: items });
    picked = [];
    renderPicked();
    $("#add-dlg").close();
    const parts = [];
    if (r.added.length) parts.push(`Added ${plural(r.added.length, "friend")}.`);
    if (r.skipped.length) parts.push(`${r.added.length ? "Already" : "Nobody new: already"} on your list: ${r.skipped.join(", ")}.`);
    toast(parts.join(" ") || "Nothing to add.", 6000);
  }, null, { keep: true, btn: e.target });
});

const cut = (s, n) => Array.from(String(s)).slice(0, n).join("");   // by characters, so an emoji is never split

const firstOf = a => (Array.isArray(a) ? a.map(x => String(x ?? "").trim()).find(Boolean) : "") || "";

$("#pick-btn").addEventListener("click", async () => {
  if (!pickerApi()) return;
  // select() must be the first thing this tap does: it needs the tap's user activation, so nothing is awaited before it.
  let list = null, err = null;
  try { list = await navigator.contacts.select(pickProps(), { multiple: true }); } catch (e) { err = e; }
  const result = err ? `${err.name}: ${err.message}` : `ok:${list.length} contacts`;
  sendDiag(result);
  if (err) {
    $("#pick-note").innerHTML = `<p>The picker did not open: ${esc(result)}</p>${isTop() ? "" : `<p>${FULL_LINK}</p>`}`;
    return toast(err.name === "SecurityError" ? "The browser blocked the contact picker on this page." : `Contact picker failed: ${result}`, 6000);
  }
  $("#pick-note").innerHTML = "";
  picked = list.map(c => {
    const phone = firstOf(c.tel), email = firstOf(c.email);
    return { name: firstOf(c.name) || phone || email, phone, email, tier: "good", on: true };
  }).filter(c => c.name);
  renderPicked();
  if (!picked.length) return toast("No contacts picked.");
  $("#pick-list").scrollIntoView({ block: "nearest" });
});

$("#diag-save").addEventListener("click", () => { sendDiag("not tried", true); });

// ---------------------------------------------------------------- contacts file (.vcf)
// Every contact starts on "Don't remind"; pick how close you are for the people you want reminders about.
// Saving adds those as friends and remembers the rest, so the next import lists only new contacts.
const NONE = "none";
let vcf = [];                 // contacts read from the file: {name, phone, email, birthday, on_list, ignored, tier}
let vcfFilter = "";
let vcfShowAll = false;       // also list contacts already sorted (friends, and Don't remind from an earlier import)
const VCF_SHOWN = 200;        // rows drawn at once; the search narrows a big address book

// Photos make exported files large; drop them before upload (a property line plus its folded continuation lines).
const stripPhotos = t => t.replace(/^(?:[\w-]+\.)?(?:PHOTO|LOGO|SOUND|KEY)[;:][^\r\n]*(?:\r?\n[ \t][^\r\n]*)*/gim, "");

// Lower case without accents, so a search for "elo" finds "Élodie"
const fold = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

const bdayShort = b => {
  if (!b) return "";
  const [m, d] = b.slice(-5).split("-").map(Number);
  return `🎂 ${MONTHS[m - 1]} ${d}`;
};

const vcfOptions = sel => `<option value="${NONE}"${sel === NONE ? " selected" : ""}>Don't remind</option>${tierOptions(sel, false)}`;

function vcfCounts() {
  const open = vcf.filter(c => !c.on_list);
  return {
    add: open.filter(c => c.tier !== NONE).length,                  // will become friends
    park: open.filter(c => !c.ignored && c.tier === NONE).length,   // new contacts that will be set to Don't remind
    sorted: vcf.filter(c => c.on_list || c.ignored).length,
  };
}

function vcfSubline(c) {
  if (c.on_list) return "Already a friend";
  const details = [c.phone || c.email || "No phone", bdayShort(c.birthday)].filter(Boolean).join(" · ");
  return c.ignored ? `Don't remind, from an earlier import · ${details}` : details;
}

function syncVcfFooter() {
  const { add, park } = vcfCounts();
  const sum = $("#vcf-sum"), btn = $("#vcf-save");
  if (!sum || !btn) return;
  sum.textContent = add && park ? `Saving adds ${plural(add, "friend")}. The other ${plural(park, "new contact")} stay on Don't remind and won't be listed next time.`
    : add ? `Saving adds ${plural(add, "friend")}.`
    : park ? `Nobody picked yet. Saving sets all ${plural(park, "new contact")} to Don't remind, so they won't be listed next time.`
    : "Everyone in this file is already sorted.";
  btn.textContent = add ? `Add ${plural(add, "friend")} and save` : "Save";
  btn.disabled = !add && !park;
}

function renderVcf() {
  const box = $("#vcf-list");
  if (!vcf.length) { box.innerHTML = ""; return; }
  const q = fold(vcfFilter.trim());
  const { sorted } = vcfCounts();
  // A search looks through everyone, so someone set to Don't remind earlier can still be found and changed
  const rows = vcf.map((c, i) => [c, i])
    .filter(([c]) => q ? fold(c.name).includes(q) || (c.phone || "").includes(q) : vcfShowAll || (!c.on_list && !c.ignored));
  box.innerHTML = `<div class="pick-head"><label for="vcf-q" class="sr">Search contacts</label>
      <input type="search" id="vcf-q" placeholder="Search ${plural(vcf.length, "contact")}" value="${esc(vcfFilter)}" autocomplete="off"></div>
    ${sorted ? `<label class="row vcf-all"><input type="checkbox" id="vcf-all"${vcfShowAll ? " checked" : ""}> Also show the ${plural(sorted, "contact")} already sorted</label>` : ""}
    <div id="vcf-rows">${rows.slice(0, VCF_SHOWN).map(([c, i]) => `<div class="pick-row${!c.on_list && c.tier !== NONE ? " chosen" : ""}" data-row="${i}">
      <span class="txt"><span>${esc(c.name)}</span><span class="muted">${esc(vcfSubline(c))}</span></span>
      ${c.on_list ? `<span class="chip">Friend</span>` : `<select data-vt="${i}" aria-label="${esc(c.name)}: how close">${vcfOptions(c.tier)}</select>`}</div>`).join("")}
    ${rows.length > VCF_SHOWN ? `<p class="muted">Showing ${VCF_SHOWN} of ${rows.length}. Search to find someone.</p>` : ""}
    ${!rows.length ? `<p class="muted">${q ? "Nobody matches." : "Everyone in this file is already sorted. Tick the box above to see them."}</p>` : ""}</div>
    <p class="hint" id="vcf-sum"></p>
    <button type="button" class="btn primary" id="vcf-save"></button>`;
  syncVcfFooter();
}

$("#vcf-file").addEventListener("change", async e => {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";                       // choosing the same file again still fires change
  if (!file) return;
  if (file.size > 40e6) return toast("That file is too big for a contacts export.");
  act(async () => {
    const text = stripPhotos(await file.text());
    if (!/BEGIN:VCARD/i.test(text)) throw new Error("That is not a contacts (.vcf) file.");
    const r = await api("import/vcf", "POST", { text }, 120000);
    vcf = r.contacts.map(c => ({ ...c, tier: NONE }));
    vcfFilter = "";
    vcfShowAll = false;
    const { sorted } = vcfCounts();
    $("#vcf-note").textContent = `${plural(vcf.length, "contact")} in ${file.name}. Everyone starts on Don't remind: `
      + `pick how close you are for the people you want reminders about${sorted ? `. ${plural(sorted, "contact")} already sorted ${sorted === 1 ? "is" : "are"} hidden` : ""}.`;
    renderVcf();
  }, null, { keep: true, btn: $("#vcf-choose"), label: "Reading the file…" });
});

$("#vcf-list").addEventListener("input", e => {
  if (e.target.id !== "vcf-q") return;
  vcfFilter = e.target.value;
  const pos = e.target.selectionStart;
  renderVcf();
  const q = $("#vcf-q");
  q.focus();
  try { q.setSelectionRange(pos, pos); } catch (err) {}
});

$("#vcf-list").addEventListener("change", e => {
  const t = e.target;
  if (t.id === "vcf-all") { vcfShowAll = t.checked; renderVcf(); return; }
  if (t.dataset.vt === undefined) return;
  const c = vcf[+t.dataset.vt];
  c.tier = t.value;
  t.closest(".pick-row").classList.toggle("chosen", c.tier !== NONE);
  syncVcfFooter();
});

$("#vcf-list").addEventListener("click", e => {
  if (e.target.id !== "vcf-save") return;
  const open = vcf.filter(c => !c.on_list);
  const chosen = open.filter(c => c.tier !== NONE).map(c => ({
    name: cut(c.name, 80), phone: c.phone ? cut(c.phone, 40) : null, email: c.email ? cut(c.email, 120) : null,
    birthday: c.birthday, tier: c.tier,
  }));
  const ignore = open.filter(c => !c.ignored && c.tier === NONE).map(c => ({ name: cut(c.name, 80), phone: c.phone ? cut(c.phone, 40) : null }));
  if (!chosen.length && !ignore.length) return;
  if (chosen.length > 500) return toast("Add up to 500 friends at a time.");
  act(async () => {
    const r = await api("import/save", "POST", { friends: chosen, ignore });
    vcf = [];
    vcfFilter = "";
    vcfShowAll = false;
    renderVcf();
    $("#vcf-note").textContent = "";
    $("#add-dlg").close();
    const parts = [];
    if (r.added.length) parts.push(`Added ${plural(r.added.length, "friend")}.`);
    if (r.ignored) parts.push(`${plural(r.ignored, "contact")} set to Don't remind.`);
    if (r.skipped.length) parts.push(`Already on your list: ${r.skipped.join(", ")}.`);
    toast(parts.join(" ") || "Saved.", 6000);
  }, null, { keep: true, btn: e.target });
});
// ---------------------------------------------------------------- add sheet
let addBuilt = false;

async function openAdd() {
  if (!S) return;
  if (!addBuilt) { $("#ad-fields").innerHTML = fieldsHTML("ad", {}, false); addBuilt = true; }
  $$("#add-dlg input[type=date]").forEach(i => { i.max = S.today; });
  renderPickerUi();
  renderChecks();
  // Without a contact picker (e.g. the Home Assistant app), the file import is the main way in: show it first
  const pick = $("#pick-h").closest("section"), file = $("#vcf-h").closest("section");
  if (!pickerApi() && pick.nextElementSibling === file) pick.before(file);
  const dlg = $("#add-dlg");
  if (!dlg.open) dlg.showModal();
  await propsReady;          // the supported-details list may arrive a moment after the sheet opens
  renderChecks();
}

$("#add-btn").addEventListener("click", () => { openAdd(); });

$("#add-dlg").addEventListener("close", () => {
  if (location.hash === "#add") {
    try { history.replaceState(null, "", location.pathname + location.search); } catch (e) {}
  }
});

$("#ad-form").addEventListener("submit", e => {
  e.preventDefault();
  let item;
  try { item = readFriend("ad", false); } catch (err) { return toast(err.message); }
  act(async () => {
    const r = await api("friends", "POST", { friends: [item] });
    if (!r.added.length) throw new Error(`${item.name} is already on your list.`);
    $("#ad-fields").innerHTML = fieldsHTML("ad", {}, false);
    $("#add-dlg").close();
    toast(`Added ${r.added[0]}.`);
  }, null, { keep: true, btn: $("#ad-form button[type=submit]") });
});

// ---------------------------------------------------------------- start
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && !busy) render();
});

render().then(() => { if (S && location.hash === "#add") openAdd(); });
