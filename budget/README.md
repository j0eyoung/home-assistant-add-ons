# Budget

Home Assistant add-on: personal budgeting with SimpleFIN bank sync and Claude Code AI (categorization, questions, monthly reviews). Runs on a Home Assistant Green.

## Install

Add the repository `https://github.com/j0eyoung/home-assistant-add-ons` (Settings → Add-ons → Add-on Store → ⋮ → Repositories), install **Budget**, start it and turn on **Show in sidebar**. Then open Budget → Accounts:

- paste a setup token from [bridge.simplefin.org](https://bridge.simplefin.org) and click Connect;
- click **Connect Claude**, open the link, approve, paste the code back;
- add a manual account for anything SimpleFIN can't reach (e.g. a mortgage servicer);
- optionally, fill in older history with **Import from your bank** (below).

Coming from an older Budget install (the separate `budget` repo): the database doesn't carry over by itself. Copy the old add-on's newest `budget-YYYY-MM-DD.db` from `/addon_configs/<old id>_budget/backups` into this add-on's `backups` folder, then restore it from Accounts → Backups. Reconnect SimpleFIN and Claude.

## What it does

- **Safe to spend this week** (top of the dashboard): the plan's monthly spending limit minus your regular bills (mortgage, utilities, insurance, subscriptions), as a weekly amount, with what's left this week and per day. Bills and loan payments don't count against it; gas, groceries and other day-to-day spending do.
- **Dashboard**: today's check ("anything to flag?"), spend vs budget with last-month comparison, tracked categories with running totals, monthly cash flow, net worth.
- **Transactions**: AI categories, merchant rules, notes, and splits (one Costco trip into groceries + pharmacy). **receipt** takes a photo of the receipt; Claude groups the items by category and the split editor opens prefilled for you to confirm. The photo isn't stored.
- **Budget**: monthly targets, 3-month averages, one-click fill from averages.
- **Recurring**: detected bills and subscriptions, monthly total, price increases, ones that may have stopped. Change how often, mark one as not recurring (with undo), or add a missed one with **recurring** on its transaction.
- **Debt**: current payoff pace per account, promo rates (e.g. 0% until a date), and avalanche vs snowball vs your plan's order with extra payments. Warns when an order wouldn't clear a promo balance in time.
- **Plan**: your debt payoff and savings plan, built around one number: the most you can spend each month and still make every payoff date (a 0% promo's end included). A spending slider shows each debt's payoff date as you drag, with last month and the 3-month average as reference points. Target dates are set right in the list. **Edit plan** covers income (paychecks, bonuses, raises, side income), one-off and monthly changes, savings goals with cost items, and **Import a written plan**, which reads a plan (e.g. a handoff from another AI chat) into the editor through Claude for you to check before saving. Plan vs actual compares each month with the plan, and it flags new charges on the card you're paying off.
- **Import from your bank** (Accounts tab): bank sync only reaches back about 90 days. Download older history from the bank's website as QFX/OFX ("Quicken") or CSV, several files at once. The account is matched by its last 4 digits, and debit/credit signs are checked against transactions already in the app. Rows bank sync already has, and anything imported before, are skipped, with a preview of the counts before anything is saved.
- **Health**: warns when an account stops updating or a sync fails.
- **Backups** (Accounts tab): the database is copied nightly to the add-on's config folder (`/addon_configs/<id>_budget/backups`, last 7 kept; empty databases are never backed up). A new install restores the newest backup on its own when it starts with no data, and the Backups section can restore any backup by hand (what's replaced is saved as `before-restore.db`). To move data from another install, copy its newest `budget-YYYY-MM-DD.db` into that folder and restore it. The SimpleFIN connection and Claude sign-in are not backed up; reconnect them after a reinstall.

## Options

| Option | Purpose |
|---|---|
| `simplefin_setup_token` | Alternative to pasting the token in the UI; claimed once on start |
| `claude_code_oauth_token` | Fallback sign-in from `claude setup-token`; the in-app login is preferred |
| `claude_model` | `haiku`, `sonnet` (default) or `opus` |
| `api_token` | Required for requests that don't come through HA ingress (other add-ons, Claude Code on a PC). Enable the port under Network first. |

## For other add-ons

Send `Authorization: Bearer <api_token>` (not needed through ingress).

- `GET /api/summary`: net worth, this month's spend vs budget, over-budget categories, balances, recent charges, bills due in the next 7 days, connection issues, today's briefing text, the plan (debt-free date, next milestones, the card being paid off, warnings), and this week's safe-to-spend.
- `GET /api/briefing?generate=1`: today's "anything to flag?" text (generated through Claude if it hasn't been yet today) plus the data behind it.

## Development

See [CLAUDE.md](CLAUDE.md). Run from this folder with `npm run build && npm start`.
