---
version: 1
slug: "static-index-html"
primary_target: "static/index.html"
related_targets: []
---

Scope: the whole web UI of the Meal & Grocery Planner (Plan, Recipes, Shop, Pantry tabs, recipe sheet, cook mode). Mode: Operate.

Audience and job: one home cook on a phone inside the Home Assistant app. Plan the day's meals, cook from a recipe, shop store by store, keep the pantry current.

Constraints: vanilla HTML/CSS/JS, no build step, HA ingress (relative URLs), HA Green resources. Grocery ticks work offline.

## Direction contract

THESIS: Every meal is a recipe card you can hold: a day reads as a short stack of cards with the food photo on top, not a 7-day spreadsheet of rows and inline inputs.

OWN-WORLD: Cream index-card stock on a warm paper ground (charcoal ground with warm-grey cards in dark mode). Tomato red is the brand and primary action colour; herb green means done, in the pantry, in the cart. Young Serif headings, system UI text, Courier Prime only for measured amounts. Drawn 1.75px-stroke icons. Gingham-free, sticker-free.

STORY: Open Meals, see today's breakfast, lunch and dinner as cards with photos, tap Cook to get the recipe large on screen; flip to Shop in the store and tick items store by store, even without signal.

FIRST VIEWPORT: Header with the day name in serif and a 7-day strip (dots for planned meals, today marked). Below, the day's meal cards: photo across the top, slot and people, name in serif, pantry/kcal/cost line, Cook primary, Swap, More. Bottom tab bar: Plan, Recipes, Shop, Pantry.

FORM: Pinned by the user. seed: none (pinned) "Recipe card: warm cream paper, tomato-red and herb-green accents, food photos up front, serif headings; charcoal in dark mode", with the day-strip plan card layout they picked. Signature move: the recipe sheet's index card, a tomato rule under the title and ingredients typed in Courier Prime on faint blue rules.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
