"use strict";
// Phone-first UI. All requests use relative URLs (Home Assistant ingress serves this under a per-install prefix).
// User text is only ever put into the page with textContent (the h() helper), never as HTML.

const view = document.getElementById("view");
let S = null;                       // /api/state
let tab = (() => { try { return localStorage.getItem("hm-tab") || "tasks"; } catch { return "tasks"; } })();
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function h(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v === true) e.setAttribute(k, "");
    else e.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) e.append(kid.nodeType ? kid : document.createTextNode(kid));
  return e;
}

async function api(path, opt = {}) {
  const r = await fetch("api/" + path, {
    method: opt.method || (opt.json || opt.body ? "POST" : "GET"),
    headers: { ...(opt.json ? { "content-type": "application/json" } : {}), ...(opt.headers || {}) },
    body: opt.json ? JSON.stringify(opt.json) : opt.body,
  });
  if (!r.ok) {
    let msg = r.statusText || "Something went wrong";
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : (j.detail || []).map(d => d.msg).join("; ") || msg;
    } catch { /* keep statusText */ }
    throw new Error(msg);
  }
  return r.json();
}

let toastTimer;
function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 4000);
}
const fail = e => toast(e.message || String(e));

async function load() {
  try { S = await api("state"); } catch (e) { fail(e); return; }
  render();
}

// ---------- helpers ----------
const fmtDate = iso => { const [y, m, d] = iso.split("-").map(Number); return `${MONTHS[m - 1]} ${d}, ${y}`; };
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
const money = v => (v == null ? "" : "$" + Number(v).toFixed(2));
const badge = (text, kind) => h("span", { class: "badge " + (kind || "") }, text);

function dueText(t) {
  const d = t.days_until;
  if (d < 0) return `${plural(-d, "day")} overdue`;
  if (d === 0) return "Due today";
  return `Due in ${plural(d, "day")} · ${fmtDate(t.next_due)}`;
}
const every = t => `Every ${t.interval_value === 1 ? t.interval_unit.replace(/s$/, "") : t.interval_value + " " + t.interval_unit}`;
const seasonText = t => t.active_months ? "Only " + t.active_months.split(",").map(m => MONTHS[m - 1]).join(", ") : "";

// ---------- dialogs ----------
function dialog(title, body, actions) {
  const d = h("dialog", {}, h("h3", {}, title), body, h("div", { class: "dialog-actions" }, actions));
  d.addEventListener("close", () => d.remove());
  document.body.append(d);
  d.showModal();
  return d;
}

// fields: [{name, label, type, options:[[value,label]], hint, required, step, rows}]
function formDialog(title, fields, initial, submitLabel, onSubmit) {
  const inputs = {};
  const form = h("form", { method: "dialog" });
  const err = h("div", { class: "err" });
  let pair = [];
  const flush = () => { if (pair.length) { form.append(h("div", { class: "two" }, pair)); pair = []; } };
  for (const f of fields) {
    let el;
    if (f.type === "select") el = h("select", {}, f.options.map(([v, l]) => h("option", { value: v }, l)));
    else if (f.type === "textarea") el = h("textarea", {});
    else el = h("input", { type: f.type || "text", step: f.step, inputmode: f.inputmode, placeholder: f.hint || "", min: f.min });
    if (f.required) el.required = true;
    el.value = initial && initial[f.name] != null ? initial[f.name] : (f.default ?? "");
    inputs[f.name] = el;
    const lab = h("label", {}, f.label, el);
    if (f.half) pair.push(lab); else { flush(); form.append(lab); }
    if (pair.length === 2) flush();
  }
  flush();
  form.append(err);
  const dlg = dialog(title, form, [
    h("button", { type: "button", onclick: () => dlg.close() }, "Cancel"),
    h("button", { class: "primary", type: "submit", form: "hm-form" }, submitLabel),
  ]);
  form.id = "hm-form";
  form.addEventListener("submit", async ev => {
    ev.preventDefault();
    const out = {};
    for (const f of fields) {
      let v = inputs[f.name].value.trim();
      if (f.type === "number") v = v === "" ? undefined : Number(v);
      else if (v === "" && f.nullable) v = undefined;
      out[f.name] = v;
    }
    try { await onSubmit(out); dlg.close(); await load(); } catch (e) { err.textContent = e.message; }
  });
  return dlg;
}

function confirmDialog(text, label, onYes) {
  const dlg = dialog("Are you sure?", h("p", {}, text), [
    h("button", { onclick: () => dlg.close() }, "Cancel"),
    h("button", { class: "danger", onclick: async () => { dlg.close(); try { await onYes(); await load(); } catch (e) { fail(e); } } }, label),
  ]);
}

// ---------- tasks ----------
const taskFields = () => [
  { name: "name", label: "Task", required: true, hint: "HVAC filter" },
  { name: "interval_value", label: "Every", type: "number", required: true, default: 3, min: 1, half: true, inputmode: "numeric" },
  { name: "interval_unit", label: "Unit", type: "select", options: [["months", "months"], ["days", "days"]], half: true },
  { name: "last_done", label: "Last done (blank = starts today)", type: "date", nullable: true },
  { name: "active_months", label: "Only in these months (optional)", hint: "10,11 for October and November", nullable: true },
  { name: "appliance_id", label: "Appliance (optional)", type: "select", nullable: true,
    options: [["", "None"], ...S.appliances.map(a => [a.id, a.name])] },
  { name: "notes", label: "Notes", type: "textarea" },
];

function cleanTask(v) {
  const out = { ...v };
  out.appliance_id = v.appliance_id ? Number(v.appliance_id) : undefined;
  return out;
}

function addTask() {
  formDialog("New task", taskFields(), null, "Add", v => api("tasks", { json: cleanTask(v) }));
}

function editTask(t) {
  const fields = taskFields();
  formDialog("Edit task", fields, { ...t, appliance_id: t.appliance_id ?? "" }, "Save", v => {
    const body = cleanTask(v);
    // a cleared optional field has to be sent as "" to clear it
    body.active_months = v.active_months || "";
    body.appliance_id = t.appliance_id && !v.appliance_id ? 0 : body.appliance_id;
    return api("tasks/" + t.id, { method: "PATCH", json: body });
  });
}

function doneTask(t) {
  formDialog("Done: " + t.name, [
    { name: "on", label: "Date", type: "date", default: new Date().toLocaleDateString("en-CA") },
    { name: "note", label: "Note", type: "textarea" },
    { name: "parts", label: "Parts used (for reordering)", hint: "MERV 11, 20x25x1" },
    { name: "cost", label: "Cost ($)", type: "number", step: "0.01", inputmode: "decimal" },
  ], null, "Mark done", v => api(`tasks/${t.id}/done`, { json: v }));
}

async function showHistory(t) {
  let rows;
  try { rows = await api(`tasks/${t.id}/history`); } catch (e) { return fail(e); }
  const body = rows.length ? h("div", {}, rows.map(r => h("div", { class: "card" },
    h("div", { class: "row" }, h("span", { class: "title" }, fmtDate(r.done_on)), h("span", { class: "muted" }, money(r.cost))),
    r.parts && h("div", { class: "muted" }, "Parts: " + r.parts),
    r.note && h("div", {}, r.note)))) : h("p", { class: "muted" }, "Nothing logged yet.");
  const dlg = dialog("History: " + t.name, body, [h("button", { onclick: () => dlg.close() }, "Close")]);
}

function taskCard(t) {
  const sleeping = !t.in_season && t.days_until > 0;
  const snoozed = t.snoozed_until && t.snoozed_until > new Date().toLocaleDateString("en-CA");
  const app = t.appliance_id && S.appliances.find(a => a.id === t.appliance_id);
  return h("div", { class: `card ${t.status} ${sleeping ? "sleeping" : ""}` },
    h("div", { class: "row" }, h("span", { class: "title" }, t.name),
      badge(t.status === "overdue" ? "Overdue" : t.status === "soon" ? "Due soon" : "OK",
        t.status === "overdue" ? "bad" : t.status === "soon" ? "soon" : "ok")),
    h("div", { class: "muted" }, dueText(t)),
    h("div", {}, badge(every(t)), t.active_months && badge(seasonText(t)), sleeping && badge("Sleeping until season"),
      snoozed && badge("Snoozed to " + fmtDate(t.snoozed_until)), app && badge(app.name)),
    t.last_done && h("div", { class: "muted" }, "Last done " + fmtDate(t.last_done)),
    t.notes && h("div", { class: "muted" }, t.notes),
    h("div", { class: "actions" },
      h("button", { class: "primary", onclick: () => doneTask(t) }, "Done"),
      h("button", { onclick: () => api(`tasks/${t.id}/snooze`, { json: { days: 3 } }).then(() => { toast("Snoozed 3 days"); load(); }).catch(fail) }, "Snooze 3 days"),
      h("button", { onclick: () => showHistory(t) }, "History"),
      h("button", { onclick: () => editTask(t) }, "Edit"),
      h("button", { class: "danger", onclick: () => confirmDialog(`Delete "${t.name}" and its history?`, "Delete", () => api("tasks/" + t.id, { method: "DELETE" })) }, "Delete")));
}

function tasksView() {
  const due = S.tasks.filter(t => t.due).length;
  return [
    h("div", { class: "bar" }, h("span", { class: "muted" }, due ? plural(due, "task") + " due now" : "Nothing due right now"),
      h("button", { class: "primary", onclick: addTask }, "+ Task")),
    S.tasks.length ? S.tasks.map(taskCard) : h("div", { class: "empty muted" }, "No tasks yet."),
  ];
}

// ---------- files (receipts, photos) ----------
// Phone photos are 3-8 MB; shrink them in the browser before they go to the bucket.
function shrink(file) {
  if (!/^image\/(jpeg|png|webp)$/.test(file.type) || file.size < 1_500_000) return Promise.resolve(file);
  return new Promise(resolve => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const k = Math.min(1, 1800 / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      c.toBlob(b => { URL.revokeObjectURL(url); resolve(b ? new File([b], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" }) : file); }, "image/jpeg", 0.85);
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file); };
    img.src = url;
  });
}

async function upload(kind, id, file) {
  if (!file) return;
  toast("Uploading...");
  try {
    const f = await shrink(file);
    await api(`${kind}/${id}/files?filename=${encodeURIComponent(f.name || "photo.jpg")}`,
      { method: "POST", headers: { "content-type": f.type || "application/octet-stream" }, body: f });
    toast("Saved");
    await load();
  } catch (e) { fail(e); }
}

function filePicker(kind, id) {
  const ready = S.storage_ready;
  const pick = (label, capture) => {
    const input = h("input", { type: "file", accept: "image/*,application/pdf", capture, hidden: true,
      onchange: () => upload(kind, id, input.files[0]) });
    return [input, h("button", { class: "small", disabled: !ready, onclick: () => input.click() }, label)];
  };
  return h("div", { class: "actions" }, pick("Add file", null), pick("Take photo", "environment"),
    !ready && h("span", { class: "muted" }, "Set the s3_* options to store files."));
}

function fileList(files) {
  if (!files || !files.length) return null;
  return h("div", { class: "files" }, files.map(f => h("span", {},
    h("a", { href: "api/files/" + f.id, target: "_blank", rel: "noopener" }, f.filename),
    h("button", { class: "x", title: "Remove", "aria-label": "Remove " + f.filename,
      onclick: () => confirmDialog(`Remove ${f.filename}?`, "Remove", () => api("files/" + f.id, { method: "DELETE" })) }, "×"))));
}

// ---------- appliances ----------
const applianceFields = () => [
  { name: "name", label: "Appliance", required: true, hint: "Water heater" },
  { name: "brand", label: "Brand", half: true }, { name: "model", label: "Model", half: true },
  { name: "serial", label: "Serial number" },
  { name: "purchase_date", label: "Purchased", type: "date", half: true, nullable: true },
  { name: "warranty_end", label: "Warranty ends", type: "date", half: true, nullable: true },
  { name: "store", label: "Store", half: true }, { name: "price", label: "Price ($)", type: "number", step: "0.01", half: true, inputmode: "decimal" },
  { name: "lifespan_years", label: "Expected lifespan (years)", type: "number", step: "0.5", inputmode: "decimal" },
  { name: "notes", label: "Notes", type: "textarea" },
];

function editAppliance(a) {
  formDialog(a ? "Edit appliance" : "New appliance", applianceFields(), a, a ? "Save" : "Add",
    v => a ? api("appliances/" + a.id, { method: "PATCH", json: v }) : api("appliances", { json: v }));
}

function applianceCard(a) {
  const warranty = { none: null, active: ["Warranty ends " + fmtDate(a.warranty_end), "ok"],
    expiring: [`Warranty ends in ${plural(a.warranty_days_left, "day")}`, "soon"], expired: ["Warranty expired " + fmtDate(a.warranty_end), "bad"] }[a.warranty_status];
  const life = { unknown: null, ok: [`${a.age_years} of ${a.lifespan_years} years`, "ok"],
    aging: [`Aging: ${a.age_years} of ${a.lifespan_years} years`, "soon"], past: [`Past its ${a.lifespan_years} year lifespan`, "bad"] }[a.lifespan_status];
  const tasks = S.tasks.filter(t => t.appliance_id === a.id);
  return h("div", { class: "card" },
    h("div", { class: "row" }, h("span", { class: "title" }, a.name), h("span", { class: "muted" }, money(a.price))),
    h("div", { class: "muted" }, [a.brand, a.model].filter(Boolean).join(" ") + (a.serial ? " · S/N " + a.serial : "")),
    h("div", {}, warranty && badge(...warranty), life && badge(...life), a.purchase_date && badge("Bought " + fmtDate(a.purchase_date) + (a.store ? " at " + a.store : "")),
      tasks.map(t => badge(t.name + ": " + (t.status === "overdue" ? "overdue" : fmtDate(t.next_due)), t.status === "overdue" ? "bad" : ""))),
    a.notes && h("div", { class: "muted" }, a.notes),
    fileList(a.files),
    filePicker("appliances", a.id),
    h("div", { class: "actions" }, h("button", { onclick: () => editAppliance(a) }, "Edit"),
      h("button", { class: "danger", onclick: () => confirmDialog(`Delete "${a.name}" and its receipts? Linked tasks are kept.`, "Delete", () => api("appliances/" + a.id, { method: "DELETE" })) }, "Delete")));
}

function appliancesView() {
  const soon = S.appliances.filter(a => a.warranty_status === "expiring").length;
  return [
    h("div", { class: "bar" }, h("span", { class: "muted" }, soon ? plural(soon, "warranty") + " ending soon" : plural(S.appliances.length, "appliance")),
      h("button", { class: "primary", onclick: () => editAppliance(null) }, "+ Appliance")),
    S.appliances.length ? S.appliances.map(applianceCard) : h("div", { class: "empty muted" }, "No appliances yet. Add one to track its warranty and receipt."),
  ];
}

// ---------- shutoffs ----------
const KIND_ICON = { water: "💧", gas: "🔥", electric: "⚡", other: "🔧" };
const shutoffFields = () => [
  { name: "kind", label: "Kind", type: "select", options: [["water", "Water"], ["gas", "Gas"], ["electric", "Electric"], ["other", "Other"]] },
  { name: "name", label: "Name", required: true, hint: "Main water shutoff" },
  { name: "location", label: "Where is it?", type: "textarea", hint: "Basement, behind the furnace, red handle" },
  { name: "notes", label: "Notes", type: "textarea" },
];

function editShutoff(s) {
  formDialog(s ? "Edit shutoff" : "New shutoff", shutoffFields(), s, s ? "Save" : "Add",
    v => s ? api("shutoffs/" + s.id, { method: "PATCH", json: v }) : api("shutoffs", { json: v }));
}

function shutoffsView() {
  return [
    h("div", { class: "bar" }, h("span", { class: "muted" }, "Where to turn things off in an emergency"),
      h("button", { class: "primary", onclick: () => editShutoff(null) }, "+ Shutoff")),
    S.shutoffs.length ? S.shutoffs.map(s => h("div", { class: "card" },
      h("div", { class: "title" }, `${KIND_ICON[s.kind] || ""} ${s.name}`),
      s.location && h("div", {}, s.location), s.notes && h("div", { class: "muted" }, s.notes),
      fileList(s.files), filePicker("shutoffs", s.id),
      h("div", { class: "actions" }, h("button", { onclick: () => editShutoff(s) }, "Edit"),
        h("button", { class: "danger", onclick: () => confirmDialog(`Delete "${s.name}"?`, "Delete", () => api("shutoffs/" + s.id, { method: "DELETE" })) }, "Delete"))))
      : h("div", { class: "empty muted" }, "Add your water, gas and electrical shutoffs with a photo of each."),
  ];
}

// ---------- toner ----------
async function pickSensors() {
  let sensors, cfg;
  try { [sensors, cfg] = await Promise.all([api("toner/sensors"), api("toner")]); } catch (e) { return fail(e); }
  const chosen = new Set(cfg.entities.map(e => e.entity_id));
  const list = h("div", { class: "picker" });
  const search = h("input", { type: "search", placeholder: "Filter sensors (try: toner, ink, black)", value: "toner" });
  const draw = () => {
    const q = search.value.trim().toLowerCase();
    const shown = sensors.filter(s => chosen.has(s.entity_id) || !q || (s.entity_id + " " + s.name).toLowerCase().includes(q));
    list.replaceChildren(...(shown.length ? shown.map(s => h("label", {},
      h("input", { type: "checkbox", checked: chosen.has(s.entity_id) || null, onchange: ev => ev.target.checked ? chosen.add(s.entity_id) : chosen.delete(s.entity_id) }),
      h("span", {}, `${s.name} `, h("span", { class: "muted" }, `${s.entity_id} · ${s.state}`)))) : [h("div", { class: "empty muted" }, "No sensors match.")]));
  };
  search.addEventListener("input", draw);
  draw();
  const threshold = h("input", { type: "number", min: 1, max: 90, value: cfg.threshold, inputmode: "numeric" });
  const model = h("input", { type: "text", value: cfg.printer_model || "", placeholder: "HP Color LaserJet Pro M255" });
  const err = h("div", { class: "err" });
  const dlg = dialog("Toner sensors", h("div", {}, h("label", {}, "Sensors to watch (percent left)", search), list,
    h("div", { class: "two" }, h("label", {}, "Alert below (%)", threshold), h("label", {}, "Printer model", model)), err), [
    h("button", { onclick: () => dlg.close() }, "Cancel"),
    h("button", { class: "primary", onclick: async () => {
      try {
        await api("toner", { method: "PUT", json: { entities: [...chosen], threshold: Number(threshold.value) || 15, printer_model: model.value } });
        await api("toner/check", { method: "POST" });
        dlg.close(); load();
      } catch (e) { err.textContent = e.message; }
    } }, "Save"),
  ]);
}

async function checkToner() {
  try { await api("toner/check", { method: "POST" }); toast("Checked"); await load(); } catch (e) { fail(e); }
}

function tonerCard(e) {
  const low = e.status === "low";
  const kind = low ? "bad" : e.status === "ok" ? "ok" : "";
  return h("div", { class: "card" },
    h("div", { class: "row" }, h("span", { class: "title" }, e.name || e.entity_id),
      badge(e.status === "unavailable" ? "Unavailable" : low ? "Low" : e.status === "ok" ? "OK" : "Not checked yet", kind)),
    e.level != null && [h("div", { class: "level" + (low ? " low" : "") }, h("i", { style: `width:${e.level}%` })),
      h("div", { class: "muted" }, `${Math.round(e.level)}%` + (e.status === "unavailable" ? " (last reading; the sensor is unavailable)" : ""))],
    e.status === "unavailable" && e.level == null && h("div", { class: "muted" }, "The sensor is reporting unavailable. Check the printer integration in Home Assistant."),
    h("div", { class: "muted" }, e.entity_id), low && e.alerted ? h("div", { class: "muted" }, "On the shopping list.") : null);
}

function tonerView() {
  return [
    h("div", { class: "bar" }, h("span", { class: "muted" }, "Alerts add the cartridge to the shopping list"),
      h("span", {}, h("button", { onclick: checkToner }, "Check now"), " ", h("button", { class: "primary", onclick: pickSensors }, "Choose sensors"))),
    S.toner.length ? S.toner.map(tonerCard) : h("div", { class: "empty muted" }, "No toner sensors chosen yet. Tap Choose sensors."),
    h("h2", {}, "More"),
    h("div", { class: "actions" },
      h("a", { class: "btn", href: "api/calendar.ics", download: "home-maintenance.ics" }, "Download calendar (.ics)"),
      h("button", { onclick: () => api("test/reminder", { method: "POST" }).then(t => toast("Sent a test reminder for " + t.name)).catch(fail) }, "Send test reminder")),
    h("p", { class: "muted" }, "Version " + S.version),
  ];
}

// ---------- shell ----------
const TABS = [
  ["tasks", "Tasks", () => S.tasks.filter(t => t.due).length],
  ["appliances", "Appliances", () => S.appliances.filter(a => a.warranty_status === "expiring").length],
  ["shutoffs", "Shutoffs", () => 0],
  ["toner", "Toner", () => S.toner.filter(e => e.status === "low").length],
];
const VIEWS = { tasks: tasksView, appliances: appliancesView, shutoffs: shutoffsView, toner: tonerView };

function render() {
  const banner = document.getElementById("banner");
  banner.hidden = S.phone || !S.in_home_assistant;
  banner.textContent = "No phone found, so reminders cannot be sent. Install the Home Assistant companion app, or set Notify service in this add-on's Configuration tab.";
  document.getElementById("tabs").replaceChildren(...TABS.map(([id, label, count]) => {
    const n = count();
    return h("button", { role: "tab", "aria-selected": String(id === tab), onclick: () => { tab = id; try { localStorage.setItem("hm-tab", id); } catch { /* private mode */ } render(); } },
      label, n ? h("span", { class: "count" }, `(${n})`) : null);
  }));
  view.replaceChildren(...VIEWS[tab]().flat());
}

load();
