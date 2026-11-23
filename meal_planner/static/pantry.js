"use strict";
// Pantry tab: search, grouped by category, use-soon strip, quick +/−, edit sheet with a real date picker,
// barcode scanning, receipt photos and item photos.

const PN = { q: "", items: [] };

async function renderPantry() {
  const seq = ++S.seq;
  const items = await api("pantry");
  if (seq !== S.seq) return;
  PN.items = items;
  view.innerHTML = `
    <header class="bar">
      <div class="bar-row"><h1>Pantry</h1><p class="bar-sub" id="pcount"></p></div>
      <form class="search" data-form="psearch" role="search">${icon("search", "search-ic")}
        <input type="search" id="pq" placeholder="Search the pantry" value="${esc(PN.q)}" aria-label="Search the pantry" enterkeyhint="search"></form>
    </header>
    <div class="tools4">
      <button type="button" class="tool primary" data-act="scan">${icon("barcode")}<span>Scan</span></button>
      <button type="button" class="tool" data-act="receipt">${icon("receipt")}<span>Receipt</span></button>
      <button type="button" class="tool" data-act="photo">${icon("camera")}<span>Photo</span></button>
      <button type="button" class="tool" data-act="add">${icon("plus")}<span>Add</span></button>
    </div>
    <div id="plist"></div>`;
  drawPantry();
  view.onclick = pantryClick;
  $("#pq").oninput = e => { PN.q = e.target.value; drawPantry(); };
  $("[data-form=psearch]", view).onsubmit = e => { e.preventDefault(); $("#pq").blur(); };
}

function drawPantry() {
  const q = PN.q.trim().toLowerCase();
  const items = PN.items.filter(i => !q || `${i.name} ${i.brand || ""} ${i.category || ""}`.toLowerCase().includes(q));
  const stocked = items.filter(i => i.qty > 0), out = items.filter(i => !(i.qty > 0));
  const soon = stocked.filter(i => i.expires && daysLeft(i.expires) <= 5).sort((a, b) => a.expires < b.expires ? -1 : 1);
  const cats = new Map();
  stocked.sort((a, b) => a.name.localeCompare(b.name)).forEach(i => { const c = (i.category || "").trim() || "Other"; cats.has(c) || cats.set(c, []); cats.get(c).push(i); });
  const order = [...cats.keys()].sort((a, b) => (a === "Other") - (b === "Other") || a.localeCompare(b));
  $("#pcount").textContent = PN.items.filter(i => i.qty > 0).length + " items";
  $("#plist").innerHTML = `
    ${soon.length && !q ? `<section class="soon"><h2>Use soon</h2><div class="hscroll">${soon.map(i => `<button type="button" class="soon-card ${daysLeft(i.expires) < 0 ? "bad" : ""}" data-act="pedit" data-id="${i.id}">
        <span class="nm">${esc(i.name)}</span><span class="when">${esc(expiryText(i.expires))}</span></button>`).join("")}</div>
      <p class="muted small">The weekly plan uses these first.</p></section>` : ""}
    ${order.map(c => `<section class="pgroup"><h2>${esc(c)}</h2><div class="list">${cats.get(c).map(pRow).join("")}</div></section>`).join("")}
    ${out.length ? `<details class="cart ranout" ${q ? "open" : ""}><summary>Ran out <span class="n">${out.length}</span>${icon("chev-down", "chev")}</summary><div class="list">${out.map(pRow).join("")}</div></details>` : ""}
    ${!items.length ? `<section class="empty-state">${icon("jar")}<h2>${q ? "Nothing matches" : "The pantry is empty"}</h2>
      <p>${q ? "Try another word, or add it." : "Scan barcodes, snap a receipt, or tick things off the shopping list and put them away."}</p></section>` : ""}`;
  markScrollers(view);
  $$("#plist .row").forEach(r => swipeable(r, { left: () => removePantry(+r.dataset.id), right: null }));
}

function pRow(i) {
  const sub = [i.brand, i.pack_size].filter(Boolean).join(" · ");
  const d = i.expires ? daysLeft(i.expires) : null;
  return `<div class="row prow ${i.qty > 0 ? "" : "out"}" data-id="${i.id}">
    <div class="sw-bg" aria-hidden="true"><span class="l"></span><span class="r">Remove ${icon("trash")}</span></div>
    <div class="sw">
      <button type="button" class="p-main" data-act="pedit" data-id="${i.id}"><span class="nm">${esc(i.name)}</span>
        ${sub || i.expires ? `<span class="sub">${esc(sub)}${i.expires ? `<span class="exp ${d < 0 ? "bad" : d <= 3 ? "warn" : ""}">${esc(expiryText(i.expires))}</span>` : ""}</span>` : ""}</button>
      ${i.qty > 0 ? `<div class="mini-step"><button type="button" data-act="pstep" data-d="-1" data-id="${i.id}" aria-label="One less ${esc(i.name)}">${icon("minus")}</button>
        <span class="q">${esc(fmtQty(i.qty))}${i.unit ? " " + esc(i.unit) : ""}</span>
        <button type="button" data-act="pstep" data-d="1" data-id="${i.id}" aria-label="One more ${esc(i.name)}">${icon("plus")}</button></div>`
        : `<button type="button" class="btn line small" data-act="pstep" data-d="1" data-id="${i.id}">${icon("plus")} Restock</button>`}
    </div></div>`;
}

function pantryClick(e) {
  const b = e.target.closest("[data-act]"); if (!b) return;
  if (b.closest(".row")?.dataset.swiped) return;
  const id = +b.dataset.id;
  switch (b.dataset.act) {
    case "pedit": pantrySheet(PN.items.find(x => x.id === id)); break;
    case "pstep": stepPantry(id, +b.dataset.d); break;
    case "add": pantrySheet(null); break;
    case "scan": startScanner(); break;
    case "receipt": if (S.busy) toast("Still working on the last thing…"); else importReceipt().catch(er => toast(er.message)); break;
    case "photo": photoItem(); break;
  }
}

// +/− save after a short pause so quick taps become one request
const pantrySaves = {};
function stepPantry(id, d) {
  const i = PN.items.find(x => x.id === id); if (!i) return;
  i.qty = Math.max(0, +(i.qty + d).toFixed(2));
  haptic(8);
  drawPantry();
  clearTimeout(pantrySaves[id]);
  pantrySaves[id] = setTimeout(async () => {
    try { await api("pantry/" + id, "PUT", { name: i.name, qty: i.qty, unit: i.unit, expires: i.expires }); }
    catch (er) { toast(er.message); render({ keepScroll: true }); }
  }, 600);
}

function removePantry(id) {
  const k = PN.items.findIndex(x => x.id === id); if (k < 0) return;
  const [i] = PN.items.splice(k, 1);
  drawPantry();
  later("pn" + id, `Removed ${i.name}.`, () => api("pantry/" + id, "DELETE").catch(er => toast(er.message)), () => { PN.items.push(i); drawPantry(); });
}

function pantrySheet(i) {
  const cats = [...new Set(PN.items.map(x => (x.category || "").trim()).filter(Boolean))].sort();
  const isNew = !i;
  i = i || { name: "", qty: 1, unit: "", expires: null, category: "" };
  const h = sheet({
    title: isNew ? "Add to the pantry" : esc(i.name),
    body: `<label class="field"><span>Name</span><input id="pe-name" value="${esc(i.name)}" maxlength="200" ${isNew ? "autofocus" : ""}></label>
      <div class="field-row"><label class="field"><span>How many</span><input id="pe-qty" type="number" inputmode="decimal" min="0" step="any" value="${+(+i.qty || 0).toFixed(2)}"></label>
        <label class="field"><span>Unit</span><input id="pe-unit" list="pe-units" value="${esc(i.unit || "")}" placeholder="items" maxlength="20"></label></div>
      <datalist id="pe-units">${["lb", "oz", "g", "kg", "cup", "can", "jar", "bag", "box", "pack", "bottle", "gallon"].map(u => `<option value="${u}">`).join("")}</datalist>
      <label class="field"><span>Shelf</span><input id="pe-cat" list="pe-cats" value="${esc(i.category || "")}" placeholder="Produce, Dairy & eggs…" maxlength="60"></label>
      <datalist id="pe-cats">${cats.map(c => `<option value="${esc(c)}">`).join("")}</datalist>
      <label class="field"><span>Best before</span><input id="pe-exp" type="date" value="${esc(i.expires || "")}"></label>
      <div class="chips" role="group" aria-label="Best before shortcuts">${[["3 days", 3], ["1 week", 7], ["2 weeks", 14], ["1 month", 30], ["None", 0]].map(([l, n]) => `<button type="button" class="chip" data-days="${n}">${l}</button>`).join("")}</div>
      ${i.barcode ? `<p class="muted small">Barcode ${esc(i.barcode)}</p>` : ""}`,
    foot: `${isNew ? `<button type="button" class="btn line" data-close>Cancel</button>` : `<button type="button" class="btn line danger" data-del>${icon("trash")} Remove</button>`}
      <button type="button" class="btn primary" data-ok>${isNew ? "Add" : "Save"}</button>`,
  });
  $(".chips", h.el).onclick = e => { const c = e.target.closest("[data-days]"); if (!c) return; $("#pe-exp", h.el).value = +c.dataset.days ? addDays(todayISO(), +c.dataset.days) : ""; };
  const del = $("[data-del]", h.el);
  if (del) del.onclick = () => { h.close(); removePantry(i.id); };
  $("[data-ok]", h.el).onclick = async () => {
    const body = { name: $("#pe-name", h.el).value.trim(), qty: +$("#pe-qty", h.el).value || 0, unit: $("#pe-unit", h.el).value.trim(),
      expires: $("#pe-exp", h.el).value || null, category: $("#pe-cat", h.el).value.trim() };
    if (!body.name) return toast("Give it a name.");
    const ok = await act(() => isNew ? api("pantry", "POST", body) : api("pantry/" + i.id, "PUT", body), isNew ? `Added ${body.name}.` : null, { keep: true });
    if (ok) h.close();
  };
}

// ---------------------------------------------------------------- Camera: barcodes, receipts, item photos
// iOS Safari has no BarcodeDetector: load the zxing-wasm polyfill (Sec-ant/barcode-detector), pinned + SRI.
async function ensureDetector() {
  if ("BarcodeDetector" in window) return true;
  try {
    await new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/barcode-detector@3.0.8/dist/iife/polyfill.js";
      s.integrity = "sha384-AQNiZ1PD/YkyuIQblEWrXvn0Byx6RIgisRdpUXjbSsLYEMsNhJxT6M3LHmS7xBZZ";
      s.crossOrigin = "anonymous";
      s.onload = res; s.onerror = rej;
      document.head.appendChild(s);
    });
  } catch (e) {}
  return "BarcodeDetector" in window;
}

// Pick (or take) a photo and downsize it to a ~1568px JPEG (what Claude reads best). Must be called from a tap.
function pickPhoto() {
  return new Promise(resolve => {
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = "image/*"; inp.capture = "environment"; inp.style.display = "none";
    document.body.appendChild(inp);              // detached inputs can be garbage-collected on iOS
    const done = v => { inp.remove(); resolve(v); };
    inp.addEventListener("cancel", () => done(null));
    inp.onchange = () => {
      const f = inp.files[0]; if (!f) return done(null);
      const img = new Image();
      img.onload = () => {
        const k = Math.min(1, 1568 / Math.max(img.width, img.height));
        const c = document.createElement("canvas"); c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(img.src);
        done(c.toDataURL("image/jpeg", 0.85).split(",")[1]);
      };
      img.onerror = () => { URL.revokeObjectURL(img.src); toast("Couldn't read that photo. Try a JPEG."); done(null); };
      img.src = URL.createObjectURL(f);
    };
    inp.click();
  });
}

async function photoItem() {
  const image = await pickPhoto(); if (!image) return;
  toast("Looking at the photo…", { ms: 0 });
  act(async () => { const t = await api("pantry/photo", "POST", { image }, 200000); toast(`Added ${t.item.name}.`); });
}

async function startScanner() {
  const ov = document.createElement("div"); ov.id = "scanner";
  ov.innerHTML = `<video playsinline muted></video><div class="scan-frame" aria-hidden="true"></div><div id="sc-panel"></div>
    <div class="scan-bar"><input id="mcode" inputmode="numeric" placeholder="Or type the barcode" aria-label="Barcode number">
    <button type="button" class="btn line" id="mok">Add</button><button type="button" class="btn primary" id="mx">Done</button></div>`;
  document.body.appendChild(ov);
  const video = $("video", ov), panel = $("#sc-panel", ov);
  let stream = null, stop = false, last = "", lastSeen = 0, inFlight = false, paused = false;
  const close = () => { stop = true; stream && stream.getTracks().forEach(t => t.stop()); ov.remove(); render({ keepScroll: true }); };

  // Unknown barcode: an in-overlay panel, so the photo button gets a real tap (file pickers need one).
  const askUnknown = bc => new Promise(resolve => {
    paused = true;
    panel.innerHTML = `<div class="scan-card"><b>Nothing knows barcode ${esc(bc)} yet.</b>
      <div class="scan-row"><input id="un-name" placeholder="What is it?" aria-label="Item name"><button type="button" class="btn primary" id="un-save">Save</button></div>
      <div class="scan-row"><button type="button" class="btn line" id="un-photo">${icon("camera")} Snap the front</button><button type="button" class="btn quiet" id="un-skip">Skip</button></div></div>`;
    const finish = () => { panel.innerHTML = ""; paused = false; resolve(); };
    $("#un-skip", panel).onclick = finish;
    $("#un-save", panel).onclick = async () => {
      const name = $("#un-name", panel).value.trim(); if (!name) return;
      try { const t = await api("pantry/teach", "POST", { barcode: bc, name }); toast(`Added ${t.item.name}.`); } catch (e) { toast(e.message); }
      finish();
    };
    $("#un-photo", panel).onclick = async () => {
      const image = await pickPhoto(); if (!image) return;
      toast("Looking at the photo…", { ms: 0 });
      try { const t = await api("pantry/photo", "POST", { image, barcode: bc }, 200000); toast(`Added ${t.item.name}.`); } catch (e) { toast(e.message); }
      finish();
    };
  });

  const hit = async code => {
    if (inFlight || paused) return;
    inFlight = true;
    try {
      haptic(60);
      const r = await api("pantry/scan", "POST", { barcode: code });
      if (r.status === "unknown") {
        if (!r.barcode) toast("That doesn't look like a product barcode.");
        else await askUnknown(r.barcode);
      } else toast(r.status === "bumped" ? `+1 ${r.item.name} (now ${fmtQty(r.item.qty)})` : `Added ${r.item.name}.`);
    } catch (e) { toast(e.message); }
    finally { inFlight = false; }
  };

  $("#mx", ov).onclick = close;
  $("#mok", ov).onclick = () => {
    const v = $("#mcode", ov).value.replace(/\D/g, "");
    if (v.length < 6 || v.length > 14) return toast("Type the digits under the barcode.");
    $("#mcode", ov).value = ""; hit(v);
  };
  $("#mcode", ov).onkeydown = e => { if (e.key === "Enter") $("#mok", ov).click(); };   // USB/Bluetooth scanners type + Enter

  try {
    const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
    if (stop) { s.getTracks().forEach(t => t.stop()); return; }   // Done was tapped while the permission prompt was up
    stream = s; video.srcObject = s; await video.play();
  } catch (e) {
    toast("The camera isn't available here (it needs HTTPS). Type the barcode or use a scanner.", { ms: 8000 });
    return;
  }
  if (!(await ensureDetector())) return toast("The scanner didn't load. Type the barcode instead.", { ms: 8000 });
  let det;
  try { det = new BarcodeDetector({ formats: ["ean_13", "ean_8", "upc_a", "upc_e", "code_128"] }); }
  catch (e) { return toast("This browser can't read barcodes. Type them instead.", { ms: 8000 }); }
  let errors = 0;
  while (!stop) {
    try {
      const f = await det.detect(video);
      errors = 0;
      if (f.length) {
        const c = f[0].rawValue; lastSeen = Date.now();
        if (c !== last) { last = c; hit(c); }          // a code re-arms only after it has left the frame
      } else if (last && Date.now() - lastSeen > 1500) last = "";
    } catch (e) {
      if (++errors === 5) toast("Scanning stopped working. Type the barcode instead.", { ms: 8000 });
    }
    await new Promise(r => setTimeout(r, 250));
  }
}

async function importReceipt() {
  const image = await pickPhoto(); if (!image) return;
  toast("Reading the receipt…", { ms: 0 });
  const r = await api("pantry/receipt", "POST", { image }, 300000);
  const items = r.items || [];
  if (!items.length) return toast("No food on that receipt.");
  $("#toast").classList.remove("show");
  const h = sheet({
    title: `Receipt: ${items.length} items`,
    body: `<p class="lede">Untick anything that shouldn't go in the pantry.</p>
      <div class="list checks">${items.map((it, n) => `<label class="check-row"><input type="checkbox" data-ri="${n}" checked>
        <span>${esc(it.name)} <span class="q">× ${esc(it.qty || 1)}${it.pack_size ? " · " + esc(it.pack_size) : ""}${it.price ? " · " + money(it.price) : ""}</span></span></label>`).join("")}</div>`,
    foot: `<button type="button" class="btn line" data-close>Cancel</button><button type="button" class="btn primary" data-ok>Add to pantry</button>`,
  });
  $("[data-ok]", h.el).onclick = async () => {
    const keep = items.filter((_, n) => $(`[data-ri="${n}"]`, h.el).checked);
    const ok = await act(async () => { const res = await api("pantry/bulk", "POST", { items: keep, store: r.store || "" }); toast(`Added ${res.added.length} items.`); }, null, { keep: true });
    if (ok) h.close();
  };
}
