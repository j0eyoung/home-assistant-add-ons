# Budget app

Personal budgeting app: Node 24 server (TypeScript run directly, no build step) + React/Vite frontend + SQLite (`node:sqlite`). Bank data comes from SimpleFIN Bridge (one `/accounts` poll a day; ~24 requests/day allowed); manual accounts and CSV import cover institutions it can't reach. A Plan tab projects a debt payoff and savings plan month by month. AI features (categorization, Q&A, daily briefing, monthly insights, receipt reading, plan import) run through the Claude Code CLI (`claude -p`, no tools) on the user's subscription, with the sign-in stored under `data/claude`; see [server/claude.ts](server/claude.ts). Packaged as a Home Assistant add-on: the repo root holds `repository.json`; this `budget/` folder is the add-on (`config.yaml` + `Dockerfile` + `icon.png`/`logo.png`). All commands below run from `budget/`.

## Commands

- `npm run build` then `npm start`: serve the app at http://127.0.0.1:8099
- `npm run dev:server` + `npm run dev:web`: watch mode (Vite proxies `/api` to the server)
- `npm run typecheck` (slow on this PC, ~50s)
- `python scripts/make_icon.py`: redraw `icon.png`/`logo.png` after changing `web/public/icon.svg`

## Constraints

- Server code must stay erasable-syntax-only TypeScript (no enums, no parameter properties) and import with `.ts` extensions, because Node runs it directly.
- Frontend URLs must stay relative (`api/...`, `./icon.svg`, Vite `base: './'`) so the app works behind Home Assistant ingress.
- Any total or per-category figure must read the `ledger` view, not `transactions`, or split transactions get counted wrong.
- The SimpleFIN access URL (it embeds credentials) lives in `data/secrets.db`, never in `budget.db`, and is not backed up. Never read, print or copy `data/secrets.db` or `.env`, and never ask the user to paste a setup token or access URL into chat; it goes in the Accounts tab or the add-on options.
- Target hardware is a Home Assistant Green (ARM, 4 GB, eMMC): keep dependencies light and avoid chatty disk writes.
- `GET /api/summary` and `GET /api/briefing` are the contract for the Daily Briefing add-on; only add fields, never rename or remove.
- The Claude CLI never gets tools or file access. Receipt photos go in as a stream-json image block (`askClaudeWithImage`), are resized in the browser first, and are never stored.
- Schema changes go through `addColumn` in [server/db.ts](server/db.ts) so existing databases (and restored backups) migrate on start.
- [shared/payoff.ts](shared/payoff.ts) (debt payoff math) and [shared/plan-math.ts](shared/plan-math.ts) (the Plan's month-by-month projection and spending limit) are imported by both the server and the browser (the Plan tab's spending slider reruns the projection live), so they stay plain TypeScript with no Node or DOM imports.
- Bank-file imports (`POST /api/accounts/:id/import`, parsed in [web/src/importParse.ts](web/src/importParse.ts)) skip rows on or after a synced account's first SimpleFIN date and rows whose date+amount the account already has. Because imports can reach further back for some accounts than others, averages start at `historyStart()` in [server/queries.ts](server/queries.ts), not at the earliest transaction.
- Every add-on version bump needs a `CHANGELOG.md` entry (newest first, plain words for the user).
- AI categorization failures must stay visible: `GET /api/status` adds a "Needs attention" issue when transactions are waiting and Claude isn't connected or the last run failed (`meta.ai_error`), and starts a background run once Claude is connected.
- Restoring a backup (`restoreBackup` in [server/db.ts](server/db.ts)) copies table by table through ATTACH, never by replacing the file, because the server holds open connections to `budget.db`. When adding a table, add it to `DATA_TABLES` there.
- Weekly safe-to-spend ([server/allowance.ts](server/allowance.ts)) is the plan's limit (the tighter of the deadline ceiling and planned spending) minus detected recurring bills, leaving out Debt Payments and the everyday `HABIT_CATEGORIES`, which count against the week.
- The review queue is `NEEDS_REVIEW` in [server/db.ts](server/db.ts): posted transactions from the last `REVIEW_DAYS` (60) with `category_source` ai or none and `reviewed = 0`. Any category the user sets (one, bulk, split, receipt) sets `reviewed = 1`; "Re-run AI categories" resets only unreviewed AI picks. The window keeps old history (imports, restored backups without the column) out of the queue, so no migration marks old rows. [web/src/Transactions.tsx](web/src/Transactions.tsx) mirrors the test in `needsReview()`.
- AI categorization sends up to 80 of the user's own merchant → category choices (hand-set, or confirmed AI picks) as examples; keep that list short, it goes into every batch prompt.
- Visual system: [DESIGN.md](DESIGN.md) ("Guide Sign", product context in [PRODUCT.md](PRODUCT.md)). Sign green is the shell and the dashboard's one sign; sign yellow means over budget and nothing else; service blue is information; construction orange is warnings; stop red is errors. Overpass is self-hosted through @fontsource (no external font requests). Icons come only from [web/src/Icon.tsx](web/src/Icon.tsx), never text glyphs.
- UI: never cut text off in tables or lists (no ellipsis, no fixed column widths); text wraps, short values stay on one line. Phones (≤640px) restack the Transactions, Debt and Plan goals tables with CSS grid, so check new tables at 375px wide. Inline panels under a row replace `window.confirm`/`prompt`. An effect callback must not return a value: newer browsers return a promise from `scrollIntoView`, and React then calls it as a cleanup.
- The Plan ([server/plan.ts](server/plan.ts)) projects from real balances and the income schedule; "spending" there means expense categories except Debt Payments and Interest, because loan payments and interest are modeled as debts. Keep that definition the same in the projection, the actual average, plan vs actual and weekly safe-to-spend; Interest also stays out of the "new charges on the card you're paying off" warning.
- Until payday ([server/forecast.ts](server/forecast.ts)): the account is `meta.forecast_account` or the depository account with the most income deposits in 90 days; payday is `nextPayday()` in [shared/plan-math.ts](shared/plan-math.ts) from the plan's income (saved or detected). It takes off recurring bills whose latest charge was on that account (every time they come up before payday; a bill up to 3 days late counts today), card and loan payments from `cardsDue()` that aren't paid yet (last payment amount, else the minimum; a Debt Payments bill near the same date and amount is dropped so a loan isn't counted twice), and everyday spending (the account's expense charges over 60 days, without Debt Payments, Interest and recurring merchants) per day from tomorrow. The warning (`meta.forecast_low`, default 200) goes to `/api/status` issues and `summary.forecast`, never `summary.issues`.
- Due dates (`cardsDue()` in [server/debts.ts](server/debts.ts)): `accounts.due_day` (1-31, a shorter month's last day) and `autopay`. A payment is a transfer-kind ledger amount < 0 on the account, pending included; a payment on a due date counts for that date. Missed: more than 2 days past the last due date with no payment since the one before (status unknown when history doesn't reach back that far or the account has no transactions). Due soon: autopay off, next due date within 5 days, no payment since the last one. Messages go to `/api/status` issues, `summary.cardsDue` and the briefing.
- Category kind `reimbursable` (the seeded Reimbursable category; `reimbursableId()` in [server/db.ts](server/db.ts)) counts as none of spending, income, savings or debt payments, so every `kind = 'expense'`/`'income'` total leaves it out without special cases; keep it that way when adding totals. The AI never gets it as a choice or as an example. `transactions.repaid_by` holds the deposit id (or `'manual'`) on a paid-back charge; matching puts the deposit in Reimbursable too, and undoing the last charge on a deposit sends it back to Other with `category_source` none. See [server/reimburse.ts](server/reimburse.ts).
- The Year tab and CSV export are [server/year.ts](server/year.ts). The current year is compared with the same months of last year. The CSV reads `ledger` and writes amounts bank style (money out negative, the opposite of the app), with a BOM so Excel reads it as UTF-8.
- Reconnecting a bank at bridge.simplefin.org gives its accounts new ids, so each shows twice. `replacements()` in [server/merge.ts](server/merge.ts) pairs an old copy with the newer account of the same institution and name; the Accounts tab and "Needs attention" offer to merge (`mergeAccount`): it fetches the new account's 90 days, moves older transactions over, keeps overlapping ones (same amount within 3 days) once with the user's category/split/note, moves balance history, debt terms and plan goals, records the old id in `meta.merged_accounts` so syncs skip it, and saves `before-merge.db` first. Any account that first appears on a later sync gets its last 90 days fetched (`backfillAccounts`), since the resync window is only 7 days.

## Analyzing the user's finances

When asked to analyze spending, debts, trends or anything about the data, query it read-only:

```
node scripts/query.mjs "SELECT c.name, ROUND(SUM(l.amount), 2) AS spent FROM ledger l JOIN categories c ON c.id = l.category_id WHERE c.kind = 'expense' AND substr(l.date, 1, 7) = '2026-10' GROUP BY c.id ORDER BY spent DESC"
```

The app must be running. For an instance on Home Assistant set `BUDGET_URL` and `BUDGET_TOKEN`.

Schema:

- `ledger` (view): `transactions` with each split transaction replaced by its parts. Same columns plus `transaction_id`. Use it for all totals.
- `transactions(id, account_id, date, name, merchant, amount, pending, category_id, category_source, reviewed, notes, repaid_by)`: amount > 0 is money out, amount < 0 is money in. category_source none means only the default 'Other' was applied; user means set by hand or split. reviewed 1 = the user has looked at the category (see the review queue). repaid_by: on a Reimbursable charge, the deposit that paid it back or 'manual'; null = still owed.
- `splits(id, transaction_id, amount, category_id)`: parts of a split; same sign as the parent and they sum to its amount.
- `accounts(id, source, org_name, name, type, balance, available, currency, balance_date, apr, min_payment, in_plan, promo_apr, promo_end, due_day, autopay)`: source is simplefin | manual; type is depository | credit | loan | investment | other. `balance` is signed: negative = owed. apr/min_payment/in_plan/promo_* feed the Debt and Plan tabs; promo_apr applies until promo_end. due_day/autopay feed the due-date warnings.
- `categories(id, name, kind, track)`: kind is expense | income | savings | transfer | reimbursable; only expense counts as spending, and reimbursable (charges someone pays back, and the deposits that repay them) counts as nothing. track = running-total card on the dashboard.
- `budgets(category_id, amount)`: monthly target.
- `balance_snapshots(date, account_id, balance)`: daily signed balances, for net worth over time.
- `recurring_overrides(merchant_key, label, status, cadence)`: the user's corrections to recurring detection; status yes (confirmed, cadence optional) or no (hidden). merchant_key is the normalized merchant from [server/recurring.ts](server/recurring.ts).
- `rules(pattern, category_id)`, `insights(month, content, created_at)`, `meta(key, value)` (last_sync, last_sync_errors, last_sync_failure, last_backup, briefing, plan, merged_accounts, forecast_account, forecast_low).
- `meta.plan`: the payoff-and-savings plan as JSON (`json_extract` works): income {paycheck, schedule, lastPayday, bonuses[] {month 1-12, amount}, side, raises[] {month, paycheck}}, spending (planned monthly, null = actual average), events[] {month, label, amount, monthly}, goals[] in order {kind debt|savings, name, accountId, target, by, items[]}. Absent until the user saves one.

Describe what the data shows; do not give personalized investment advice.
