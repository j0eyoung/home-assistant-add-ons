# Changelog

## 0.2.1 - Always Round Up

### 🔧 Improvements
* **Timesheet hours always round up** to the next quarter hour per day, client and case (1 to 15 minutes is 0.25 h, 16 to 30 minutes is 0.5 h). This applies to the Week tab, the weekly summary and the CSV export.

## 0.2.0 - Laptop Link and Case Status

### 🌟 Features
* **Optional laptop link.** Set an API key and a port in the add-on's Network tab, and the `wt.py` script on your laptop can start and stop the timer, log time, add tasks and set a case status. Off until you set a port.
* **Case status.** A case number and a short status (40 characters at most) show on the Week tab.

## 0.1.0 - First Version

### 🌟 Features
* **Timer and manual time** by client and optional case number, with daily and weekly totals.
* **Tasks and follow-ups** with a due date, and phone reminders with Done and Snooze buttons.
* **Stop-time nudge** (default 17:30, Monday to Friday) if a timer is running or hours are below your target, and a **weekly summary** of hours per client.
* **Timesheet CSV** export and a phone-friendly page in the Home Assistant sidebar.
