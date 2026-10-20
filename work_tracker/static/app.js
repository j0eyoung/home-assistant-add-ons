"use strict";
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hm = m => `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
const iso = d => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
let S = null, tick = null, manual = false;

async function api(path, method = "GET", body) {
  const r = await fetch("api/" + path, { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) {
    let msg = r.statusText;
    try { const d = (await r.json()).detail; msg = typeof d === "string" ? d : "Check the form and try again."; } catch (e) {}
    throw new Error(msg);
  }
  return r.json();
}
function toast(msg, err) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast show" + (err ? " err" : "");
  clearTimeout(toast.t); toast.t = setTimeout(() => t.className = "toast", 3500);
}
async function act(fn) { try { await fn(); await load(); } catch (e) { toast(e.message, true); } }

function elapsed() {
  if (!S.running) return 0;
  const start = new Date(S.running.start.replace(" ", "T"));
  return Math.max(0, Math.floor((Date.now() - start) / 60000));
}
function renderTimer() {
  const r = S.running, box = $("#timer");
  box.className = "card" + (r ? " live" : "");
  if (!r) { box.innerHTML = `<div class="muted">No timer running</div><div class="muted">Today: ${hm(S.totals.day_minutes)}</div>`; return; }
  const what = esc(r.client) + (r.case_no ? " · case " + esc(r.case_no) : "");
  box.innerHTML = `<div class="muted">Running: ${what}${r.note ? " · " + esc(r.note) : ""}</div>
    <div class="big">${hm(elapsed())}</div>
    <div class="row sp"><span class="muted">Today: ${hm(S.totals.day_minutes)}</span><button class="btn primary" id="stop">Stop</button></div>`;
  $("#stop").onclick = () => act(() => api("timer/stop", "POST"));
}
async function renderEntries() {
  const today = iso(new Date());
  const list = await api(`entries?frm=${today}&to=${today}`);
  $("#entries").innerHTML = list.length ? list.slice().reverse().map(e => {
    const end = e.end ? e.end.slice(11, 16) : "now";
    const min = e.end ? Math.round((new Date(e.end.replace(" ", "T")) - new Date(e.start.replace(" ", "T"))) / 60000) : elapsed();
    return `<div class="card item"><div><b>${esc(e.client)}</b>${e.case_no ? " · " + esc(e.case_no) : ""}${e.billable ? "" : " · non-billable"}
      <div class="muted">${e.start.slice(11, 16)}–${end} · ${hm(min)}${e.note ? " · " + esc(e.note) : ""}</div></div>
      ${e.end ? `<button class="btn sm danger" data-del="${e.id}" aria-label="Delete entry">Delete</button>` : ""}</div>`;
  }).join("") : `<p class="muted">Nothing logged today.</p>`;
  document.querySelectorAll("[data-del]").forEach(b => b.onclick = () => confirm("Delete this entry?") && act(() => api("entries/" + b.dataset.del, "DELETE")));
}
function renderRecent() {
  $("#recent").innerHTML = S.recent.map((r, i) => `<button type="button" class="chip" data-i="${i}">${esc(r.client)}${r.case_no ? " " + esc(r.case_no) : ""}</button>`).join("");
  document.querySelectorAll(".chip").forEach(b => b.onclick = () => {
    const f = $("#start-form"), r = S.recent[+b.dataset.i];
    f.client.value = r.client; f.case_no.value = r.case_no;
  });
}
function dueLabel(t) {
  if (!t.due) return "No date";
  const today = iso(new Date());
  return t.due < today ? `Overdue since ${t.due}` : t.due === today ? "Due today" : `Due ${t.due}`;
}
function renderTasks() {
  $("#task-list").innerHTML = S.tasks.length ? S.tasks.map(t => `<div class="card item${t.due && t.due < iso(new Date()) ? " over" : ""}">
    <div><b>${esc(t.title)}</b><div class="muted">${dueLabel(t)}${t.client ? " · " + esc(t.client) : ""}${t.case_no ? " " + esc(t.case_no) : ""}</div></div>
    <div class="row">${t.due ? `<button class="btn sm" data-snooze="${t.id}">+1 day</button>` : ""}<button class="btn sm primary" data-done="${t.id}">Done</button></div></div>`).join("")
    : `<p class="muted">No open tasks.</p>`;
  document.querySelectorAll("[data-done]").forEach(b => b.onclick = () => act(() => api(`tasks/${b.dataset.done}/done`, "POST")));
  document.querySelectorAll("[data-snooze]").forEach(b => b.onclick = () => act(() => api(`tasks/${b.dataset.snooze}/snooze`, "POST")));
}
function table(title, rows) {
  const tot = rows.reduce((a, c) => a + c.hours, 0);
  return `<div class="card"><h3>${title}</h3>${rows.length ? `<table><tr><th>Client</th><th class="n">Actual</th><th class="n">Hours (0.25)</th></tr>
    ${rows.map(c => `<tr><td>${esc(c.client)}</td><td class="n">${hm(c.minutes)}</td><td class="n">${c.hours.toFixed(2)}</td></tr>`).join("")}
    <tr><th>Total</th><th class="n"></th><th class="n">${tot.toFixed(2)}</th></tr></table>` : `<p class="muted">Nothing yet.</p>`}</div>`;
}
function renderWeek() {
  $("#week-totals").innerHTML = table("Today", S.totals.day) + table("This week (from " + S.totals.week_start + ")", S.totals.week);
  $("#cases").innerHTML = S.cases.length ? `<div class="card"><h3>Case statuses</h3>${S.cases.map(c =>
    `<div class="item"><b>${esc(c.case_no)}</b><span class="muted">${esc(c.status)}</span></div>`).join("")}</div>` : "";
  $("#phone").textContent = S.phone ? "Sending to notify." + S.phone : "No phone found. Set notify_service in the add-on's Configuration tab.";
  setLink();
}
function setLink() {
  $("#x-link").href = `api/export.csv?frm=${$("#x-from").value}&to=${$("#x-to").value}`;
}
function render() {
  $("#status").textContent = (S.running ? "Timer running · " : "") + `Today ${hm(S.totals.day_minutes)} · Week ${hm(S.totals.week_minutes)}`;
  renderTimer(); renderRecent(); renderTasks(); renderWeek();
  clearInterval(tick);
  if (S.running) tick = setInterval(renderTimer, 20000);
}
async function load() {
  S = await api("state");
  render();
  await renderEntries();
}

document.querySelectorAll(".tab").forEach(b => b.onclick = () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.toggle("on", x === b));
  ["today", "tasks", "week"].forEach(id => $("#" + id).hidden = id !== b.dataset.tab);
});
$("#manual-btn").onclick = () => {
  manual = !manual;
  document.querySelectorAll(".manual").forEach(e => e.hidden = !manual);
  $("#manual-btn").textContent = manual ? "Back to timer" : "Add as manual time";
  $("#start-form button[type=submit]").textContent = manual ? "Add time" : "Start";
  $("#start-form").date.value = iso(new Date());
};
$("#start-form").onsubmit = e => {
  e.preventDefault();
  const f = e.target, base = { client: f.client.value, case_no: f.case_no.value, note: f.note.value, billable: f.billable.checked };
  act(async () => {
    if (manual) await api("entries", "POST", { ...base, date: f.date.value, minutes: parseInt(f.minutes.value || "0", 10) });
    else await api("timer/start", "POST", base);
    f.note.value = ""; f.minutes.value = "";
    toast(manual ? "Time added" : "Timer started");
  });
};
$("#task-form").onsubmit = e => {
  e.preventDefault();
  const f = e.target;
  act(async () => {
    await api("tasks", "POST", { title: f.title.value, due: f.due.value || null, client: f.client.value, case_no: f.case_no.value });
    f.reset(); toast("Task added");
  });
};
$("#test-nudge").onclick = () => act(async () => { await api("test-nudge", "POST"); toast("Test nudge sent"); });
const now = new Date(), mon = new Date(now); mon.setDate(now.getDate() - ((now.getDay() + 6) % 7));
const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
$("#x-from").value = iso(mon); $("#x-to").value = iso(sun);
$("#x-from").onchange = $("#x-to").onchange = setLink;
document.addEventListener("visibilitychange", () => { if (!document.hidden) load().catch(() => {}); });
load().catch(e => { $("#status").textContent = e.message; });
