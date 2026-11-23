"use strict";
// Plan tab: one day at a time, a strip of the 7 days on top, meals as recipe cards.

const P = { start: null, sel: null, notes: "", days: [], claude: null, polling: false };
const HINTS = ["Something quick", "Use what's in the pantry", "Vegetarian", "Chicken", "Soup", "Lighter", "Comfort food"];

const mealAt = k => { const [d, s] = k.split("|"); const day = P.days.find(x => x.date === d); return day && { day, slot: s, meal: day.meals[s] }; };

async function renderPlan() {
  const seq = ++S.seq;
  const today = todayISO();
  if (!P.start) P.start = today;
  const end = addDays(P.start, 6);
  if (!P.sel || P.sel < P.start || P.sel > end) P.sel = P.start <= today && today <= end ? today : P.start;
  const [days, gen] = await Promise.all([api(`plan?start=${P.start}`), api("plan/generate")]);
  if (seq !== S.seq) return;
  P.days = days;
  const d = days.find(x => x.date === P.sel) || days[0];
  const weekEmpty = days.every(x => SLOTS.every(s => !x.meals[s]));
  const label = dayLabel(d.date);
  view.innerHTML = `
    <header class="bar plan-bar">
      <div class="bar-row">
        <div class="day-title"><h1>${esc(label)}</h1>
          <p>${esc(fmtDay(d.date, label === "Today" || label === "Tomorrow" ? { weekday: "long", month: "long", day: "numeric" } : { month: "long", day: "numeric" }))}</p></div>
        <div class="bar-tools">
          ${P.start !== today ? `<button type="button" class="btn quiet small" data-act="today">Today</button>` : ""}
          <button type="button" class="icon-btn quiet" data-act="week" data-n="-7" aria-label="Previous week">${icon("chev-left")}</button>
          <button type="button" class="icon-btn quiet" data-act="week" data-n="7" aria-label="Next week">${icon("chev-right")}</button>
          <button type="button" class="icon-btn tinted" data-act="plan-week" aria-label="Plan the week with Claude">${icon("sparkle")}</button>
        </div>
      </div>
      <nav class="strip" aria-label="Days">${days.map(dayChip).join("")}</nav>
    </header>
    ${genNote(gen)}
    ${weekEmpty && gen.status !== "running" ? `<section class="note-card hero-empty">
        <h2>Nothing planned for these days</h2>
        <p>Claude can plan breakfast, lunch and dinner around what's in your pantry, what expires soon and your favourites.</p>
        <button type="button" class="btn primary" data-act="plan-week">${icon("sparkle")} Plan the week</button></section>` : ""}
    <section class="day" aria-label="${esc(fmtDay(d.date, { weekday: "long", month: "long", day: "numeric" }))}">
      ${SLOTS.map(s => mealCard(d, s)).join("")}
      ${dayFoot(d)}
    </section>`;
  view.onclick = planClick;
  swipeDays($(".day", view));
  if (gen.status === "running") pollGeneration(seq);
}

function dayChip(x) {
  const t = todayISO();
  const dots = SLOTS.map(s => { const m = x.meals[s]; return `<i class="${m ? (m.cooked ? "done" : "on") : ""}"></i>`; }).join("");
  return `<button type="button" class="dchip ${x.date === P.sel ? "sel" : ""} ${x.date === t ? "today" : ""}" data-act="day" data-date="${x.date}"
    aria-pressed="${x.date === P.sel}" aria-label="${esc(fmtDay(x.date, { weekday: "long", month: "long", day: "numeric" }))}">
    <span class="dw">${x.date === t ? "Today" : esc(fmtDay(x.date, { weekday: "short" }))}</span>
    <span class="dn">${parseISO(x.date).getDate()}</span><span class="dots" aria-hidden="true">${dots}</span></button>`;
}

function genNote(g) {
  if (g.status === "running") return `<div class="note-card working" role="status"><span class="spinner" aria-hidden="true"></span>
    <div><b>Claude is planning your week.</b><p>This takes a few minutes. You can leave this page; the plan and the shopping list fill in when it's done.</p></div></div>`;
  if (g.status === "error" && g.finished && Date.now() / 1000 - g.finished < 3600) return `<div class="note-card warn" role="status">
    <div><b>The last plan didn't finish.</b><p>${esc(g.message)}</p></div><button type="button" class="btn line small" data-act="plan-week">Try again</button></div>`;
  return "";
}

function mealCard(d, s) {
  const m = d.meals[s], key = `${d.date}|${s}`;
  if (!m) return emptySlot(d, s);
  const lo = m.leftover_of, n = d.people[s];
  const bits = [];
  if (lo) bits.push(`<span>${icon("box")} Leftovers from ${esc(whenText(lo))}</span>`);
  bits.push(`<button type="button" class="link" data-act="people" data-key="${key}">${icon("user")} ${people(n)}</button>`);
  if (!lo && m.match && m.match.total) bits.push(`<span class="${m.match.have === m.match.total ? "ok" : ""}">${icon("jar")} ${m.match.have} of ${m.match.total} on hand</span>`);
  if (m.calories) bits.push(`<span>${num(m.calories)} kcal</span>`);
  if (m.meal_cost) bits.push(`<span>≈ ${money(m.meal_cost)}</span>`);
  const loNote = !lo && m.leftovers.length ? `<p class="lo-note">${icon("box")} Cook for ${m.cook_for}: ${m.leftovers.map(x => `${people(x.people)} at ${esc(whenText(x))}`).join(", ")}</p>` : "";
  const main = lo
    ? (m.cooked ? `<span class="done-chip">${icon("check")} Eaten</span>` : `<button type="button" class="btn herb" data-act="eaten" data-key="${key}">${icon("check")} Eaten</button>`)
    : m.cooked ? `<span class="done-chip">${icon("check")} Cooked</span><button type="button" class="btn line" data-act="recipe" data-key="${key}">${icon("card")} Recipe</button>`
      : `<button type="button" class="btn primary" data-act="cook" data-key="${key}">${icon("pot")} Cook</button>`;
  return `<article class="meal ${s === "dinner" ? "big" : "compact"} ${m.cooked ? "is-done" : ""} ${lo ? "is-lo" : ""}">
    <button type="button" class="meal-photo" data-act="recipe" data-key="${key}" aria-label="${esc(m.name)}: open the recipe">${photo(m.image_url, m.name)}<span class="slot-tag">${SLOT_LABEL[s]}</span></button>
    <div class="meal-body">
      <h3><button type="button" class="meal-name" data-act="recipe" data-key="${key}">${esc(m.name)}</button></h3>
      <p class="meta">${bits.join("")}</p>${loNote}
    </div>
    <div class="actions">${main}${lo || m.cooked ? "" : `<button type="button" class="btn line" data-act="swap" data-key="${key}">${icon("swap")} Swap</button>`}
      <button type="button" class="icon-btn line" data-act="more" data-key="${key}" aria-label="More for ${esc(m.name)}">${icon("more")}</button></div>
  </article>`;
}

function emptySlot(d, s) {
  const key = `${d.date}|${s}`;
  const canLo = earlierMeals(d.date, s).length > 0;
  return `<article class="meal empty">
    <div class="meal-body"><h3>${SLOT_LABEL[s]}</h3><p class="meta">Nothing planned.</p></div>
    <div class="actions"><button type="button" class="btn line" data-act="ask" data-key="${key}">${icon("sparkle")} Ask Claude</button>
      <button type="button" class="btn line" data-act="pick" data-key="${key}">${icon("card")} Pick a recipe</button>
      ${canLo ? `<button type="button" class="btn line" data-act="lo-from" data-key="${key}">${icon("box")} Leftovers</button>` : ""}</div>
  </article>`;
}

function dayFoot(d) {
  const ms = SLOTS.map(s => d.meals[s]).filter(Boolean);
  const kcal = ms.reduce((t, m) => t + (m.calories || 0), 0);
  const bits = [d.cost ? `≈ ${money(d.cost)} in groceries` : "", kcal ? `${num(kcal).toLocaleString()} kcal per person` : ""].filter(Boolean);
  return bits.length ? `<p class="day-foot">${bits.join(" · ")}</p>` : "";
}

// Meals before this slot (this week), the ones that can be cooked double
function earlierMeals(date, slot) {
  const out = [];
  for (const d of P.days) for (const s of SLOTS) {
    const m = d.meals[s];
    if (d.date > date || (d.date === date && SLOTS.indexOf(s) >= SLOTS.indexOf(slot))) continue;
    if (m && !m.leftover_of) out.push({ date: d.date, slot: s, meal: m });
  }
  return out.reverse().slice(0, 8);
}

function planClick(e) {
  const b = e.target.closest("[data-act]"); if (!b) return;
  const k = b.dataset.key, at = k && mealAt(k);
  switch (b.dataset.act) {
    case "day": P.sel = b.dataset.date; render(); break;
    case "today": P.start = todayISO(); P.sel = null; render(); break;
    case "week": P.start = addDays(P.start, +b.dataset.n); P.sel = P.start; render(); break;
    case "plan-week": weekSheet(); break;
    case "cook": openCook(at.meal, { date: at.day.date, slot: at.slot, servings: at.meal.cook_for }); break;
    case "recipe": openRecipe(at.meal.recipe_id, { date: at.day.date, slot: at.slot, servings: at.meal.cook_for, cooked: at.meal.cooked, leftover: at.meal.leftover_of }); break;
    case "swap": case "ask": swapSheet(at); break;
    case "more": moreSheet(at); break;
    case "people": peopleSheet(at); break;
    case "eaten": act(() => api("plan/cooked", "POST", { date: at.day.date, slot: at.slot }), "Marked as eaten."); break;
    case "pick": S.pickFor = { date: at.day.date, slot: at.slot }; go("recipes"); break;
    case "lo-from": leftoversFromSheet(at); break;
  }
}

function swipeDays(el) {
  let x0, y0;
  el.addEventListener("touchstart", e => { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; }, { passive: true });
  el.addEventListener("touchend", e => {
    if (x0 == null || sheets.length) return;
    const dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0;
    x0 = null;
    if (Math.abs(dx) < 70 || Math.abs(dy) > 50) return;
    const i = P.days.findIndex(x => x.date === P.sel) + (dx < 0 ? 1 : -1);
    if (i < 0) { P.start = addDays(P.start, -7); P.sel = addDays(P.start, 6); }
    else if (i > 6) { P.start = addDays(P.start, 7); P.sel = P.start; }
    else P.sel = P.days[i].date;
    view.classList.remove("slide-l", "slide-r"); void view.offsetWidth;
    view.classList.add(dx < 0 ? "slide-l" : "slide-r");
    render();
  }, { passive: true });
}

function pollGeneration(seq) {
  if (P.polling) return;
  P.polling = true;
  const tick = async () => {
    if (seq !== S.seq || S.tab !== "plan") { P.polling = false; return; }
    try {
      const g = await api("plan/generate");
      if (g.status === "running") return setTimeout(tick, 4000);
      P.polling = false;
      toast(g.status === "done" ? g.message + (g.skipped ? ` ${g.skipped} meal(s) were left as they were.` : "") : "The plan didn't finish: " + g.message, { ms: 7000 });
      render();
    } catch (e) { setTimeout(tick, 6000); }
  };
  setTimeout(tick, 4000);
}

// ---------------------------------------------------------------- Sheets
async function weekSheet() {
  const t = todayISO(), start = P.start < t ? t : P.start, end = addDays(start, 6);
  const range = `${fmtDay(start, { weekday: "short", month: "short", day: "numeric" })} to ${fmtDay(end, { weekday: "short", month: "short", day: "numeric" })}`;
  const h = sheet({
    title: "Plan the week",
    body: `<p class="lede">Claude plans breakfast, lunch and dinner for ${esc(range)} around your pantry, what expires soon, your favourites and what things cost you.</p>
      <label class="field"><span>Anything Claude should know?</span>
        <textarea id="wk-notes" rows="3" placeholder="Guests on Friday, busy Wednesday, more soups…">${esc(P.notes)}</textarea></label>
      <p class="muted small">This replaces the meals already planned for those days. Your shopping list updates when it's done.</p>
      <div id="claude-slot"></div>`,
    foot: `<button type="button" class="btn line" data-rebuild>${icon("refresh")} Rebuild list</button>
      <button type="button" class="btn primary" data-gen>${icon("sparkle")} Plan ${esc(fmtDay(start, { month: "short", day: "numeric" }))}–${esc(fmtDay(end, { day: "numeric" }))}</button>`,
  });
  $("#wk-notes", h.el).oninput = e => { P.notes = e.target.value; };
  $("[data-gen]", h.el).onclick = () => act(async () => {
    await api("plan/generate", "POST", { notes: P.notes, start });
    h.close();
    toast("Planning the week. This takes a few minutes; you can leave this page.", { ms: 6000 });
  }, null, { keep: true });
  $("[data-rebuild]", h.el).onclick = () => act(async () => { await api("grocery/rebuild", "POST"); h.close(); }, "Shopping list rebuilt from the plan.");
  fillClaude($("#claude-slot", h.el), h);
}

// Claude sign-in (Claude Code CLI with the cook's subscription)
async function fillClaude(slot, h) {
  let s;
  try { s = await api("claude"); } catch (e) { return; }
  if (!slot.isConnected) return;
  const l = s.login;
  if (s.signed_in) {
    slot.innerHTML = `<div class="claude ok">${icon("check")}<span>Claude is connected with your subscription.</span><button type="button" class="btn quiet small" data-out>Disconnect</button></div>`;
  } else if (!s.cli) {
    slot.innerHTML = s.token ? "" : `<div class="claude">${icon("sparkle")}<span>Add a Claude token or API key on the add-on's Configuration tab to plan meals.</span></div>`;
  } else if (l && !l.done && l.url) {
    slot.innerHTML = `<div class="claude col"><b>Connect Claude</b>
      <p>1. <a href="${esc(l.url)}" target="_blank" rel="noopener">Open the sign-in page</a> and approve.</p>
      <label class="field"><span>2. Paste the code it shows</span><input id="cl-code" autocomplete="off"></label>
      <div class="row-btns"><button type="button" class="btn line" data-cancel>Cancel</button><button type="button" class="btn primary" data-code>Connect</button></div></div>`;
  } else if (l && !l.done) {
    slot.innerHTML = `<div class="claude"><span class="spinner" aria-hidden="true"></span><span>Starting Claude sign-in…</span></div>`;
    setTimeout(() => fillClaude(slot, h), 2000);
  } else {
    slot.innerHTML = `<div class="claude col"><b>Connect Claude</b><p>${s.token ? "Using the token from the Configuration tab. " : ""}Sign in with your Claude subscription to plan meals with no API fees.${l && l.result ? " Last attempt: " + esc(l.result) : ""}</p>
      <button type="button" class="btn line" data-in>Sign in to Claude</button></div>`;
  }
  const on = (sel, fn) => { const b = $(sel, slot); if (b) b.onclick = fn; };
  const again = () => fillClaude(slot, h);
  on("[data-in]", async () => { try { await api("claude/login", "POST"); } catch (e) { toast(e.message); } again(); });
  on("[data-code]", async () => { try { await api("claude/code", "POST", { code: $("#cl-code", slot).value }); toast("Checking…"); } catch (e) { toast(e.message); } setTimeout(again, 1500); });
  on("[data-cancel]", async () => { try { await api("claude/cancel", "POST"); } catch (e) {} again(); });
  on("[data-out]", async () => { if (await confirmSheet("Disconnect Claude?", "Planning and swaps stop working until you sign in again.", "Disconnect")) { try { await api("claude/logout", "POST"); } catch (e) { toast(e.message); } again(); } });
}

function swapSheet(at) {
  const { day, slot, meal } = at, n = day.people[slot];
  const h = sheet({
    title: meal ? `Swap ${esc(whenText({ date: day.date, slot }))}` : `Ask Claude for ${esc(whenText({ date: day.date, slot }))}`,
    body: `${meal ? `<p class="lede">Instead of ${esc(meal.name)}.</p>` : ""}
      <label class="field"><span>Anything in mind?</span><input id="hint" maxlength="300" placeholder="Something quick, uses the spinach…" enterkeyhint="go"></label>
      <div class="chips" role="group" aria-label="Ideas">${HINTS.map(x => `<button type="button" class="chip" data-hint="${esc(x)}">${esc(x)}</button>`).join("")}</div>
      <p class="muted small">Claude writes a recipe for ${people(n)} and the shopping list updates.</p>`,
    foot: `<button type="button" class="btn line" data-pick>${icon("card")} My recipes</button>
      <button type="button" class="btn primary" data-go>${icon("sparkle")} Ask Claude</button>`,
  });
  const hint = $("#hint", h.el), goBtn = $("[data-go]", h.el);
  $(".chips", h.el).onclick = e => {
    const c = e.target.closest("[data-hint]"); if (!c) return;
    const v = c.dataset.hint.toLowerCase();
    hint.value = hint.value ? `${hint.value}, ${v}` : c.dataset.hint;
    c.classList.add("on");
  };
  hint.onkeydown = e => { if (e.key === "Enter") goBtn.click(); };
  $("[data-pick]", h.el).onclick = () => { S.pickFor = { date: day.date, slot }; h.close(); go("recipes"); };
  goBtn.onclick = async () => {
    if (S.busy) return toast("Still working on the last thing…");
    goBtn.disabled = true; goBtn.innerHTML = `<span class="spinner" aria-hidden="true"></span> Claude is cooking up an idea…`;
    const ok = await act(() => api("plan/meal", "POST", { date: day.date, slot, hint: hint.value.trim() }, 300000),
      `${SLOT_LABEL[slot]} updated. Shopping list too.`, { keep: true });
    if (ok) h.close(); else { goBtn.disabled = false; goBtn.innerHTML = `${icon("sparkle")} Ask Claude`; }
  };
}

function moreSheet(at) {
  const { day, slot, meal } = at, k = { date: day.date, slot }, lo = meal.leftover_of;
  const rows = [
    ["recipe", "card", "Recipe card", "Ingredients, method and your notes"],
    !meal.cooked && !lo ? ["cooked", "check", "Mark as cooked", "Takes the ingredients out of the pantry"] : null,
    !lo ? ["leftovers", "box", meal.leftovers.length ? "Cook extra for another meal" : "Cook extra for leftovers", "Eat the rest at another meal; the list buys enough"] : null,
    ["move", "move", "Move to another day", "Whatever is there swaps into this spot"],
    ["people", "user", `Cooking for ${people(day.people[slot])}`, "Change how many are eating"],
    lo ? ["swap", "swap", "Swap for something else", "Plan a different meal here"] : null,
    ["clear", "trash", "Remove from the plan", lo ? "" : (meal.leftovers.length ? "Its leftovers go too" : ""), "danger"],
  ].filter(Boolean);
  const h = sheet({
    title: esc(meal.name),
    body: `<p class="muted sheet-sub">${esc(cap(whenText(k)))}</p><div class="menu">${rows.map(([a, ic, t, d, cls]) => `<button type="button" class="menu-row ${cls || ""}" data-m="${a}">${icon(ic)}<span><b>${esc(t)}</b>${d ? `<small>${esc(d)}</small>` : ""}</span></button>`).join("")}</div>`,
  });
  $(".menu", h.el).onclick = async e => {
    const b = e.target.closest("[data-m]"); if (!b) return;
    const a = b.dataset.m; h.close();
    if (a === "recipe") openRecipe(meal.recipe_id, { ...k, servings: meal.cook_for, cooked: meal.cooked, leftover: lo });
    if (a === "cooked") act(async () => {
      const r = await api("plan/cooked", "POST", k);
      toast(r.changed.length ? "Used: " + r.changed.map(c => `${c.name} (${fmtQty(c.left) || 0} left)`).join(", ") : "Marked as cooked. Nothing in the pantry matched.", { ms: 6000 });
    });
    if (a === "leftovers") slotPicker({ title: "Eat the leftovers at", from: k, def: { date: addDays(day.date, 1), slot: "lunch" }, verb: "Plan leftovers", leftovers: true,
      run: to => api("plan/leftovers", "POST", { ...k, to_date: to.date, to_slot: to.slot }), done: to => `Leftovers planned for ${whenText(to)}.` });
    if (a === "move") slotPicker({ title: `Move ${esc(meal.name)}`, from: k, def: { date: addDays(day.date, 1), slot }, verb: "Move here",
      run: to => api("plan/move", "POST", { ...k, to_date: to.date, to_slot: to.slot }), done: to => `Moved to ${whenText(to)}.` });
    if (a === "people") peopleSheet(at);
    if (a === "swap") swapSheet(at);
    if (a === "clear" && await confirmSheet(`Remove ${meal.name}?`, lo ? "This meal comes off the plan." : "This meal comes off the plan and the shopping list updates.", "Remove"))
      act(() => api(`plan/meal?date=${k.date}&slot=${k.slot}`, "DELETE"), "Removed from the plan.");
  };
}

// Pick a day (this week) and a meal. Used for Move, Leftovers and Add to plan.
function slotPicker({ title, from, def, verb, run, done, leftovers = false, days = null }) {
  const list = days || P.days.map(d => d.date);
  let sel = { date: list.includes(def.date) ? def.date : list[0], slot: def.slot };
  const what = to => {
    const d = P.days.find(x => x.date === to.date), m = d && d.meals[to.slot];
    if (from && to.date === from.date && to.slot === from.slot) return "That's where it is now.";
    if (leftovers && from && (to.date < from.date || (to.date === from.date && SLOTS.indexOf(to.slot) <= SLOTS.indexOf(from.slot)))) return "Leftovers have to come after the meal.";
    return m ? (leftovers ? `Replaces ${m.name}.` : from ? `${m.name} swaps into its place.` : `Replaces ${m.name}.`) : "Nothing planned there yet.";
  };
  const h = sheet({
    title,
    body: `<div class="pick-days" role="group" aria-label="Day">${list.map(d => `<button type="button" class="pday" data-d="${d}">
        <span>${d === todayISO() ? "Today" : esc(fmtDay(d, { weekday: "short" }))}</span><b>${parseISO(d).getDate()}</b></button>`).join("")}</div>
      <div class="seg wide" role="group" aria-label="Meal">${SLOTS.map(s => `<button type="button" data-s="${s}">${SLOT_LABEL[s]}</button>`).join("")}</div>
      <p class="pick-what" aria-live="polite"></p>`,
    foot: `<button type="button" class="btn line" data-close>Cancel</button><button type="button" class="btn primary" data-ok>${esc(verb)}</button>`,
  });
  const draw = () => {
    $$(".pday", h.el).forEach(b => b.classList.toggle("on", b.dataset.d === sel.date));
    $$("[data-s]", h.el).forEach(b => { b.classList.toggle("on", b.dataset.s === sel.slot); b.setAttribute("aria-pressed", b.dataset.s === sel.slot); });
    const w = what(sel);
    $(".pick-what", h.el).textContent = w;
    $("[data-ok]", h.el).disabled = /now\.|have to come/.test(w);
  };
  h.el.addEventListener("click", e => {
    const d = e.target.closest("[data-d]"), s = e.target.closest("[data-s]");
    if (d) sel.date = d.dataset.d; if (s) sel.slot = s.dataset.s;
    if (d || s) draw();
  });
  $("[data-ok]", h.el).onclick = async () => {
    const to = { ...sel };
    const ok = await act(() => run(to), done(to), { keep: true });
    if (ok) h.close();
  };
  draw();
  const on = $(".pday.on", h.el); on && on.scrollIntoView({ inline: "center", block: "nearest" });
}

function leftoversFromSheet(at) {
  const { day, slot } = at, list = earlierMeals(day.date, slot);
  const h = sheet({
    title: `Leftovers for ${esc(whenText({ date: day.date, slot }))}`,
    body: `<p class="lede">Which meal should be cooked bigger?</p><div class="menu">${list.map((x, i) => `<button type="button" class="menu-row" data-i="${i}">
      <span class="menu-ph">${photo(x.meal.image_url, x.meal.name)}</span><span><b>${esc(x.meal.name)}</b><small>${esc(whenText(x))}</small></span></button>`).join("")}</div>`,
  });
  $(".menu", h.el).onclick = e => {
    const b = e.target.closest("[data-i]"); if (!b) return;
    const src = list[+b.dataset.i];
    h.close();
    act(() => api("plan/leftovers", "POST", { date: src.date, slot: src.slot, to_date: day.date, to_slot: slot }), `Leftovers of ${src.meal.name} planned.`);
  };
}

function peopleSheet(at) {
  const { day, slot } = at;
  let n = day.people[slot], wholeDay = false;
  const h = sheet({
    title: `Who's eating ${esc(whenText({ date: day.date, slot }))}?`, cls: "small",
    body: `<div class="people-row">${icon("user")}<span>People</span>${stepper(n, { label: "People" })}</div>
      <label class="check-row"><input type="checkbox" id="pp-day"><span>Same for the whole day</span></label>
      <p class="muted small">Recipes and the shopping list scale to match.</p>`,
    foot: `<button type="button" class="btn line" data-close>Cancel</button><button type="button" class="btn primary" data-ok>Save</button>`,
  });
  wireStepper($(".stepper", h.el), { min: 1, max: 30, value: n, onChange: v => { n = v; } });
  $("#pp-day", h.el).onchange = e => { wholeDay = e.target.checked; };
  $("[data-ok]", h.el).onclick = async () => {
    const ok = await act(() => api("plan/headcount", "POST", wholeDay ? { date: day.date, headcount: n } : { date: day.date, slot, headcount: n }), null, { keep: true });
    if (ok) h.close();
  };
}
