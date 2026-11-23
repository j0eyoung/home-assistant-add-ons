# Changelog

## 0.11.0 - Learning to Ski

### 🌟 Features
* **A skis day goes by what's open today.** With "Skis day" ticked on the Plan tab, a quarter of the score is about learning: how many greens and blues are open today (groomed ones count most), how much of the mountain is green or blue, whether the snow is firm, the wind and the light. Early in the season that favours the resort with the most easy runs open, not the one with the most on paper. The Plan list shows each resort's open greens and blues under its name.
* **How the snow will feel.** The morning after a thaw and a hard freeze, the forecast warns of firm, icy snow, and says whether it softens by midday or stays firm. Thick cloud from 9am to 3pm is marked as flat light, with a reminder to bring a low-light lens. Both show on the Plan tab and in each resort's day-by-day table.
* **Learner view on the trail map.** One tick makes open groomed greens and blues stand out, fades the blacks and park, and zooms to where the easy runs are. The map remembers your choice, and it starts on when "Skis day" is ticked.

### 🔧 Improvements
* "Open right now" lists greens and blues first, as their own group, and the resort page shows how many greens and blues are open and groomed.

## 0.10.0 - Open Lifts and Trails, Trail Map

### 🌟 Features
* **Which lifts and trails are open, by name.** On a resort's page, "On the mountain" now shows trails open next to lifts open, and "Open right now" folds out the open lifts and the open trails with their colour (green, blue, black, double black, park) and whether they're groomed. Aspen Snowmass lists each of its four mountains.
* **A trail map of what's open.** Each resort page has a map of its runs and lifts: open runs in their trail colour, closed runs grey, running lifts red, lifts opening later dashed. Tap a line for its name. Keystone's report doesn't name its runs, so its map shows every run in its colour.
* **More resorts report in.** Steamboat and Aspen Snowmass now have live reports (lifts, trails, snow), Copper and Eldora add trails to their lift counts, and Keystone gets its lift count from OnTheSnow.

### 🔧 Improvements
* The Plan table has a Trails column beside Lifts.

### 🐞 Fixes
* The "Trail map (OpenSkiMap)" link works again for Steamboat, Eldora and Aspen Snowmass (OpenSkiMap had changed their ids).

## 0.9.0 - Free Days, Dashboard Card, Shorter Drives

### 🌟 Features
* **Picks only the days you're free.** Choose a Home Assistant calendar under More → Settings ("Calendar for free days"). A day with a timed event between 8am and 3pm counts as busy; all-day events like holidays don't. The best bet is always a free day, and busy days say "Busy" on their day button.
* **A dashboard card.** A new `sensor.ski_best_bet` holds the best resort and day, the fresh snow, when to leave and the drive. The Documentation tab has a card to paste into any dashboard.
* **A nudge to set your home.** While the home departure point is still the downtown-Denver placeholder, the Forecast tab says so and links to where to change it.

### 🔧 Improvements
* **Drive time counts for more.** It's now 20 of the 100 points (was 10): 75 minutes or less is free and 3½ hours or more gets nothing, so a long drive has to be worth it. Wind and temperature give up 5 points each.
* **Resorts that aren't open drop out.** A resort whose report says it isn't open for the season, or with no lifts running at midday, goes to the bottom of the Plan list marked "not open yet" and is never the best bet.
* "Add a day" on the Season tab folds away behind a button, since Garmin logs your days on its own.
* Removed the Shopping list box under More (Home Assistant has its own list; the packing list still uses it).

## 0.8.0 - The Guide-Sign Redesign

### 🌟 Features
* **A whole new look, taken from the signs on the drive up.** Guide-sign green day and night, each resort on a brown recreation-sign tab, big white snow totals, and an amber message board that says when to leave. Amber only ever marks your next move: the leave time and live road alerts.
* **The Forecast tab opens on a sign.** The resort and day worth it, how much fresh snow, the high and the gusts, then the amber board with the leave time and an "I'm going" button. Tap a day underneath and the board flips to that day.
* **Two columns on a computer:** the sign and the days on the left, every resort's 15-day snow on the right.

### 🔧 Improvements
* Five tabs instead of six: Forecast, Plan, Radar, Season and More. Gear and Settings now live together under More.
* On the Plan tab the top pick is a sign with its leave time on the board, and CDOT road alerts show on the amber board.
* Resort pages lead with the elevation switch and big totals, then the snow chart and getting there.
* On a phone, tables keep the columns that matter and the season's days stack into rows.
* The season recap video uses the new colours and type.
* The sign lettering (Overpass) is built into the add-on, so it looks right even with a weak signal.

## 0.7.0 - Season Recap, Clearer Charts

### 🌟 Features
* **Season recap.** A "Season recap" button on the Season log tab plays a 15-second animation of your season so far: days on snow (board and skis), vertical and how many times up Everest that is, top speed, the resorts you rode, and how you compare with last season by the same date. "Save video" saves it as a phone-shaped video to share. Tested in Chrome; not yet tried in the Home Assistant phone app.

### 🔧 Improvements
* **Snow charts are easier to read.** Weekends are shaded, the three biggest snow days on a resort page show their inches, and in dark mode days 11-15 are a clearly darker blue than days 1-10.
* **Easier with a keyboard or screen reader.** Resort rows in the forecast are proper links, status messages are read out, form fields are labelled, and the page has a heading. The radar doesn't start moving by itself when your device is set to reduce motion.
* When a resort's forecast hasn't loaded, it says Open-Meteo didn't answer and that it tries again in a minute.
* An empty season log says how to add days instead of showing an empty table.

## 0.6.0 - Best Bet, Phone Tab Bar, Instant Forecast

### 🌟 Features
* **Best bet at the top of the Forecast tab.** The best resort and day in the next five days, with fresh snow, the high, gusts and when to leave, and an "I'm going" button. Tap a day underneath to see that day's top pick, or "All resorts that day" to open the Plan tab on that date. Powder alerts show here too.
* **Tabs along the bottom on your phone**, with icons. Buttons and fields are bigger and easier to tap.

### 🔧 Improvements
* **The forecast shows up straight away.** The page shows the last forecast it had while a fresh one loads. If Open-Meteo doesn't answer, you see the last good forecast and the time it's from instead of "no forecast model answered", and the add-on waits a few minutes before asking again, so a slow Open-Meteo no longer holds up the page.
* **Resort pages put the snow first:** big next 5, 6-10 and 11-15 day totals, then the daily snow chart and "Getting there", with the webcams after. When no snow is due in the next 48 hours it says so instead of showing an empty chart.
* The page sits in the middle of wide screens, snow totals are larger, and a 5-day total at or above your powder alert size stands out in blue.
* When Claude isn't connected, Daily Snow no longer takes the top of the page; a short line under the forecast links to Settings.
* After an update the browser loads the new page, not an old saved copy.

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
