"use strict";
// Shop tab: store tabs, tap a row to put it in the cart, swipe to remove or put away, quick add that
// understands "2 lb chicken thighs". Ticks go through the offline queue so they never wait on the signal.

const G = { store: local.get("mp:store", "all"), items: null, sugg: [], est: null, offline: false, known: null, cartOpen: false };

const flat = groups => groups.flatMap(g => g.aisles.flatMap(a => a.items.map(i => ({ ...i, store: g.store }))));
function applyQueue(items) {
  for (const op of queue) {
    const i = items.find(x => x.id === op.id);
    if (!i) continue;
    if (op.kind === "check") { i.checked = op.checked ? 1 : 0; if (op.pantry) i.stocked = 1; }
    if (op.kind === "delete") items.splice(items.indexOf(i), 1);
  }
  return items;
}
const keepItems = () => local.set("mp:items", G.items);

async function renderShop() {
  const seq = ++S.seq;
  let items, offline = false;
  try {
    const [groups, sugg, est] = await Promise.all([api("grocery", "GET", null, 12000),
      api("grocery/suggestions", "GET", null, 12000).catch(() => []), api("grocery/estimate", "GET", null, 12000).catch(() => null)]);
    items = flat(groups); G.sugg = sugg; G.est = est;
  } catch (e) {
    if (e.status) throw e;
    items = local.get("mp:items", null);
    if (!items) throw e;
    offline = true;
  }
  if (seq !== S.seq) return;
  G.items = applyQueue(items); G.offline = offline || S.offline;
  keepItems();
  drawShop();
  if (!G.known) api("grocery/known").then(k => { G.known = k; fillKnown(); }).catch(() => {});
}

function drawShop() {
  if (S.tab !== "shop" || !G.items) return;
  const typed = $("#qa") ? $("#qa").value : "", focused = document.activeElement && document.activeElement.id === "qa";
  const stores = STORE_ORDER.filter(s => G.items.some(i => i.store === s));
  if (G.store !== "all" && !stores.includes(G.store)) G.store = "all";
  const inStore = G.items.filter(i => G.store === "all" || i.store === G.store);
  const todo = inStore.filter(i => !i.checked), done = inStore.filter(i => i.checked);
  const count = s => G.items.filter(i => !i.checked && (s === "all" || i.store === s)).length;
  view.innerHTML = `
    <header class="bar shop-bar">
      <div class="bar-row"><h1>Shop</h1><p class="bar-sub">${todo.length ? `${todo.length} to get` : inStore.length ? "Everything's in the cart" : ""}</p><span id="net">${netChip()}</span></div>
      ${stores.length > 1 ? `<div class="seg scroll" role="tablist" aria-label="Store">${["all", ...stores].map(s => `<button type="button" role="tab" aria-selected="${G.store === s}" class="${G.store === s ? "on" : ""}" data-act="store" data-store="${s}">
        ${s === "all" ? "All" : STORE_SHORT[s]}<span class="n">${count(s)}</span></button>`).join("")}</div>` : ""}
      ${inStore.length ? `<div class="progress" role="progressbar" aria-label="In the cart" aria-valuemin="0" aria-valuemax="${inStore.length}" aria-valuenow="${done.length}"><i style="width:${done.length / inStore.length * 100}%"></i></div>` : ""}
    </header>
    <form class="quick" data-form="quick" autocomplete="off">
      <input id="qa" list="known" placeholder="Add an item: 2 lb chicken thighs" enterkeyhint="done" aria-label="Add an item${G.store !== "all" ? " to " + STORE_SHORT[G.store] : ""}">
      <button type="submit" class="icon-btn primary" aria-label="Add">${icon("plus")}</button><datalist id="known"></datalist></form>
    ${G.sugg.length && !G.offline ? `<section class="due"><h2>Due again</h2><div class="hscroll">${G.sugg.map((s, n) => `<button type="button" class="chip add" data-act="due" data-n="${n}">
      ${icon("plus")}<span>${esc(s.name)}<small>every ${s.every_days} days</small></span></button>`).join("")}</div></section>` : ""}
    ${todo.length ? groupsHtml(todo) : `<section class="empty-state">${icon(inStore.length ? "check" : "bag")}
      <h2>${inStore.length ? "All done here" : "Nothing on the list"}</h2>
      <p>${inStore.length ? "Everything is in the cart. Finish the trip to put things in the pantry." : "Plan some meals and the list builds itself, or add things above."}</p></section>`}
    ${done.length ? `<details class="cart" ${G.cartOpen ? "open" : ""}><summary>${icon("check")} In the cart <span class="n">${done.length}</span>${icon("chev-down", "chev")}</summary>
      <div class="list">${done.sort((a, b) => a.name.localeCompare(b.name)).map(rowHtml).join("")}</div></details>` : ""}
    <div class="shop-tools">
      ${G.items.some(i => i.checked) ? `<button type="button" class="btn herb wide" data-act="finish">${icon("check")} Finish the trip</button>` : ""}
      <button type="button" class="btn line" data-act="sync">${icon("send")} Send to Home Assistant</button>
      <button type="button" class="btn line" data-act="rebuild">${icon("refresh")} Rebuild from plan</button>
    </div>
    ${G.est && G.est.priced ? `<p class="muted small center">About ${money(G.est.total)} for the ${G.est.priced} of ${G.est.items} items you have receipt prices for.</p>` : ""}`;
  fillKnown();
  const onTab = $(".seg.scroll .on", view);
  if (onTab) onTab.parentElement.scrollLeft = onTab.offsetLeft - 40;   // keep the chosen store in view
  markScrollers(view);
  updateBadge();
  const qa = $("#qa"); qa.value = typed; if (focused) qa.focus({ preventScroll: true });
  view.onclick = shopClick;
  $("[data-form=quick]", view).onsubmit = quickAdd;
  $(".cart", view)?.addEventListener("toggle", e => { G.cartOpen = e.target.open; });
  $$(".row", view).forEach(r => swipeable(r, { left: () => removeItem(+r.dataset.id), right: r.classList.contains("checked") && r.dataset.stocked === "1" ? null : () => putAway(+r.dataset.id) }));
}

function groupsHtml(items) {
  const byAisle = list => {
    const m = new Map();
    list.sort((a, b) => (a.aisle || "Other").localeCompare(b.aisle || "Other") || a.name.localeCompare(b.name))
      .forEach(i => { const a = i.aisle || "Other"; m.has(a) || m.set(a, []); m.get(a).push(i); });
    return [...m].map(([a, l]) => `<section class="aisle"><h3>${esc(a)}</h3><div class="list">${l.map(rowHtml).join("")}</div></section>`).join("");
  };
  if (G.store !== "all") return byAisle(items);
  return STORE_ORDER.filter(s => items.some(i => i.store === s))
    .map(s => `<section class="store"><h2>${esc(STORE_LABEL[s])}</h2>${byAisle(items.filter(i => i.store === s))}</section>`).join("");
}

function rowHtml(i) {
  const note = i.note && i.note !== "manual" ? `<span class="note">${esc(i.note)}</span>` : "";
  return `<div class="row ${i.checked ? "checked" : ""}" data-id="${i.id}" data-stocked="${i.stocked ? 1 : 0}">
    <div class="sw-bg" aria-hidden="true"><span class="l">${icon("jar")} Pantry</span><span class="r">Remove ${icon("trash")}</span></div>
    <div class="sw">
      <button type="button" class="tick-area" data-act="tick" data-id="${i.id}" aria-pressed="${!!i.checked}">
        <span class="box">${icon("check")}</span>
        <span class="it"><span class="nm">${esc(i.name)}</span>${i.qty ? `<span class="q">${esc(amount(i.qty, i.unit))}</span>` : ""}${note}</span>
      </button>
      ${i.stocked ? `<span class="tag ok">${icon("jar")} In pantry</span>` : ""}
      <button type="button" class="icon-btn quiet" data-act="edit" data-id="${i.id}" aria-label="Edit ${esc(i.name)}">${icon("edit")}</button>
    </div></div>`;
}

const netChip = () => (G.offline || queue.length)
  ? `<span class="net ${G.offline ? "off" : ""}">${icon("cloud-off")}${G.offline ? "Offline" : "Sending"}${queue.length ? ` · ${queue.length} waiting` : ""}</span>` : "";
queueListeners.add(() => { G.offline = S.offline; const n = $("#net"); if (n && S.tab === "shop") n.innerHTML = netChip(); });

function fillKnown() {
  const dl = $("#known");
  if (dl && G.known && !dl.childElementCount) dl.innerHTML = G.known.map(n => `<option value="${esc(n)}">`).join("");
}

function shopClick(e) {
  const b = e.target.closest("[data-act]"); if (!b) return;
  if (b.closest(".row")?.dataset.swiped) return;
  const id = +b.dataset.id;
  switch (b.dataset.act) {
    case "tick": tickItem(id, b); break;
    case "edit": editItem(id); break;
    case "store": G.store = b.dataset.store; local.set("mp:store", G.store); drawShop(); break;
    case "due": { const s = G.sugg[+b.dataset.n]; act(() => api("grocery", "POST", { name: s.name, store: s.store }), `Added ${s.name}.`); break; }
    case "finish": finishTrip(); break;
    case "sync": act(async () => { const r = await api("grocery/sync", "POST"); toast(r.synced ? `Sent ${r.synced} item${r.synced > 1 ? "s" : ""} to your Home Assistant list.` : "Your Home Assistant list is already up to date."); }); break;
    case "rebuild": act(() => api("grocery/rebuild", "POST"), "Rebuilt from the plan."); break;
  }
}

function tickItem(id, btn) {
  const i = G.items.find(x => x.id === id); if (!i) return;
  i.checked = i.checked ? 0 : 1;
  haptic(12);
  enqueue({ kind: "check", id, checked: !!i.checked });
  keepItems();
  const row = btn.closest(".row");
  row.classList.add(i.checked ? "going" : "coming");
  btn.setAttribute("aria-pressed", !!i.checked);
  setTimeout(drawShop, 320);         // let the tick land before the row moves
}

function removeItem(id) {
  const k = G.items.findIndex(x => x.id === id); if (k < 0) return;
  const [i] = G.items.splice(k, 1);
  keepItems(); drawShop();
  later("g" + id, `Removed ${i.name}.`, () => enqueue({ kind: "delete", id }), () => { G.items.push(i); keepItems(); drawShop(); });
}

function putAway(id) {
  const i = G.items.find(x => x.id === id); if (!i) return;
  const was = { checked: i.checked, stocked: i.stocked };
  i.checked = 1; i.stocked = 1;
  keepItems(); drawShop();
  later("p" + id, `${i.name} goes in the pantry.`, () => enqueue({ kind: "check", id, checked: true, pantry: true }),
    () => { Object.assign(i, was); keepItems(); drawShop(); });
}

async function quickAdd(e) {
  e.preventDefault();
  const qa = $("#qa"), text = qa.value.trim();
  if (!text) return;
  try {
    const r = await api("grocery/quick", "POST", { text, store: G.store === "all" ? null : G.store }, 12000);
    G.items = applyQueue(flat(r.list)); keepItems();
    qa.value = "";
    if (G.known && !G.known.includes(r.item.name)) G.known.push(r.item.name);
    drawShop();
    $("#qa").focus({ preventScroll: true });
    const q = amount(r.item.qty, r.item.unit);
    toast(`Added ${q ? q + " " : ""}${r.item.name} to ${STORE_SHORT[r.item.store] || "Other"}, ${r.item.aisle}.`, { action: "Change", onAction: () => editItem(r.item.id) });
  } catch (er) {
    toast(er.status ? er.message : "You're offline. Add it again when you have signal.", { ms: 6000 });
  }
}

const AISLES = ["Produce", "Meat", "Dairy", "Bakery", "Frozen", "Pantry", "Spices", "Drinks", "Snacks", "Household", "Other"];
function editItem(id) {
  const i = G.items.find(x => x.id === id); if (!i) return;
  const aisles = [...new Set([...AISLES, ...G.items.map(x => x.aisle).filter(Boolean)])];
  let store = i.store;
  const h = sheet({
    title: "Edit item",
    body: `<label class="field"><span>Item</span><input id="ge-name" value="${esc(i.name)}" maxlength="200"></label>
      <div class="field-row"><label class="field"><span>Amount</span><input id="ge-qty" type="number" inputmode="decimal" min="0" step="any" value="${i.qty ? +(+i.qty).toFixed(2) : ""}" placeholder="Any"></label>
        <label class="field"><span>Unit</span><input id="ge-unit" list="ge-units" value="${esc(i.unit || "")}" placeholder="lb, can, bag…" maxlength="20"></label></div>
      <datalist id="ge-units">${["lb", "oz", "g", "kg", "cup", "can", "jar", "bag", "box", "pack", "bunch", "bottle", "carton", "gallon", "dozen"].map(u => `<option value="${u}">`).join("")}</datalist>
      <fieldset class="field"><legend>Store</legend><div class="seg wide">${STORE_ORDER.map(s => `<button type="button" data-s="${s}" class="${s === store ? "on" : ""}" aria-pressed="${s === store}">${STORE_SHORT[s]}</button>`).join("")}</div></fieldset>
      <label class="field"><span>Aisle</span><input id="ge-aisle" list="ge-aisles" value="${esc(i.aisle || "Other")}" maxlength="40"></label>
      <datalist id="ge-aisles">${aisles.map(a => `<option value="${esc(a)}">`).join("")}</datalist>
      <p class="muted small">Next time ${esc(i.name)} is on the list it goes to the same store and aisle.</p>`,
    foot: `<button type="button" class="btn line danger" data-del>${icon("trash")} Remove</button><button type="button" class="btn primary" data-ok>Save</button>`,
  });
  $(".seg", h.el).onclick = e => {
    const b = e.target.closest("[data-s]"); if (!b) return;
    store = b.dataset.s;
    $$("[data-s]", h.el).forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", x === b); });
  };
  $("[data-del]", h.el).onclick = () => { h.close(); removeItem(id); };
  $("[data-ok]", h.el).onclick = async () => {
    const body = { name: $("#ge-name", h.el).value.trim(), qty: +$("#ge-qty", h.el).value || 0, unit: $("#ge-unit", h.el).value.trim(),
      store, aisle: $("#ge-aisle", h.el).value.trim() || "Other" };
    if (!body.name) return toast("Give the item a name.");
    try {
      const r = await api("grocery/" + id, "PUT", body, 12000);
      Object.assign(i, r.item); keepItems(); h.close(); drawShop();
    } catch (er) { toast(er.status ? er.message : "You're offline. Edit it when you have signal.", { ms: 6000 }); }
  };
}

async function finishTrip() {
  await flushQueue();
  if (queue.length) return toast("You're offline. Finish the trip when you have signal; your ticks are saved.", { ms: 6000 });
  const done = G.items.filter(i => i.checked);
  const fresh = done.filter(i => !i.stocked), stocked = done.filter(i => i.stocked);
  const nonFood = /household|paper|cleaning|pharmacy|pet/i;
  const h = sheet({
    title: "Finish the trip",
    body: `<p class="lede">${fresh.length ? "Put these in the pantry? Untick anything that isn't food." : "Everything ticked is already in the pantry."}</p>
      ${fresh.length ? `<div class="list checks">${fresh.map(i => `<label class="check-row"><input type="checkbox" value="${i.id}" ${nonFood.test(i.aisle || "") ? "" : "checked"}>
        <span>${esc(i.name)}${i.qty ? ` <span class="q">${esc(amount(i.qty, i.unit))}</span>` : ""}</span></label>`).join("")}</div>` : ""}
      ${stocked.length ? `<p class="muted small">${stocked.length} already put away.</p>` : ""}
      <p class="muted small">Ticked items come off the list.</p>`,
    foot: `<button type="button" class="btn line" data-close>Not yet</button><button type="button" class="btn herb" data-ok>${icon("check")} Finish</button>`,
  });
  $("[data-ok]", h.el).onclick = async () => {
    const ids = $$("input[type=checkbox]:checked", h.el).map(c => +c.value);
    let res;
    const ok = await act(async () => { res = await api("grocery/finish", "POST", { to_pantry: ids }); }, null, { keep: true });
    if (!ok) return;
    h.close();
    toast(`${res.stocked ? `Put ${res.stocked} thing${res.stocked > 1 ? "s" : ""} in the pantry. ` : ""}Cleared ${res.cleared} from the list.`, { ms: 5000 });
  };
}
