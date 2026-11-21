# Changelog

## 0.6.1 - Merge Reconnected Accounts, Interest Category

### 🌟 Features
* **Merge an account into its replacement.** Reconnecting a bank at SimpleFIN gives its accounts new ids, so each one showed twice and the old copy stopped updating. Accounts now spots the old copy and offers **Merge into it**: its older transactions, balance history, debt settings and plan goals move to the new account, and charges both copies have are kept once with your categories, splits and notes. A copy of everything is saved first as before-merge.db.
* **Interest** category for interest and finance charges on cards and loans, picked automatically for charges like "INTEREST CHARGE ON PURCHASES". Like loan payments, it stays out of the Plan's spending and the weekly safe-to-spend, because the Plan already counts interest on your debts.

### 🔧 Improvements
* A newly connected or reconnected account now brings in its last 90 days of history instead of only the last week.
* "Needs attention" says when an account shows twice because of a reconnect, and the Delete prompt points to Merge instead.
* Accounts shows how many transactions each account has.

### 🐞 Fixes
* An American Express Blue Cash card connected from now on is set up as a credit card instead of a bank account.

If you already deleted an old copy, restore last night's backup in Accounts → Backups, click **Sync now**, then merge.

## 0.6.0 - Review New Charges, Better on Your Phone

### 🌟 Features
* **To review** (Transactions tab): charges from the last 60 days whose category is the AI's guess, one card each. Tap **Looks right**, pick another category, split it or add a receipt. **All look right** clears the rest at once. The Transactions tab and the dashboard show how many are waiting.
* **Fix it once.** After you change a category, the app asks "Always put this merchant in that category?" right under the charge, and says how many other charges it would move. No more OK/Cancel pop-ups.
* **Change several at once.** Tick transactions (in the queue or the full list) and move them all to a category from the bar at the bottom of the screen.
* **Claude learns from your fixes.** When it categorizes new charges, it now sees how you've categorized each merchant before.

### 🔧 Improvements
* **Built for the phone.** The tabs scroll sideways in one row, the dashboard shows two numbers per row, and transactions are stacked rows with a ⋯ button for note, split, receipt and recurring. Buttons are bigger on touch screens, and tapping a field no longer zooms the page on iPhone.
* Safe to spend is now the first thing on the dashboard, and headline numbers are in whole dollars.
* Spending by category lists what you've spent on this month; categories with nothing yet are behind **Show**.
* Notes and "mark as recurring" open right under the transaction instead of in a pop-up, and how often is picked from a list instead of typed.
* Text in tables wraps instead of being cut off with "…". The Plan's payoff list stacks on a phone.
* Cash flow shows the last six months on a phone so the labels fit.
* "Re-run AI categories" leaves alone the AI picks you've confirmed.

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
