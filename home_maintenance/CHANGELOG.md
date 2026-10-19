# Changelog

## 0.3.0

The phone web page.

- Tabs for Tasks, Appliances, Shutoffs and Toner, built for a phone. Tasks show OK / Due soon / Overdue, with Done (date, note, parts, cost), Snooze, History, Edit and Delete.
- Appliances show warranty and lifespan badges, with receipts and photos added from the camera or the gallery. Photos are shrunk on the phone before they are uploaded to your bucket.
- Shutoffs with where-to-find-it notes and photos.
- Toner: pick the sensors from a list of your Home Assistant sensors, set the alert level and printer model, and see each sensor's level, including unavailable ones.
- Download the calendar (.ics) and send a test reminder from the Toner tab.

## 0.2.0

Backend only; the phone web page is still a placeholder.

- Status per task: ok, soon (due within 7 days) or overdue.
- Seasonal tasks: a task only comes due in its active months (the Gutters preset is October to November) and sleeps until the season starts.
- Spreading: a new or just-completed task may shift a few days (at most 10% of its interval, 14 days) so the year's jobs do not land in the same week.
- Completions also log the parts used (for example the filter size), for reordering.
- A Monday summary notification: overdue, due this week and what is coming up.
- Home Assistant entities: sensor.home_maintenance_due (number of tasks due, with their names), one inary_sensor per task (on = due) and a home_maintenance_task_due event, for dashboards and automations.
- Calendar export (.ics) of due dates and warranty end dates.
- Appliance and warranty register with expected lifespan (aging and past-lifespan flags), tasks linkable to an appliance, and a reminder 30 days before a warranty ends.
- Emergency shutoffs list (water, gas, electric) with locations.
- Receipt and photo files for appliances and shutoffs, stored in your S3-compatible bucket (set the s3_* options); only the file details are kept on the Green.

## 0.1.0

First version (backend).

- Recurring maintenance tasks with an interval in days or months, last done and next due. Starts with presets: HVAC filter, smoke/CO detector batteries, water heater flush, fridge water filter, dishwasher/washer clean, gutters.
- A daily phone reminder for tasks that are due, with Done / Snooze buttons. Done resets the clock and logs the date, an optional note and cost.
- Printer toner alerts: watches the toner sensors you choose, and when one drops below the threshold (default 15%) sends a phone notification and adds the cartridge to the shopping list. Unavailable sensors are skipped and shown as unavailable.
- Works only through Home Assistant; nothing is exposed on your network. The database is kept in the add-on's own config folder.
