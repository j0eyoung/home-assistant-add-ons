# Changelog

## 0.5.3 - Shorter Road Alerts, Tidier Tabs

### 🌟 Features
* **Road alerts are one line each.** "I-70, Exit 190 Vail Pass Summit to Exit 180 East Vail: two left lanes closed (road construction), today 12am to tomorrow 12am." Closures happening now come first, then ones starting within 24 hours; later ones are just counted. The same closure on several days is one line with the days listed.

### 🔧 Improvements
* **Only roads on your drives show up.** Closures on other roads (Aurora, Commerce City, CO-57 and so on) no longer appear, and I-70 only counts between Denver and Vail Pass.
* **Garmin connect moved to Settings.**
* **Removed the Learning to ski tab.** The ski-day option on the Plan tab (favours green and blue runs) and your ski stats on the Season log tab are still there.
* The CDOT travel-time line is hidden while it only has empty readings.

## 0.5.2 - Radar Map: CARTO Key

### 🌟 Features
* **A "CARTO map key" option in the Configuration tab.** CARTO's free basemap needs a key (free at carto.com/basemaps/apikey). With one, the Radar tab uses CARTO's map, light or dark to match your theme.

### 🐞 Fixes
* **The radar map no longer depends on OpenStreetMap blocking you.** Without a CARTO key the map goes back to OpenStreetMap and now sends the page's origin with each tile request, which is what OpenStreetMap asks for. The CARTO map tried in 0.5.1 had no key, so it showed an "API KEY REQUIRED" watermark.

## 0.5.1 - Radar Map Fix (replaced in 0.5.2)

### 🐞 Fixes
* Tried CARTO's free map for the Radar tab to get around "Access blocked" squares from OpenStreetMap. It shows an "API KEY REQUIRED" watermark, so 0.5.2 goes back to OpenStreetMap.

## 0.5.0 - Weekend Outlook, Storm Trends, Model Accuracy, Packing List

### 🌟 Features
* **Thursday weekend outlook.** At 6pm Thursday your phone gets the best weekend day and resort, when to leave, and a reminder to book a parking reservation where one is needed (A-Basin's weekend reservations start January 2, with a button to book). Turn it off or change the time in Settings.
* **Storm trending up alerts.** When a resort's next-5-day snow total jumps by 3 inches or more since earlier in the day and ECMWF and GFS agree, you get a heads-up before it becomes a powder alert.
* **The forecast learns which model is right.** Every evening each model's forecast for tomorrow is saved, then checked against what the resort's SNOTEL station measured. Once both models have 5 wet days, the blend leans toward the one that has been closer at that resort. The scores show on each resort page.
* **"I'm going" packing list.** A button on the Plan tab and each resort page adds the day's gear (layers, goggles lens, hand warmers, board or skis) to a Home Assistant to-do list. On a powder morning it does it for you. Pick the list in Settings, or it uses the shopping list.
* **Season stats from Garmin** on the Season log tab: days, board and ski days, vertical, top speed, distance and hours, this season against last season to the same date, plus a chart of your top speed on skis while you learn.
* **Live webcam pictures** on the resort pages for Winter Park, Copper, Arapahoe Basin and Aspen Snowmass.

### 🔧 Improvements
* The first Garmin sync goes back to the start of last season so the stats can compare the two.
* Pushing the add-on now commits only its own folder, so it never picks up another add-on's unfinished work.

## 0.4.3 - Shared Secrets

### 🔧 Improvements
* Blank options (the Claude token and the COtrip key) are filled from `/config/addon_secrets.json` on the Green, the same file the other add-ons use. A value typed in the Configuration tab always wins.

## 0.4.1 - Icon and Daily Snow Fix

### 🌟 Features
* **A new icon and logo**, and the same icon in the browser tab.

### 🐞 Fixes
* **The Daily Snow could fail to save.** It now handles Claude's reply and errors properly, including a sign-in that has expired.

## 0.4.0 - Claude Code, Garmin, Live Traffic

### 🌟 Features
* **Forecast dashboard like OpenSnow.** Up to 15 days of snow for every resort at base, mid-mountain and summit, from ECMWF and GFS, with last 5 days, next 5, days 6-10 and 11-15 totals and a daily snow bar for each. Snow comes from each elevation's temperature and humidity (so rain at the base shows up), not the model's own snowfall.
* **Resort pages.** Per resort: daily and hourly snow, temperature and wind, a model comparison chart, freezing level, the resort's reported base, new snow, lifts and terrain open, and SNOTEL depth.
* **Radar tab** with a moving NEXRAD radar and a snow forecast pin on each resort.
* **Daily Snow and Ask Claude run on your Claude subscription** through Claude Code, with no API fees. Connect it once in Settings (same sign-in as the Workout Tracker). Fresh Daily Snow is written each morning from 5:30am.
* **Garmin import.** Every Ski or Snowboard activity you record becomes a day in the Season log, matched to the nearest resort, with vertical and board or skis. It reuses the Workout Tracker's Garmin login when that's in the shared config folder; otherwise sign in once on the Season log tab. A day you delete stays deleted, and one tap flips a day between board and skis.
* **Live traffic.** Waze Travel Time sensors from Home Assistant are matched to resorts by name (or pick them in Settings), and a free COtrip key from manage-api.cotrip.org adds CDOT incidents, road conditions and closures on your routes. Both show on the Plan tab and resort pages.

### 🔧 Improvements
* The Pass tab is gone.
* Fresh snow for a ski day no longer counts snow that falls after you've left.

## 0.3.0 - Leave Times That Beat I-70 Traffic

### 🌟 Features
* **Leave times aimed at beating the rush.** On weekends and ski holidays the leave time is set so you're on I-70 by 6:00am (5:30am on powder days), with what 7:00am would cost instead and the best times to head home.
* **Ski holidays count as peak days** for traffic and crowds: Thanksgiving, Dec 20 to Jan 3, MLK Day and Presidents Day.

## 0.2.0 - Season Log, Gear, Notifications

### 🌟 Features
* **Season log, learning-to-ski log and gear upkeep** (wax and tune reminders by days on snow, for board and skis separately).
* **Departure points** for drive times, shuttle and transit links for each resort, and a gear and clothing call from the day's temperature, wind and snow.
* **Home Assistant tie-ins:** powder alerts and a powder-morning wake-up (lights and a speaker announcement), thermostat set back to normal when you leave the mountain, boot and glove drying reminder, shopping-list adds, and `sensor.ski_best_today` and `sensor.ski_days_this_season`.

## 0.1.0 - First Release

### 🌟 Features
* **Forecasts and best-day ranking** for Winter Park, Steamboat, Copper, Eldora, Arapahoe Basin, Aspen Snowmass and Keystone, from Open-Meteo snow forecasts by elevation, SNOTEL snowpack and live lift status where the resort publishes it.
