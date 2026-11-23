"use strict";
// Recipes tab (photo grid, search, filters) and the recipe card sheet (servings, rating, notes, cook, plan).

const R = { q: "", live: false, sort: "", fav: false, top: false, type: "", list: [], dirty: false };
const ORIGIN = { mealdb: "TheMealDB", recipeapi: "Recipe API", claude: "Claude", mine: "Mine" };

async function renderRecipes() {
  const seq = ++S.seq;
  const live = R.live;
  R.live = false;
  const [rs, lib] = await Promise.all([
    api(`recipes?q=${encodeURIComponent(R.q)}&live=${live}&sort=${R.sort}&fav=${R.fav}`, "GET", null, 90000), api("library")]);
  if (seq !== S.seq) return;
  R.list = rs;
  view.innerHTML = `
    <header class="bar">
      <div class="bar-row"><h1>Recipes</h1><button type="button" class="btn line small" data-act="import">${icon("download")} Import</button></div>
      <form class="search" data-form="search" role="search">${icon("search", "search-ic")}
        <input type="search" id="rq" placeholder="Search your recipes" value="${esc(R.q)}" enterkeyhint="search" aria-label="Search recipes">
        <button type="button" class="btn quiet small" data-act="online" title="Also search TheMealDB and Recipe API">Online</button></form>
      <div class="filters" role="group" aria-label="Filters">
        ${fchip("make", `${icon("jar")} Can make`, R.sort === "match")}${fchip("fav", `${icon("star")} Favorites`, R.fav)}${fchip("top", "Rated 4+", R.top)}
        ${SLOTS.map(t => fchip("type:" + t, SLOT_LABEL[t], R.type === t)).join("")}</div>
    </header>
    ${S.pickFor ? `<div class="note-card pick-banner">${icon("calendar")}<span>Choose a recipe for <b>${esc(whenText(S.pickFor))}</b>.</span>
      <button type="button" class="btn quiet small" data-act="pick-cancel">Cancel</button></div>` : ""}
    <div id="rlist"></div>
    <p class="muted small center lib-line">${lib.total} recipes stored${lib.recipeapi.enabled ? ` · Recipe API: ${lib.recipeapi.used} of ${lib.recipeapi.cap} calls this month` : ""}</p>`;
  drawRecipeList();
  view.onclick = recipesClick;
  $("[data-form=search]", view).onsubmit = e => { e.preventDefault(); R.q = $("#rq").value.trim(); $("#rq").blur(); render(); };
  $("#rq").addEventListener("search", () => { if (!$("#rq").value && R.q) { R.q = ""; render(); } });
}

const fchip = (k, label, on) => `<button type="button" class="chip ${on ? "on" : ""}" data-act="filter" data-f="${k}" aria-pressed="${on}">${label}</button>`;

function drawRecipeList() {
  const shown = R.list.filter(r => (!R.type || r.meal_type === R.type) && (!R.top || (r.rating || 0) >= 4));
  $("#rlist").innerHTML = shown.length ? `<div class="rgrid">${shown.map(rCard).join("")}</div>`
    : `<section class="empty-state">${icon("card")}<h2>${R.q ? "No recipes match" : "No recipes here yet"}</h2>
       <p>${R.q ? "Try Online to search TheMealDB and Recipe API too." : "Meals you plan save here on their own. You can also import one from a link or pasted text."}</p>
       ${R.q ? `<button type="button" class="btn primary" data-act="online">${icon("search")} Search online</button>` : `<button type="button" class="btn primary" data-act="import">${icon("download")} Import a recipe</button>`}</section>`;
}

function rCard(r) {
  const meta = [
    r.favorite ? `<span class="fav">${icon("star", "fill")}</span>` : "",
    r.rating ? `<span class="rating" aria-label="Rated ${r.rating} of 5">${r.rating}${icon("star", "fill")}</span>` : "",
    r.match && r.match.total ? `<span class="${r.match.have === r.match.total ? "ok" : ""}">${r.match.have}/${r.match.total} on hand</span>` : "",
    !r.saved ? `<span>${esc(ORIGIN[r.origin] || r.origin || "")}</span>` : "",
  ].filter(Boolean).join("");
  return `<button type="button" class="rcard" data-act="open" data-id="${r.id}">
    <span class="rphoto">${photo(r.image_url, r.name)}</span>
    <span class="rname">${esc(r.name)}</span>${meta ? `<span class="rmeta">${meta}</span>` : ""}</button>`;
}

function recipesClick(e) {
  const b = e.target.closest("[data-act]"); if (!b) return;
  const a = b.dataset.act;
  if (a === "open") openRecipe(+b.dataset.id);
  if (a === "import") importSheet();
  if (a === "online") { R.q = $("#rq").value.trim(); if (!R.q) return toast("Type what to look for first."); R.live = true; toast("Searching online…"); render(); }
  if (a === "pick-cancel") { S.pickFor = null; render(); }
  if (a === "filter") {
    const f = b.dataset.f;
    if (f === "make") { R.sort = R.sort ? "" : "match"; return render(); }
    if (f === "fav") { R.fav = !R.fav; return render(); }
    if (f === "top") R.top = !R.top;
    if (f.startsWith("type:")) R.type = R.type === f.slice(5) ? "" : f.slice(5);
    $$(".filters .chip", view).forEach(c => {
      const k = c.dataset.f, on = k === "top" ? R.top : k.startsWith("type:") ? R.type === k.slice(5) : c.classList.contains("on");
      c.classList.toggle("on", on); c.setAttribute("aria-pressed", on);
    });
    drawRecipeList();
  }
}

function importSheet() {
  const h = sheet({
    title: "Import a recipe",
    body: `<label class="field"><span>Link to a recipe</span><input id="imp-url" type="url" inputmode="url" placeholder="https://…" autocomplete="off"></label>
      <p class="or">or</p>
      <label class="field"><span>Paste the recipe</span><textarea id="imp-text" rows="6" placeholder="Ingredients and steps, as written"></textarea></label>`,
    foot: `<button type="button" class="btn line" data-close>Cancel</button><button type="button" class="btn primary" data-go>${icon("download")} Import</button>`,
  });
  const goBtn = $("[data-go]", h.el);
  goBtn.onclick = async () => {
    const url = $("#imp-url", h.el).value.trim(), text = $("#imp-text", h.el).value.trim();
    if (!url && !text) return toast("Add a link or paste the recipe.");
    goBtn.disabled = true; goBtn.innerHTML = `<span class="spinner" aria-hidden="true"></span> Reading the recipe…`;
    let res = null;
    const ok = await act(async () => { res = await api("recipes/import", "POST", { url: url || null, text: text || null }, 300000); }, null, { keep: true });
    if (!ok) { goBtn.disabled = false; goBtn.innerHTML = `${icon("download")} Import`; return; }
    h.close();
    toast(`Saved ${res.recipe.name}.`);
    openRecipe(res.id);
  };
}

// ---------------------------------------------------------------- The recipe card
const ingKey = n => String(n || "").toLowerCase();

async function openRecipe(id, ctx = {}) {
  let r;
  try { r = await api("recipes/" + id); } catch (e) { return toast(e.message); }
  const base = r.servings || 1;
  let serv = ctx.servings || base;
  const missing = new Set((r.match && r.match.missing || []).map(ingKey));
  const pick = !ctx.date && S.pickFor;
  const h = sheet({
    cls: "recipe-sheet", label: r.name,
    body: `<div class="rs-hero drag-zone">${photo(r.image_url, r.name, "rs-img")}
        <button type="button" class="icon-btn on-photo" data-close aria-label="Close">${icon("x")}</button></div>
      <article class="index-card">
        <h2 class="rs-title">${esc(r.name)}</h2>
        <div class="rs-row">
          <div class="stars" role="group" aria-label="Your rating">${[1, 2, 3, 4, 5].map(n => `<button type="button" data-rate="${n}" aria-label="${n} star${n > 1 ? "s" : ""}" aria-pressed="false">${icon("star")}</button>`).join("")}</div>
          <button type="button" class="btn line small fav-btn" data-fav aria-pressed="${!!r.favorite}">${icon("star")} <span>Favorite</span></button>
        </div>
        <p class="meta">${[r.calories ? `${num(r.calories)} kcal` : "", r.protein ? `${num(r.protein)} g protein` : "", r.carbs ? `${num(r.carbs)} g carbs` : "", r.fat ? `${num(r.fat)} g fat` : ""].filter(Boolean).map(x => `<span>${x}</span>`).join("")}${r.calories ? "<span>per serving</span>" : ""}${r.cost ? `<span>≈ ${money(r.cost)} a serving</span>` : ""}</p>
        ${ctx.date ? `<p class="meta"><span>${icon("calendar")} On the plan for ${esc(whenText(ctx))}</span>${ctx.leftover ? `<span>${icon("box")} leftovers</span>` : ""}</p>` : ""}
        <div class="rs-serv"><span>Servings</span>${stepper(serv, { label: "Servings" })}</div>
        <h3 class="rs-h">Ingredients</h3>
        <ul class="ing"></ul>
        <h3 class="rs-h">Method</h3>
        ${r.steps.length ? `<ol class="steps">${r.steps.map(s => `<li>${esc(s)}</li>`).join("")}</ol>` : `<p class="muted">No steps saved for this one.</p>`}
        <h3 class="rs-h"><label for="rs-notes">Your notes</label></h3>
        <textarea id="rs-notes" rows="3" placeholder="What you'd change next time">${esc(r.notes || "")}</textarea>
        <p class="muted small rs-saved" aria-live="polite"></p>
        <div class="rs-links">${r.source_url ? `<a class="btn quiet small" href="${esc(r.source_url)}" target="_blank" rel="noopener">${icon("link")} ${esc(hostOf(r.source_url))}</a>` : ""}
          ${r.saved && !ctx.date ? `<button type="button" class="btn quiet small danger" data-del>${icon("trash")} Delete recipe</button>` : ""}</div>
      </article>`,
    foot: `${!r.saved ? `<button type="button" class="btn line" data-save>Save</button>` : ""}
      ${ctx.date ? "" : `<button type="button" class="btn line" data-plan>${icon("calendar")} ${pick ? `Put on ${esc(whenText(pick))}` : "Add to plan"}</button>`}
      ${ctx.leftover ? "" : `<button type="button" class="btn primary" data-cook>${icon("pot")} Cook</button>`}`,
    onClose: () => { if (R.dirty && S.tab === "recipes") { R.dirty = false; render({ keepScroll: true }); } },
  });
  const el = h.el;
  const drawIngs = () => {
    const k = serv / base;
    $(".ing", el).innerHTML = r.ingredients.map(i => {
      const need = missing.has(ingKey(i.name));
      return `<li class="${need ? "need" : ""}"><span class="q">${esc(amount(i.qty * k, i.unit))}</span>
        <span class="n">${esc(i.name)}${i.note ? ` <small>${esc(i.note)}</small>` : ""}</span>${need ? `<span class="need-tag">to buy</span>` : ""}</li>`;
    }).join("") || `<li><span class="n muted">No ingredients saved.</span></li>`;
  };
  const drawMeta = () => {
    $$("[data-rate]", el).forEach(b => { const on = +b.dataset.rate <= (r.rating || 0); b.classList.toggle("on", on); b.setAttribute("aria-pressed", +b.dataset.rate === r.rating); $("svg", b).classList.toggle("fill", on); });
    const f = $("[data-fav]", el); f.setAttribute("aria-pressed", !!r.favorite); f.classList.toggle("on", !!r.favorite); $("svg", f).classList.toggle("fill", !!r.favorite);
  };
  drawIngs(); drawMeta();
  wireStepper($(".stepper", el), { min: 1, max: 40, value: serv, onChange: v => { serv = v; drawIngs(); } });

  $(".stars", el).onclick = async e => {
    const b = e.target.closest("[data-rate]"); if (!b) return;
    const v = +b.dataset.rate === r.rating ? 0 : +b.dataset.rate, was = r.rating;
    r.rating = v || null; drawMeta(); haptic(8);
    try { await api(`recipes/${r.id}/meta`, "POST", { rating: v }); R.dirty = true; r.saved = 1; } catch (er) { r.rating = was; drawMeta(); toast(er.message); }
  };
  $("[data-fav]", el).onclick = async () => {
    const on = !r.favorite; r.favorite = on ? 1 : 0; drawMeta(); haptic(8);
    try { await api(`recipes/${r.id}/favorite?on=${on}`, "POST"); R.dirty = true; toast(on ? "Added to favorites. The weekly plan brings favorites back." : "Removed from favorites."); }
    catch (er) { r.favorite = on ? 0 : 1; drawMeta(); toast(er.message); }
  };
  const notes = $("#rs-notes", el), saved = $(".rs-saved", el);
  let nt, lastNotes = notes.value;
  const saveNotes = async () => {
    clearTimeout(nt);
    if (notes.value === lastNotes) return;
    const v = notes.value;
    try { await api(`recipes/${r.id}/meta`, "POST", { notes: v }); lastNotes = v; saved.textContent = "Notes saved."; } catch (er) { saved.textContent = "Couldn't save the notes: " + er.message; }
  };
  notes.oninput = () => { saved.textContent = ""; clearTimeout(nt); nt = setTimeout(saveNotes, 1200); };
  notes.onblur = saveNotes;
  const on = (sel, fn) => { const b = $(sel, el); if (b) b.onclick = fn; };
  on("[data-cook]", () => {
    saveNotes(); h.close();
    const k = serv / base;
    openCook({ ...r, ingredients: r.ingredients.map(i => ({ ...i, qty: i.qty * k })) }, { ...ctx, servings: serv });
  });
  on("[data-save]", async () => { try { await api(`recipes/${r.id}/save`, "POST"); r.saved = 1; R.dirty = true; $("[data-save]", el).remove(); toast("Saved to your recipes."); } catch (er) { toast(er.message); } });
  on("[data-del]", async () => {
    if (!await confirmSheet(`Delete ${r.name}?`, "It leaves your recipes for good.", "Delete")) return;
    try { await api("recipes/" + r.id, "DELETE"); R.dirty = true; h.close(); toast("Recipe deleted."); } catch (er) { toast(er.message, { ms: 6000 }); }
  });
  on("[data-plan]", async () => {
    if (pick) {
      const ok = await act(() => api("plan/meal", "POST", { date: pick.date, slot: pick.slot, recipe_id: r.id }), `On the plan for ${whenText(pick)}.`, { keep: true });
      if (ok) { S.pickFor = null; P.sel = pick.date; h.close(); go("plan"); }
      return;
    }
    if (!P.days.length || P.start > todayISO()) { P.start = todayISO(); try { P.days = await api(`plan?start=${P.start}`); } catch (er) { return toast(er.message); } }
    const next = P.days.map(d => d.date);
    slotPicker({
      title: `Add ${esc(r.name)} to the plan`, def: { date: next[0], slot: r.meal_type === "breakfast" ? "breakfast" : r.meal_type === "lunch" ? "lunch" : "dinner" },
      verb: "Add to plan", days: next,
      run: to => api("plan/meal", "POST", { date: to.date, slot: to.slot, recipe_id: r.id }),
      done: to => `On the plan for ${whenText(to)}. Shopping list updated.`,
    });
  });
}

const hostOf = u => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return "Source"; } };
