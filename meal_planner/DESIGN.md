---
name: Meal & Grocery Planner
description: A recipe-card world for one home cook: cream card stock, tomato-red actions, herb-green for done, charcoal at night.
colors:
  paper: "#f3eadb"
  card: "#fffbf4"
  card-2: "#f4ebdd"
  sunk: "#ebdfcc"
  line: "#e3d5c0"
  line-2: "#cbb89d"
  ink: "#2a2019"
  ink-2: "#66564a"
  ink-3: "#6c5d4d"
  tomato: "#bf3f2a"
  tomato-ink: "#a2321f"
  on-tomato: "#fff8ef"
  tomato-soft: "#f7e0d6"
  herb: "#3d7536"
  herb-ink: "#2f6129"
  on-herb: "#f6fbf1"
  herb-soft: "#e0ecd6"
  amber: "#9a5b0c"
  amber-soft: "#f6e5c6"
  rule: "#bccfe2"
  paper-dark: "#1b1815"
  card-dark: "#27231f"
  card-2-dark: "#302b26"
  sunk-dark: "#141210"
  line-dark: "#3b342d"
  line-2-dark: "#51473d"
  ink-dark: "#f1e8db"
  ink-2-dark: "#c0b2a1"
  ink-3-dark: "#a99a89"
  tomato-dark: "#e0654d"
  tomato-ink-dark: "#f39079"
  on-tomato-dark: "#200f0a"
  tomato-soft-dark: "#45261f"
  herb-dark: "#8bbe7d"
  herb-ink-dark: "#a6d397"
  on-herb-dark: "#12200e"
  herb-soft-dark: "#263522"
  amber-dark: "#e8aa5c"
  amber-soft-dark: "#3d2f1d"
  rule-dark: "#33465b"
typography:
  display:
    fontFamily: "Young Serif, Iowan Old Style, Palatino Linotype, Georgia, serif"
    fontSize: "30px"
    fontWeight: 400
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Young Serif, Iowan Old Style, Palatino Linotype, Georgia, serif"
    fontSize: "24px"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Young Serif, Iowan Old Style, Palatino Linotype, Georgia, serif"
    fontSize: "19px"
    fontWeight: 400
    lineHeight: 1.22
    letterSpacing: "-0.01em"
  body:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.4
  amount:
    fontFamily: "Courier Prime, Courier New, ui-monospace, monospace"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1.4
rounded:
  sm: "8px"
  md: "9px"
  lg: "12px"
  sheet: "18px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  tap: "44px"
components:
  button-primary:
    backgroundColor: "{colors.tomato}"
    textColor: "{colors.on-tomato}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    height: "44px"
    padding: "0 16px"
  button-done:
    backgroundColor: "{colors.herb}"
    textColor: "{colors.on-herb}"
    rounded: "{rounded.md}"
    height: "44px"
  button-default:
    backgroundColor: "{colors.card-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    height: "44px"
  chip:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    height: "36px"
    padding: "0 14px"
  chip-on:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  meal-card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
  input:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    height: "44px"
    padding: "10px 12px"
  index-card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink}"
    padding: "18px 20px 8px"
  tab-bar:
    backgroundColor: "{colors.card}"
    textColor: "{colors.ink-2}"
    height: "62px"
---

# Design System: Meal & Grocery Planner

## Overview

**Creative North Star: "The Recipe Card"**

Everything is a card you could hold. Cream index-card stock sits on a warm paper ground; at night the ground goes charcoal and the cards warm grey. Tomato red is the brand and every primary action; herb green only ever means done, in the pantry, in the cart. The food photo leads each card, a serif name sits under it, and measured amounts are typed in Courier Prime like a card from a recipe box.

The user is one cook with a phone, sometimes with messy hands, in a kitchen or a store. Density is moderate, tap targets are 44px or more, and the UI never makes a screen of rows: a day is a short stack of meal cards, a store is one list on one card. Light or dark follows the phone; there is no toggle.

The signature move is the recipe sheet's index card: a 2px tomato rule under the serif title, and ingredients typed in Courier Prime on faint blue rules.

**Key Characteristics:**
- Warm paper and cream card, never white or grey
- One action colour (tomato), one status colour (herb); amber is a quiet warning only
- Young Serif for names and headings, system UI for reading, Courier Prime for quantities
- Photos carry the cards; a tomato-tint serif initial stands in when there is none
- Drawn 1.75px-stroke 24px icons, no emoji or glyph icons
- Surfaces separate by soft warm shadow and tonal steps, not by borders

## Colors

A warm, food-coloured palette: cream and paper neutrals, a single tomato accent, herb green as the "done" signal. Values live in the frontmatter (light) with `-dark` twins used under `prefers-color-scheme: dark`.

### Primary
- **Tomato** (`tomato`): primary buttons, selected day chip, active tab rule, cook-mode progress bar, favourite and rating marks. Tomato text on a light surface uses **Tomato Ink** (`tomato-ink`) for contrast; **Tomato Soft** (`tomato-soft`) is its quiet fill for tags, time chips, placeholder photos and the pick banner.

### Secondary
- **Herb** (`herb`): done and stocked states only: the green Cook-again button, ticked boxes, shopping progress, "in pantry" text (`herb-ink`), swipe-to-put-away. **Herb Soft** fills done chips and tags.

### Tertiary
- **Amber** (`amber`, `amber-soft`): offline pill, expiring-soon cards, warning note cards. Never a button colour.

### Neutral
- **Paper** (`paper`) page ground; **Card** (`card`) cream card stock; **Card 2** (`card-2`) default button, note and nested fills; **Sunk** (`sunk`) segmented-control trough, photo wells, progress track.
- **Line** / **Line 2**: hairline separators and input strokes. **Ink**, **Ink 2**, **Ink 3**: text, secondary text, hints.
- **Rule** (`rule`): faint blue, used only for the ruled lines under ingredients (recipe sheet and cook-mode ingredient list).

### Named Rules
**The Red Means Do Rule.** Tomato marks what to tap or what you chose; green marks what is finished. A screen never uses green for a button the user hasn't done yet, or tomato for a finished state.
**The Cream Not White Rule.** No pure white or black on the page. Text on photos sits on a cream pill (`rgb(255 251 244 / .94)`), never bare.

## Typography

**Display / Heading Font:** Young Serif (with Iowan Old Style, Palatino Linotype, Georgia)
**Body Font:** system UI (system-ui, -apple-system, Segoe UI, Roboto)
**Amount Font:** Courier Prime (400, 700; Courier New fallback)

**Character:** A warm cookbook serif for names, plain system text for everything read quickly, and a typewriter face reserved for quantities and timers so numbers read as measured.

### Hierarchy
- **Display** (400, 30px, 1.1): tab titles in the sticky bar.
- **Headline** (400, 24-27px, 1.18-1.2): recipe sheet title (27px), focused meal name (24px), cook-mode headings.
- **Title** (400, 19px, 1.22): meal card names (19px), sheet titles (23px), recipe grid names (16.5px), section headings (17-24px).
- **Body** (400, 16px, 1.45): all reading text; inputs are 16px to stop mobile zoom. Step text is capped at 68ch; cook-mode steps scale `clamp(22px, 5.6vw, 30px)` at 34ch.
- **Label** (600, 14-15px): buttons, tags, field labels, segmented controls; tab-bar labels 12.5px.
- **Amount** (Courier Prime 700, 15-19px): ingredient and list quantities, stepper values, timers. Tabular numerals are on for the whole body.

### Named Rules
**The Typed Amounts Rule.** Courier Prime is for measured amounts and timers only. Never for names, prose or labels.
**The Serif For Names Rule.** Anything the user would call a dish, a day, a store or a section is Young Serif; actions and metadata are system UI.

## Layout

Phone first. One column, `max-width: 680px`, 16px side gutters, centred; sheets cap at 600px. A sticky per-tab header holds the serif title and the tab's controls; a fixed bottom tab bar (62px plus safe-area) carries four tabs: Plan, Recipes, Shop, Pantry. Body padding keeps content clear of the bar.

Spacing is a small hand-set ladder: 4, 8, 12, 16, 20px; cards stack with 14px gaps. Plan opens on a 7-day strip (weekday, serif date number, up to three status dots), then the selected day's meal cards. Recipes is a two-column photo grid (three from 560px). Shop and Pantry are single cards of rows grouped under serif store and aisle headings. Cook mode is a full-screen layer with its own top bar, progress line, scrolling main and a bottom Back/Next bar.

Every frequent action is reachable by thumb: 44px minimum targets, 56px big buttons, swipe on list rows past 84px to commit. Above 700px sheets become centred dialogs; the layout otherwise stays the phone column.

## Elevation & Depth

Soft and warm: depth comes from tonal steps (paper, card, card-2, sunk) plus two warm-tinted shadows. Borders are mostly avoided; separation is a 1.5px inset stroke on inputs and outline buttons, hairlines between list rows, and a header hairline that appears on scroll.

### Shadow Vocabulary
- **Card** (`0 1px 2px rgb(74 48 22 / .07), 0 4px 12px rgb(74 48 22 / .07)`): meal cards, recipe cards, lists, tool tiles, the selected segment. Dark mode uses black at .3 and .22.
- **Overlay** (`0 2px 8px rgb(74 48 22 / .12), 0 18px 40px rgb(74 48 22 / .18)`): sheets, toast, timers, scanner card.
- The selected day chip carries a tomato-tinted lift; the scrim is `rgb(30 20 12 / .42)`.

### Named Rules
**The Flat Until Held Rule.** Cards rest on the soft Card shadow; only things that float over content (sheet, toast, timer pill) use the Overlay shadow. Empty meal slots are an inset outline with no shadow.

## Shapes

Gently rounded, never sharp, never pill-for-everything. Cards 12px, buttons and inputs 9px, photo thumbs 10px, nested notes 8-10px, sheets 18px at the top (all four corners above 700px). Pills (999px) are reserved for chips, tags, steppers, the offline badge and timers. Circles are for icon buttons and tick boxes. The meal card's photo is a rounded square inset in the card (92px) in the list view and full-bleed 16:9 for the focused meal.

## Components

### Buttons
- **Shape:** 9px radius, 44px tall, 600-weight 15px label, 8px icon gap; press scales to .97.
- **Primary:** tomato fill, cream text. **Herb** is the done action (Cook again). **Default** is card-2 fill; **line** is a 1.5px inset stroke; **quiet** is transparent; **danger** is tomato-ink text. **Big** is 56px; **small** is 36px.
- Round icon buttons (44px circle) come in quiet, line, tinted and primary. Disabled drops to 45% opacity.

### Meal card
Cream card, 12px radius. Photo (inset 92px, or full-width 16:9 for the focused meal) with a cream slot pill ("Dinner") over the corner; serif name; meta line with 16px icons (pantry match in herb, kcal, cost); optional note strip in card-2; action row with Cook primary (wider), Swap and More. Done meals show a herb "Cooked" chip and a slightly desaturated photo. Empty slots are a transparent card with an inset outline and choose/generate buttons.

### Recipe card (grid)
Photo at 4:3, serif name at 16.5px, then a small meta row (time, rating and favourite in tomato, pantry match in herb).

### Chips and segmented controls
Chips are 36px pills on card with a 1.5px inset line; selected inverts to ink on paper. The segmented control is a sunk trough with a raised card segment for the selected one; counts sit beside labels. Both scroll sideways without scrollbars when they overflow, with a 56px fade on the right until scrolled to the end. Small buttons, chips and segments keep their drawn size but carry an `::after` hit area that brings the tap target to 44px; nothing on screen is set below 13px except the Shop badge count.

### Inputs
Card fill, 1.5px inset stroke in line-2, 9px radius, 44px minimum height; focus swaps the stroke for a 2px tomato one. Placeholders use ink-3. Search has a drawn icon inside the left edge. Checkboxes are herb. Fields carry a 14px/600 label above.

### Navigation
Bottom tab bar on card with a top hairline: four drawn 25px icons with 12.5px labels; the active tab turns tomato-ink with a 32px tomato tab-edge at the top; a tomato count badge sits on Shop. The sticky header carries the tab title and tools; the seven-day strip is Plan's secondary navigation.

### Sheets, toast and timers
Bottom sheets slide up with a grab handle, serif title, scrolling body and a footer action bar (primary takes 1.5x width). The toast is an ink pill with cream text and one optional action (undo), above the tab bar. Cook timers float as ink pills with Courier minutes; a ringing timer turns tomato and pulses. All motion uses one ease (`cubic-bezier(.16, 1, .3, 1)`), 0.15-0.35s, and collapses under reduced motion.

### Swipe rows (Shop, Pantry)
A tap area with a 28px round tick box (herb when in the cart), the item name and a Courier quantity. Swiping right reveals a herb "put away" action and swiping left a tomato "remove" action, committing past 84px with a haptic tick. Ticking never waits on the network.

### Index card (signature)
The recipe sheet body: full-width hero photo, then a cream panel whose serif title (27px) rests on a 2px tomato rule. Ingredients are a list on faint blue rules (`rule`, 1px) with the quantity typed in Courier Prime 700 in an 8.5ch column, the name beside it, and a tomato-soft "need" pill when it isn't in the pantry. Steps use serif tomato-ink numerals. Cook mode reuses the ruled list with 28px round tick boxes.

## Do's and Don'ts

### Do:
- **Do** put the food photo first on any card that has one; fall back to a tomato-soft tile with the serif initial.
- **Do** use tomato for actions and selection, herb for done, in the pantry and in the cart, and amber only for warnings.
- **Do** set quantities in Courier Prime and names in Young Serif.
- **Do** keep every tap target at 44px or more and give destructive swipes an undo toast.
- **Do** use the drawn icon set (`ICONS` in core.js, 24px viewBox, 1.75px round stroke, `currentColor`).
- **Do** define every new colour as a light and a dark token pair on `:root`.

### Don't:
- **Don't** use pure white, pure black or cool greys on the page; the ground is paper.
- **Don't** use green for a button the user hasn't acted on, or red for a finished state.
- **Don't** use Courier Prime for prose or labels.
- **Don't** add gingham, stickers, handwriting fonts or decorative borders around cards.
- **Don't** put bare text on photos; use the cream slot pill.
- **Don't** use emoji or glyph characters as icons.
- **Don't** build a seven-day grid of rows with inline inputs; one day at a time, one card per meal.

### Not canonized
Defects the build carries, not rules for new surfaces: the Google Fonts stylesheet loads from the network with only the system stack as fallback; the scanner overlay uses literal black and its own 3px cream frame; `.slot-tag` and `.on-photo` hard-code `#2a2019` and a cream rgba instead of tokens.
