# Changelog

## 0.5.7 - Tells You When Claude Isn't Connected

### 🔧 Improvements
* **"Needs attention" now says when transactions are waiting for a category because Claude isn't connected** (a new install or a reinstall has to be connected again in Accounts). It also shows when the AI step fails, with the reason, instead of silently leaving everything as Other.
* **Connecting Claude categorizes the waiting transactions on its own.** No need to click "Re-run AI categories" afterwards.

### 🐞 Fixes
* "Re-run AI categories" now tells you to connect Claude when it isn't, instead of doing nothing.

## 0.5.6 - Restore Backups, Weekly Safe-to-Spend, Import From Your Bank

### 🌟 Features
* **Backups in Accounts.** See the nightly backups, back up now, and restore any of them with one click (what you had before is saved as before-restore.db first). To move data from another install, copy its newest budget-YYYY-MM-DD.db into the backups folder shown there and restore it. A new install with no data also picks up the newest backup on its own.
* **Safe to spend this week** at the top of the dashboard: your plan's monthly spending limit minus regular bills (mortgage, utilities, insurance, subscriptions), as a weekly amount, with what's left this week and per day.
* **Import from your bank** (Accounts): download older history from your bank as QFX/OFX or CSV, several files at once. The account is matched by its last 4 digits, debit and credit signs are checked against transactions already in the app, and anything bank sync or an earlier import already has is skipped, with a preview before anything is saved.

### 🔧 Improvements
* The payoff card shows the most you can spend for each date instead of "not in 10 years".
* Bonuses can be set per month (for example a bigger February bonus) and are read from your deposits.

### 🐞 Fixes
* Saving a plan no longer clears a debt's APR or minimum when only some of its fields were sent.

## 0.5.5 - Moved to the Shared Add-ons Repository

### 🔧 Improvements
* Budget now lives in the shared home-assistant-add-ons repository and is built as a ready-made image. It fills blank options from the shared secrets file on the Green. It's a separate add-on from the old Budget, so it starts empty: reconnect SimpleFIN and Claude, then restore a backup or import your history.

## 0.5.0 - Payoff Plan

### 🌟 Features
* **Plan tab.** Debts and savings goals in order with target dates, the most you can spend each month and still make every date, a spending slider that updates the dates as you drag, income with raises and bonuses, plan vs actual, and an import that reads a written plan with Claude.
* **Debt tab** now handles promo rates (like 0% until a date) and warns when a payoff order wouldn't clear a promo balance in time.

## 0.4.0 - Receipts and Recurring Controls

### 🌟 Features
* Take a photo of a receipt and Claude splits the charge into categories for you to confirm.
* Change how often a bill repeats, mark something as not recurring (with undo), or add one that was missed.
