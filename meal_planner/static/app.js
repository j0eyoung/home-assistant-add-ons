"use strict";
// Shell: the tab bar, rendering the current tab, and start-up.

const renderers = { plan: renderPlan, recipes: renderRecipes, shop: renderShop, pantry: renderPantry };
const TABS = [["plan", "calendar", "Plan"], ["recipes", "card", "Recipes"], ["shop", "bag", "Shop"], ["pantry", "jar", "Pantry"]];

async function render(o = {}) {
  if ($("#scanner") || $(".cook")) return;
  const y = o.keepScroll ? window.scrollY : 0;
  const seq = S.seq;
  try { await renderers[S.tab](); }
  catch (e) {
    if (S.seq !== seq + 1) return;          // a newer render took over
    view.innerHTML = `<section class="empty-state">${icon("cloud-off")}<h2>Couldn't load this page</h2><p>${esc(e.message)}</p>
      <button type="button" class="btn primary" data-retry>Try again</button></section>`;
    $("[data-retry]", view).onclick = () => render();
  }
  window.scrollTo(0, y);
  markScrollers();
  updateBadge();
}

function go(tab) {
  flushLater();
  S.tab = tab;
  local.set("mp:tab", tab);
  $$(".tabs button").forEach(b => { const on = b.dataset.tab === tab; b.classList.toggle("on", on); on ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current"); });
  window.scrollTo(0, 0);
  render();
}

// Items still to get, on the Shop tab's icon
function updateBadge() {
  const n = G.items ? G.items.filter(i => !i.checked).length : 0;
  const b = $(".tabs [data-tab=shop] .badge");
  if (b) { b.textContent = n > 99 ? "99+" : n; b.hidden = !n; }
}

$(".tabs").innerHTML = TABS.map(([t, ic, label]) => `<button type="button" data-tab="${t}">${icon(ic)}<span>${label}</span>${t === "shop" ? '<b class="badge" hidden></b>' : ""}</button>`).join("");
$(".tabs").onclick = e => { const b = e.target.closest("[data-tab]"); if (b && b.dataset.tab !== S.tab) go(b.dataset.tab); else if (b) window.scrollTo({ top: 0, behavior: "smooth" }); };
window.addEventListener("scroll", () => document.body.classList.toggle("scrolled", window.scrollY > 4), { passive: true });

const start = local.get("mp:tab", "plan");
G.items = local.get("mp:items", null);
flushQueue();
go(renderers[start] ? start : "plan");
