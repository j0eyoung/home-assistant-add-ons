# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
One household cook (usually cooking for one, sometimes for guests) running Home Assistant on an HA Green. Uses the planner mostly on a phone inside the Home Assistant app: planning the week on the couch, cooking in the kitchen with messy hands, and ticking items off in Costco or King Soopers, sometimes with poor signal.

## Product Purpose
Plan a week of meals with Claude, keep the recipes that worked, know what is in the pantry, and walk into the store with a list grouped by store and aisle. Success: dinner is decided before 5 pm, the list is right, and food in the pantry gets used before it expires.

## Positioning
The plan, the pantry and the list are one loop: what is planned builds the list, what is bought fills the pantry (barcode, receipt or item photo), and what is cooked comes out of the pantry. Generation knows the pantry, what expires soon and what things cost from real receipts.

## Operating Context
- Served only through Home Assistant ingress (sidebar panel "Meals"); also read by Claude Terminal through `/meals/*`.
- Grocery list syncs to an HA to-do list so Google speakers can read and add items.
- Night-before prep reminder through an HA notify service.
- Stores: Costco, Costco Business Center, King Soopers, other.

## Capabilities and Constraints
- Runs on an HA Green (ARM, 4 GB RAM, eMMC): keep it light, few disk writes, no build step for the web UI (plain HTML, CSS and JavaScript in `static/`).
- Diet rule: everything except ocean fish (shrimp and freshwater fish are fine).
- Servings usually 1, with per-day and per-meal guest counts that scale recipes and the list.
- Macros are information only; there are no nutrition goals.
- Claude through the user's subscription (Claude Code CLI sign-in) or an API key.

## Brand Commitments
- Name: "Meal & Grocery Planner", panel title "Meals".
- Visual direction chosen by the user (2026-11-23): "Recipe card": warm cream paper, tomato-red and herb-green accents, food photos up front, serif headings; charcoal in dark mode. Follows the phone's light or dark setting.

## Evidence on Hand
- Recipe photos come from TheMealDB, Openverse, Pixabay or Pexels, cached in the user's S3 bucket. No other imagery exists.

## Product Principles
- Phone first, one hand: every frequent action is a thumb tap, never a typed prompt.
- The store is offline-tolerant: ticking an item never waits on the network.
- Never lose what the user typed or scanned.
- Claude suggests; the user can always swap, move or clear.

## Accessibility & Inclusion
Readable at arm's length in a kitchen or store: large type for cooking, 44 px minimum tap targets, works in both light and dark.
