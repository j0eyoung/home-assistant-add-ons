---
version: 1
slug: "web-src-app-tsx"
primary_target: "web/src/App.tsx"
related_targets: ["web/src/styles.css","web/src/Transactions.tsx"]
---

# Budget app: whole-app visual redesign

Scope: every tab of the Budget add-on UI (Dashboard first). Mode: Operate. Audience: the owner alone, about half quick phone checks in the Home Assistant app, half sit-down sessions on a computer. First look: this month's spending against the budget. Must not feel like a corporate banking app or a dense spreadsheet. Light and dark both, following the device.

## Direction contract

THESIS: The month reads like the green guide sign before an exit: each category with what's left, set big and right-aligned like mileage, so one glance answers where the month stands. It refuses the category default of white cards, a spending donut and a hero-metric row.

OWN-WORLD: Sign green (#0b5d3b) carries the top bar and the one sign panel, white inset border and white legends in Overpass, a Highway Gothic face. MUTCD yellow appears only where a category is over, with a diamond marker. Service blue panels carry information (safe to spend, to review). Ground is a green-tinted neutral in light mode, near-black green in dark. Sign radii 10-12px; standard web controls everywhere.

STORY: Open the app, read the month total and each category's remaining on the sign, spot any yellow, then go to the charges to check or this week's safe-to-spend. Every other tab keeps the same type, colours, tables and controls.

FIRST VIEWPORT: Phone, 390 wide: green top bar with Budget, the month, and one row of scrolling tabs with the to-review count. Then the sign: its first line "November, $526 left of $3,400" with the day marker, then a line per category, remaining right-aligned, a pace rule under each; over lines yellow with a diamond, idle lines grey. Below it two blue service panels, Safe this week and To review. Desktop: the same sign, wider, with the service panels in a right column.

FORM: Grounded candidate 5 of 7 (Interstate guide signs), seed:48f7e75fa2c8f244. Raises: nothing labeled twice (catalog sleeve); yellow reserved for over (orienteering map); idle categories print grey (character roster); state restyles a row in place (split-flap board); sticky day headers in Transactions (lexicon guide words).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Open decisions

None.
