# Changelog

## 0.10.2 - PT Office Reminder

### 🌟 Features
* **A reminder when you get to the PT office.** In Settings › Home Assistant › Reminder at the PT office, type the office address (looked up on OpenStreetMap) or tap "I'm at the office now" while you're there, then pick your phone. When your phone arrives (checked every minute), you get a notification to ask your PT about new or changed exercises, listing the PT exercises you do now, plus a nudge to log biofeedback. While you're there, Today shows buttons to add a PT exercise, log biofeedback and open your PT report.
* **Add a PT exercise from Today.** "+ Add an exercise from my PT" under the daily non-negotiables opens the form, set up as a daily tick-box every day.

### 🔧 Improvements
* Drop-down menus are readable in dark mode.
* Settings saved by background checks can't overwrite each other.

## 0.10.1 - Pelvic Floor Biofeedback

### 🌟 Features
* **Track your manometric biofeedback sessions.** Turn it on in Settings › Pelvic floor biofeedback (pick your PT's unit: mmHg, cmH2O or µV, and how often you go). After each session, log resting tone, peak squeeze, endurance hold, time to relax after a squeeze, quick flicks and resting tone at the end, plus what your PT said; leave any blank. History charts resting tone and peak squeeze and shows first vs latest for each reading with "better" or "not yet" (lower resting tone and faster relaxing count as better for a tight pelvic floor). Today reminds you when the next session is due (or snooze it 3 days), the PT report includes it, and the coach can see it.

## 0.10.0 - PT Exercises, PT Report, Trends, Ski Checks, Records, Install

### 🌟 Features
* **Your PT's exercises (Settings › From your PT).** Add what your physio gives you: name, dose, how-to steps, which days, and whether it's a daily tick-box or goes with strength (sets come from a dose like "2 x 12"). It shows up on Today with a PT tag. Put seconds in the dose ("3 x 30 s hold") and it gets a timer.
* **PT report (More › PT report).** One page for appointments: workouts done vs planned, check-ins, average kidney and pelvic floor scores with the trend chart, how often each daily non-negotiable got done, every exercise's first vs latest (weight × reps, reps or hold time), personal records, anything marked "Bothered me", and your notes. Pick 14 to 90 days; "Print or save PDF" gives a clean printout.
* **Symptom trends (History › How you've felt).** Kidney and pelvic floor scores by day with workout effort underneath, and plain-language patterns: how you feel the morning after hard vs easier days, which kind of day (Legs, Core, Cardio…) is followed by the highest scores, and which way the scores are heading. Also as a table.
* **Ski readiness checks.** Every two weeks until opening day: wall sit, single-leg balance (eyes closed, each leg), skater steps in 30 s and side plank (each side). Timers count up and fill in your time when you tap Done now. Results show first vs latest on the Week tab; Today reminds you when one is due.
* **Faster set logging.** "↺ Same as last time" fills your sets with exactly what you did last time, and changing a weight or reps on one set updates the sets after it that matched. (The rest timer already starts when you tick a set.)
* **Personal-record trophies.** Saving a workout that beats your best (heaviest weight, most reps at a weight, most reps, longest hold) pops a 🏆 celebration, and the records show on the done card and in History.
* **Install as an app (Settings › Install as an app).** Open the add-on's own address on your phone (on home Wi-Fi) and add it to the home screen: it opens full screen with its own icon, straight to Today.

### 🔧 Improvements
* Ticks on the daily non-negotiables and the day type are now saved with each workout (for the PT report and trends).
* The rest timer stops when you save the workout.

## 0.9.8 - Leaky Can Cues

### 🔧 Improvements
* **Core Canister Breathing is cued around the TA.** Fingers just inside the hip bones; on each slow out-breath you should feel the TA tighten and flatten under them. A bulge or breath hold means ease off and reset on the next breath.

## 0.9.7 - Core Canister Breathing

### 🌟 Features
* **Core Canister Breathing (Leaky Can) every day.** 40 slow breaths (4 rounds of 10) in the daily non-negotiables, before the TVA Adductor Hack. Breathe in and let the ribs widen and the pelvic floor relax; breathe out and draw the lower belly in with a light pelvic floor lift, with nothing pushing down or bulging. Cued for a tight pelvic floor: no gripping, and the relax matters as much as the lift.

## 0.9.6 - Done for Today

### 🌟 Features
* **Completed means completed.** Once today's workout is saved, the Today tab shows "✅ Today's workout is done" with what you logged (exercises, sets, cardio minutes, effort) and a link to History, instead of the whole workout again. The cool-down (and its guided player) and the second-session option stay available.
* **No double logging.** The same session can't be saved twice in one day; a finished second session shows as done too.

## 0.9.5 - Side-by-Side Timers, Opener Timers, Guided Cool-Down

### 🌟 Features
* **One side at a time.** Holds done per side (side planks, one-leg holds, one-sided stretches) run a **left** timer, give you 5 seconds to switch, then run a **right** timer before ticking the hold off. The timer bar says which side you are on.
* **Timers on the daily openers.** Timed warm-ups (the 2-minute Gut-Motility Primer and rib breathing, the vibration board primer) have a "▶ Start timer" button that checks the item off when time is up. Rep-based openers stay a simple check box.
* **"▶ Play guided cool-down" on the Today tab.** It plays exactly today's cool-down (qigong moves, yoga poses, vibration board or inversion table, breathing) in your chosen natural voice, with time for each one, both sides for one-sided poses, and the picture following along. The first time it prepares the audio (a few minutes); repeat plays start straight away.
## 0.9.4 - Guided Qigong Session

### 🌟 Features
* **Guided Baduanjin session** in Mind & Body > Qigong. Pick 30, 45 or 60 seconds per move and press play: your chosen voice introduces each of the eight moves with its kidney-safe cues, then gives you quiet time to do it, and finishes with a short breathing practice.
* **The picture follows along.** The player shows the photo of the move being described, "Move 3 of 8", and the kidney-safe note where the photo shows the traditional version. Back and Next jump between moves, and the screen stays on while it plays.
* The first time for each voice and pace, the add-on prepares the audio (a few minutes on the Green); after that it starts straight away.
## 0.9.3 - Garmin Lighter Days (Off by Default)

### 🌟 Features
* **Let Garmin make a day lighter.** A switch in Settings > Garmin, **off by default**. When it is on, today's synced Garmin numbers are compared with your own last two weeks:
  * short sleep (under 6 hours), low body battery (under 30), HRV well below your usual (under 85%), or resting heart rate 5 or more above your usual.
  * **One sign** makes the day lighter: one fewer exercise, about a quarter less cardio, and no load increases.
  * **Two or more signs** make it a recovery day.
* When it kicks in, the Today tab says which numbers triggered it. With no Garmin data for today, nothing changes.
## 0.9.2 - Swap Button and Weekly Recap

### 🌟 Features
* **"Swap" on every exercise card** picks a different safe exercise for the same muscle group, for today only, using your equipment and the same kidney and pelvic floor safety filter (paused exercises are never picked). Handy when a machine is busy or a move just doesn't feel right. Tap again for another option; "Undo them" at the top of Today brings back the original.
* **"Weekly recap" on the Week tab** asks the coach for a short summary of your week: what you did compared with the plan, how your kidney and pelvic floor scores trended, any personal bests, and what to change next week.
## 0.9.1 - Home Assistant Sensors and Morning Reminder

### 🌟 Features
* **Two sensors for your dashboards:** `sensor.workout_today` (for example "Strength: Legs: quads and glutes", "Cardio: 25 min bike", "Rest day" or "Done", with the exercise list as attributes) and `sensor.workout_streak` (days in a row with a workout; planned rest days don't break it). They update every 5 minutes and right after you log something.
* **Morning check-in reminder to your phone** through the Home Assistant app. Pick your phone and a time in Settings > Home Assistant. It only comes if you haven't checked in or worked out yet that day, and tapping it opens this app. "Send a test" tries it straight away.

### 🔧 Changes
* The add-on now asks Home Assistant for API access (needed for the sensors and notifications). Home Assistant shows this on the add-on page.
## 0.9.0 - Peloton and Rower Come Back When Your Body Says So

### 🌟 Features
* **The Peloton and the water rower unlock from your own scores** (morning check-ins and workout logs), not from a calendar.
  * **Peloton:** unlocks when your pelvic floor score averages 3 or lower over the last 7 days with no day above 5. It starts at 12 easy minutes and adds 5 minutes a week (up to 45). It steps back to walking after a pelvic floor score of 5 or more.
  * **Rower:** unlocks after 2 good weeks on the Peloton and 14 days of kidney scores at 3 or lower. It starts at 8 easy minutes at a low water level, adds 5 minutes a week (up to 30), and steps back after a kidney score above 4.
* **Once unlocked, they rotate with walking on your cardio days**, with the minutes shown on the Week tab.
* **Week tab status card** for both machines: in your plan, or what is still needed ("Needs a few more scored days", "unlocks when…").
* **Settings > Peloton and rower:** Automatic, "PT cleared it" (use it now) or "Not yet" (keep it off) for each machine. Your choice wins over the automatic rules.
* The coach knows which machines are unlocked, and its plan changes can't add a locked one.

These thresholds are a starting point, not medical advice. Check them with your PT.
## 0.8.4 - Snow Days

### 🌟 Features
* **"Log a snow day" on the Today tab** (when Skiing or Snowboarding is ticked in Settings). Pick skiing or snowboarding, hours on the snow, effort, and your kidney and pelvic floor scores, plus notes. It is saved to History as that day's workout.
* **The next day's legs get a break:** a legs or full-body day right after a snow day becomes a core activation day.
* The Week tab labels snow days, and a snow day counts as a done day, so it doesn't trigger the skipped-day re-plan.
* Anything you had already typed into the day's gym workout is kept.
## 0.8.3 - "Bothered Me"

### 🌟 Features
* **"Bothered me" on every exercise.** Tap it and that exercise sits out of your plans for 2 weeks (not forever). It is left out of daily picks, second sessions and the coach's suggestions while it rests.
* **It comes back with a reminder.** For two weeks after it returns, its card says it bothered you and to go lighter. Tap "Bothered me" again if it still does.
* **Paused exercises in Settings** with the date each one comes back and a "Bring back" button.
* The coach is told which exercises are paused and why.
## 0.8.2 - Timer Bar Fix

### 🔧 Changes
* Fixed the timer bar showing up empty when no timer was running.
## 0.8.1 - Hold Timers, Rest Timers, Holds That Grow

### 🌟 Features
* **Hold timer.** Tap a hold's number (wall sits, planks, stretches) and a countdown starts in a bar above the tabs. When time is up it beeps, buzzes and ticks the hold off on its own. "Done now" stops early and records how long you actually held; "Cancel" stops without ticking.
* **Rest timer.** Finishing a set or a hold starts a rest countdown (the exercise's rest time, or 60 s for sets and 45 s between holds). "+15 s" adds time, "Skip" ends it.
* The screen stays on while a timer runs.
* **Holds get longer over time.** The seconds you hold are saved, and next time the card suggests 5 s more (10 s in Build+ weeks, up to 2 minutes). It holds steady after a tough session or high symptoms, and the Easy week drops one hold.
## 0.8.0 - Morning Check-In, Equipment Without Symptom Limits

### 🌟 Features
* **"How do you feel today?" on the Today tab.** Two sliders, left kidney / flank and pelvic floor tightness. Today's plan is built from your check-in instead of how you felt after your last workout, so a rough night changes the plan right away (a kidney score above 5 still makes today a recovery day, the cool-down follows your scores, and so on). You can change it any time, and the coach sees it. The sliders at the end of your workout start from your check-in.

### 🔧 Changes
* **The vibration board and inversion table are no longer held back by symptoms.** They help when you are tight, so the vibration board primer shows up on strength days and a board or inversion table session is added to the cool-down every other day, and on every tight or recovery day. The cards still say to keep the board on the lowest setting, the table at a shallow angle, and to stop at dizziness or sharp pain.
## 0.7.2 - Varied Cool-Downs, Recovery Equipment, Check Marks For Holds

### 🌟 Features
* **The cool-down changes every day** instead of repeating. After strength you get a different mix of yoga poses (spine, fold, hips, rest). After cardio it rotates between half of the qigong moves, the other half, all eight, a yoga flow, or a **mix of qigong moves and yoga poses**, always finishing with a breathing practice.
* **Vibration board and inversion table are in the plan.** A short, lowest-setting **vibration board primer** joins the warm-up on strength days, and about every other day the cool-down includes the **vibration board leg release** or a shallow-angle **inversion table decompression**. They only appear when the equipment is ticked in Settings and your kidney and pelvic floor scores are low, and never on high-symptom days. Each card repeats the safety notes.
* **Timed holds are tracked with check marks.** Wall sits, planks and timed stretches show one numbered button per hold that turns into a check mark when you finish it, instead of boxes for reps. "+ Add hold" and "Remove last" adjust how many.
## 0.7.1 - The Cool-Down Follows The Day

### 🔧 Changes
* **Today's cool-down now matches the Week tab.** After strength it is the gentle yoga wind-down as before. On a **cardio day it is the Baduanjin qigong** (all eight moves in their kidney-safe form, with pictures) followed by a minute of belly breathing, instead of yoga. On recovery and rest days it is restorative poses and breathing. A high kidney or pelvic floor score still limits it to rest and breathing only.
## 0.7.0 - The Week Adapts When You Skip A Day

### 🌟 Features
* **Skip a strength day and the rest of the week is re-planned.** A strength day that passes without a logged workout is moved into the strength days you still have this week. Core activation goes first, then legs, back, hips and full body.
* **Your rest day stays, and so does the 5-strength-day limit.** If there isn't room for everything, the lowest-priority group is left out, and the Week tab tells you which group was moved up and which one was left out.
* Today's workout follows the new plan, and the coach sees it too. The re-plan only covers the current week, and it is switched off in opening week before the snow season so the taper isn't disturbed.
* A second session logged on its own doesn't count as that day's workout.
## 0.6.4 - No Weight Box For Bodyweight Moves

### 🔧 Changes
* **Bodyweight exercises only track reps.** The pounds box is gone for bodyweight moves, bands, rings, sliders, foam rolling and the like, and for your daily non-negotiables such as wall sits and heel slides. Weighted exercises (dumbbells, kettlebells, cables, machines, barbells) and exercises you add yourself keep it.
## 0.6.3 - More Yoga Pictures

### 🌟 Features
* **Nine more yoga poses now have pictures:** staff pose, goddess pose, head-to-knee forward fold, crocodile, gate pose, wide-leg forward fold, easy seat, wide-angle seated forward fold and the wrist stretch. They come from freely licensed Wikimedia Commons photos, bundled in the add-on, with the photographer and licence shown under each picture.
## 0.6.2 - Second Session Logged On Its Own

### 🌟 Features
* **The second session is its own workout.** It has its own section at the bottom of the Today tab with its own effort rating and notes, and its own "Complete second session" button. It shows up as a separate entry in History.
* Finishing the first workout no longer touches the second session's sets: anything you have typed for it is kept until you complete it.
* The first workout logs only its own exercises, so your suggested weights and progress charts are not mixed up with the second session.
## 0.6.1 - Second Sessions On Request

### 🌟 Features
* **"+ Add a second session" on the Today tab.** Choose a second strength session (a different muscle group from the first), core, mobility, or 20 minutes of easy cardio. Strength, core and mobility exercises are added to your list with sets you can log; extra cardio gets its own card.
* The same safety checks as the coach's changes apply: nothing that is filtered out for your kidney or pelvic floor, nothing needing equipment you don't have, no second strength session on a recovery or rest day, and extra cardio is limited to 5 to 30 easy minutes.
* The coach can also suggest a second cardio session, and you approve it with Apply.
* "Undo them" on the Today tab removes added sessions and coach changes together.
## 0.6.0 - Ski and Snowboard Season Ramp-Up

### 🌟 Features
* **The plan now builds toward opening day.** Set the snow season start date in Settings > Sports and the Week tab shows the phase and the days to go.
  * **Foundation** (more than 8 weeks out): general base, core work continues.
  * **Ski prep** (8 weeks to 2 weeks out): a second leg day each week, plus edge and balance control work on leg days.
  * **Sharpen** (the last two weeks): leg-heavy, the last hard sessions.
  * **Taper** (the last 3 days): no new leg load. Core, hips, mobility and rest, loads held and one set fewer.
  * **Opening day:** a rest day. **In season:** keep one leg day a week.
* The coach is told the phase and the days to opening day, so its advice and any plan changes follow it.
## 0.5.2 - More Pictures

### 🌟 Features
* **All eight Baduanjin moves now have pictures** (photos by Alexander Callegari, CC BY-SA 3.0 de).
* **Pictures for five more yoga poses** from freely licensed Wikimedia Commons photos: legs up the wall, reclined bound angle, knees to chest, happy baby and mountain pose. Each shows its photographer and licence under the picture. They are bundled in the add-on.
## 0.5.1 - Qigong Pictures

### 🌟 Features
* **Pictures for the Baduanjin qigong moves** (7 of the 8 so far), from freely licensed photos by Alexander Callegari on Wikimedia Commons (CC BY-SA 3.0 de, resized). They are bundled in the add-on, so there is nothing to set up.
* Where your kidney-safe version differs from the traditional movement (looking back, the sway, the forward fold), the card says so under the picture.
## 0.5.0 - Garmin Connected From Inside the App

### 🌟 Features
* **Connect Garmin in Settings.** Enter your Garmin email and password once (and the verification code if Garmin asks for one). The password is used only for the sign-in and is never saved; only a login token is kept on your Home Assistant, and it refreshes itself.
* **Automatic sync every few hours** of resting heart rate, HRV, last night's sleep, body battery and your latest activity. "Sync now" does it on demand.
* **The coach uses it.** It now sees your Garmin numbers alongside your logged effort and symptoms. If Garmin isn't connected it says so instead of guessing.

### 🔧 Changes
* Fixed the old sync reading the wrong field for resting heart rate (it always stored 0).
## 0.4.7 - Picture Test Tries Several Files

### 🔧 Changes
* The picture test now tries three different pictures and passes if any of them loads, instead of failing because one specific file is missing.
* Added `tools/upload_yoga.py`, a script that uploads the yoga pictures to your bucket one at a time with retries (the Backblaze web uploader rate-limits large drags).
## 0.4.6 - Picture Test Shows What It Found

### 🔧 Changes
* When the picture test can sign in but can't find a picture, it now lists how many pictures it found in your folder, whether any are in a subfolder, and an example file name, so a missing upload or a wrong folder is easy to spot.
## 0.4.5 - Test Your Picture Connection

### 🌟 Features
* **Test connection button** in Settings > Yoga pictures. It fetches one picture from your private bucket and tells you plainly what is wrong if it can't: wrong bucket name, wrong key or secret, a key without read access, the wrong folder, or an endpoint it can't reach. It never shows your keys.

### 🔧 Changes
* Settings now says "Private bucket details saved" until the test passes, instead of "connected" (it only meant the fields were filled in).
## 0.4.4 - Suggested Weights and Reps

### 🌟 Features
* **Each exercise card shows what you did last time and what to try today,** and the set rows are pre-filled with it. Small steps only: a rep or two at a time, and weight goes up (2.5 lb under 20 lb, otherwise 5 lb) only once you reach 12 reps, then you start back at 8.
* **It holds back when your body says so:** no increase after a hard session (effort 8 or more), or when your last kidney score was above 3 or pelvic floor above 6. Bodyweight moves progress a little faster.
* **Build+ weeks add two reps, and the Easy week backs off** to last time's load with one set fewer.
* Exercises you have never logged show no suggestion, so the first time is your own call.
## 0.4.3 - Five Strength Days With Core Activation Every Day

### 🌟 Features
* **Five strength days a week** (Mon, Tue, Thu, Fri, Sat) with Wednesday as the cardio day and Sunday as rest. The coach can still move days around, now up to 5 strength days a week with at least one rest or recovery day.
* **Core activation on every strength day:** each one has two core slots (activation and stability), and a dedicated **core activation day** joins the rotation. Cardio days add a short core or mobility piece too.
* The five groups (legs, back and posture, core activation, hips and balance, full body and core) rotate across the week and shift every week, so a weekday is never the same twice in a row.
## 0.4.2 - A Different Muscle Group Every Day, A Different Week Every Week

### 🌟 Features
* **Each strength day works a different group:** legs (quads and glutes, with ski and snowboard leg work), back and posture, or hips and balance. The three groups rotate week to week, so Monday is not always the same.
* **Cardio days add one short piece of extra work** for a group that isn't trained that day (core, or hip and spine mobility), which also alternates from week to week.
* **A 4-week cycle:** Base, Build, Build+, then an Easy week that trims one extra from each strength day. The Week tab shows which week you are in and what each day is for.
* The coach sees the muscle group planned for each day when it suggests changes.
## 0.4.1 - Roomier Tab Bar and Sports-Aware Coach

### 🌟 Features
* **Five tabs instead of seven:** Today, Week, Coach, Mind & Body and **More**. More opens a short menu for History, Library and Settings. Swiping still moves through every screen.

### 🔧 Changes
* **Untick Triathlon in Settings > Sports and it really goes away:** the coach no longer introduces itself as a triathlon coach, and cardio descriptions no longer start with "Triathlon Prep". The coach is now told which sports you are training for and sticks to them.
## 0.4.0 - Weekly Plan and Swipe Navigation

### 🌟 Features
* **Week tab:** see the whole week at a glance, Monday to Sunday, with next week one tap away. Each day shows what it is for (strength, cardio, recovery or rest), the cardio type, the exercises, a mind-body suggestion, and whether you did it. The default week is strength, cardio, strength, cardio, strength, a long easy cardio day, and a rest day. With Triathlon on, cardio rotates swim, run and bike.
* **Today follows the week.** Rest and recovery days turn into gentle recovery days, cardio days keep the strength part short, and the planned cardio type is used when it is safe for your pelvic floor score. A high kidney score still forces a recovery day, whatever the week says.
* **The coach can plan your week.** Ask it to adjust the week (there is a button on the Week tab) and it suggests changes to specific days. You approve with **Apply**. Every week keeps at least one rest or recovery day and at most 4 strength days, and cardio stays between 5 and 45 minutes.
* **Swipe left and right** to move between tabs. It is ignored on sliders, text boxes, audio players and sideways-scrolling strips so it never gets in the way.
* Weeks to snow season show on the Week tab when you set the season date in Settings.

### 🔧 Changes
* The bottom tab "Mind & Body" is now "Mind" to make room for the Week tab.
## 0.3.6 - Sports and a Coach That Can Change Your Plan

### 🌟 Features
* **Sports in Settings:** tick Skiing, Snowboarding and Triathlon, and optionally set when the snow season starts. Daily extras lean toward ski and snowboard legs and add a balance slot (single-leg, ankle and hip control). Triathlon controls whether the swim, bike and run cardio is used.
* **The coach can change today's plan.** Ask it, for example, for more ski-useful work or a shorter cardio day. It suggests changes (add or remove an exercise, change cardio minutes), and nothing happens until you tap **Apply**. "Undo coach changes" on the Today tab brings the original plan back.
* **Safety still wins:** every suggestion is checked by the app. Exercises that are filtered out for your kidney or pelvic floor, that need equipment you don't have, or that aren't in the library are skipped, and the coach is told why. On a recovery day the plan stays a recovery day (only gentle mobility can be added), and cardio can't jump by more than 10 minutes.
## 0.3.5 - Natural Voices for Meditation

### 🌟 Features
* **Pick your meditation voice.** Eight natural-sounding female voices (American, Scottish, British and Irish-English) made right on your Home Assistant with Piper, so there is no robotic phone voice and nothing is sent to a cloud service. Choose one under Meditation and tap "Hear this voice" to try it.
* Sessions Claude writes for you now become a real audio file with the normal player (pause, scrub, replay). A session you already made opens instantly the next time.
* A voice is about 60 MB and downloads the first time you pick it, so only the voices you use take space. The phone's own voice stays as a fallback if the audio can't be made.
## 0.3.4 - Yoga Pictures From Your Private Bucket

### 🌟 Features
* **Yoga pictures from a private bucket,** set up the same way as the Trading Terminal: fill in the bucket endpoint, name, access key and secret key on this add-on's Configuration tab. The add-on fetches each picture with the key, keeps a copy on the Green (a few MB), and the key never reaches your phone.
* The bucket can stay private. Without the key set, Settings still accepts a public folder address instead.
## 0.3.3 - Meditation, More Yoga, Coach That Reads Your Data

### 🌟 Features
* **Meditation** in the Mind & Body tab: about 70 free guided practices (mindfulness, breathwork, yoga nidra, sleep, open awareness) from The Holistic Care's Stillness Library, played straight from their server. Nothing is stored on your Home Assistant.
* **A session written for you:** pick a length (3, 5 or 10 minutes) and an optional focus. Claude writes a calm script with slow breathing, long exhales and no straining, and your phone reads it aloud.
* **32 more yoga poses** (79 in total, including gentle floor work, supports like legs up the wall, mobility and four breathing practices with no breath holds). Every pose has steps and a safety note.

### 🔧 Changes
* **The coach no longer tries to run database commands.** It could not ask for approval from inside the app, so it stalled. The app now reads your recent workouts, symptoms, sets and Garmin data itself and gives them to the coach. The HTML progress report is written the same way.
* If there is no Garmin data stored yet, the coach says so instead of guessing.
## 0.3.2 - Mind & Body: Yoga, Qigong and Cool-Downs

### 🌟 Features
* **Mind & Body tab:** 47 yoga poses (steps, tips, safety notes, up to 5 pictures each) and the Baduanjin qigong routine, adjusted for the left kidney: head-only turns, hips square, folds only as far as is comfortable.
* **Cool-down on Today:** a short, gentle yoga wind-down after cardio, picked from your last symptom scores. High kidney or pelvic floor scores give rest and breathing only.
* **Safety:** deep twists, backbends, inversions, hard core work and extreme stretches are marked "not in auto picks" and never chosen automatically.
* **Settings:** gear details the coach reads (weights, plates, bands), vibration plate and inversion table added as equipment, and an address for the yoga pictures.

### 🔧 Changes
* Yoga pictures come from the Yoga Posture Dataset on Kaggle (CC0) and are hosted outside the add-on.
## 0.3.1 - Settings Tab and In-App Claude Sign-In

### 🌟 Features
* **Settings tab:** pick the equipment you have by tapping chips. Today's plan rebuilds as soon as you change it. More settings (sports, training goals) will go here later.
* **Connect Claude inside the app:** Settings > Connect Claude gives you a sign-in link, you paste the code back, and the coach uses your Claude subscription. No more `claude setup-token`. The login is kept across updates.

### 🔧 Changes
* An old, expired token in the Configuration tab no longer breaks the coach once you have signed in (that was the "401 Invalid bearer token" error).
* When the sign-in expires, the coach tells you to reconnect instead of showing a raw error.

## 0.3.0 - Fast Phone-First App

### 🌟 Features
* **New, much faster app.** Streamlit is gone: the screens are a lightweight web page served by the add-on's own server. Taps (ticking warm-ups, marking sets done, adding sets) respond instantly on your phone; the server is only called to load and save.
* **Built for the phone:** bottom tab bar (Today, History, Coach, Library), big tap targets, a number keypad for weight and reps, and light or dark to match your phone.
* **Set logging per exercise:** each exercise card has its own sets with a done button, lbs and reps. "+ Add set" copies your last set, and "+ Add another exercise" logs something extra.
* **Auto-save** shows "Saved ✓" at the top. It saves right away when you lock the phone, and the finish sliders and notes are remembered on that phone until you complete the workout.
* **History:** tap a workout to see its exercises, cardio and every set, with a progress chart per exercise (heaviest lbs and total reps).
* **Coach** remembers the last few messages of the conversation, so follow-up questions work.
* **Library:** instant search with focus chips (legs, upper back, core, mobility, balance), muscle and equipment filters, and "Show more".

### 🔧 Changes
* One server on port 8501 for the app and Claude Terminal (`/workout/today`, `/workout/log`); port 8000 is no longer used.
* Smaller image and faster startup: Streamlit, pandas and pyarrow are no longer installed.
* The daily plan and cardio progression use your Home Assistant time zone's date.

## 0.2.1 - Workout History, API Ninjas & Your Home Gym

### 🌟 Features
* **History tab:** every completed workout with its date, effort, symptoms, exercises, cardio and each set (weight, reps, done), plus a progress chart per exercise (heaviest weight and total reps by day).
* **Sets saved as real rows** (new `workout_sets` table) instead of a block of text in the notes, so progress can be charted.
* **Auto-save:** warm-up ticks and the set tracker save as you go. Closing or reloading the page no longer loses them, and a page left open overnight starts fresh the next day.
* **API Ninjas exercises (optional):** add your free API Ninjas key in Configuration and the add-on collects their ~3,000 exercises (with steps and safety notes) in the background, staying under 90 calls an hour and your monthly budget (default 2,500 of the free 3,000). Progress shows on the Exercise Library tab.
* **Weight plates** are now equipment (your 25, 2 x 10 and 2.5 lb plates). Plate-loaded moves get the same spine-loading checks as dumbbells.

### 🔧 Fixes
* **Workout dates use your Home Assistant time zone** instead of UTC, so evening workouts land on the right day.
* **Equipment defaults to your home gym:** bodyweight, bands, dumbbells, 15 lb kettlebell, plates, foam roller, adjustable bench, pull-up bar, Centr 1 cable machine, EZ-curl bar, barbell and cardio machines. Daily extras no longer pick stability ball, medicine ball, gym-machine, suspension, slider or unknown-equipment exercises. Barbell lifts stay filtered out for your kidney. If you already saved Configuration, click **Reset to defaults** there (or tick the new items) to pick this up.

## 0.2.0 - Exercise Library (about 5,000 exercises)

### 🌟 Features
* **Exercise Library:** merges four databases into one list of about 5,000 exercises, stored in the `exercise_library` table of `/config/workout_tracker.db`:
  * Free Exercise DB (876, public domain, photos and steps)
  * RepDB (609, illustrations, steps and tips). Exercise data by RepDB (repdb.co)
  * Strength to Overcome functional fitness database (3,242, detailed movement tags)
  * Boostcamp programs (830 exercise names with typical sets and reps)
* **Safety filter for your kidney, pelvic floor and core:** every exercise is checked for torso twisting, weight loading the spine, one-sided weight, crunch/sit-up/plank pressure, jumping, explosive swings, heavy barbell lifting, lower-back loading, upside-down positions and advanced level. About 1,850 pass; the rest stay browsable with the reason they're left out.
* **Pictures across sources:** exercises without their own picture borrow the picture of a closely similar movement, labeled as such.
* **New 📚 Exercise Library tab:** search and filter by focus (legs, upper back, core, mobility, balance), muscle and equipment.
* **Daily plan adds 4 rotating extras** from the safe list: snowboard legs, posture/swim pulling, beginner core and mobility (2 gentle stretches on recovery days). New picks each day, each with a "why it's in today's plan" line.
* **Equipment setting:** choose the equipment you have in the add-on Configuration tab; daily extras only use that equipment.
* **Better pictures for your own moves:** Wall Sit, Dead Bug, Banded Lateral Walk, Butterfly and Child's Pose now use RepDB illustrations.

## 0.1.9 - Cardio Minutes, Exercise Guides & Coach Errors

### 🌟 Features
* **Cardio now says how long:** every cardio session shows its minutes (recovery 15, swim 20, run 20, incline walk 20, bike 30), at an easy Zone 2 pace.
* **Cardio auto-adjusts from your logs:** adds 5 min (max once a week, up to 45) when your last session felt easy (effort 6 or less) and flank pain stayed at 3 or below. Cuts back by about a quarter when your last effort was 8+. A "Why this length" line explains each change.
* **Exercise guides:** every exercise shows its dose (sets, reps or time) and step-by-step form cues from your routine. Tap an exercise to open it.
* **Demo photos:** Dead Bug, Lateral Band Walk, Butterfly, Child's Pose, bike, treadmill run and walk show start/finish photos that flip like a GIF (public-domain Free Exercise DB).
* **Set tracker** creates one row per prescribed set instead of always 3.

### 🔧 Fixes
* **AI Coach errors now show the real message** (Claude's CLI prints errors to stdout, which the app used to drop). Errors also appear in the add-on's Log tab.
* **Claude token:** spaces and line breaks picked up when copying the token from a terminal are removed automatically.

## 0.1.8 - Open Web UI & Sidebar

### 🌟 Features
* **Open from Home Assistant:** the add-on page now has **Open Web UI**, and you can turn on **Show in sidebar** to get a "Workouts" panel. Works in the HA phone app, behind your Home Assistant login.
* Direct access on port 8501 still works.

## 0.1.7 - Prebuilt Image, Claude Token & Garmin Fix

(0.1.6 was never released: its build hung and was replaced by this version.)

### 🌟 Features
* **Claude token setting:** new "Claude token" field in the add-on Configuration tab. Run `claude setup-token` in Claude Terminal and paste the token there so the AI Coach uses your Max subscription. The token stays on your Home Assistant, never on GitHub.

### 🔧 Fixes
* **Installs no longer build on the HA Green:** GitHub now builds the add-on image and Home Assistant just downloads it. Installs and updates take a minute or two instead of 40+ minutes.
* **Fixed the 0.1.5 install failure:** 0.1.5 ran on Python 3.13 and tried to compile `pydantic-core` and `numpy` from source. The image now uses Python 3.12, where every package installs from a prebuilt wheel.
* **Fixed the endless dependency loop:** `garminconnect` 0.2.14 pulled in `withings-sync`, whose newer versions require a newer `garminconnect`, so pip searched old versions forever. Now on `garminconnect` 0.3.17, the same version that created your Garmin token.
* **Garmin sync reads your token again:** sync now loads `/config/garmin_tokens.json` in the 0.3.x token format and saves refreshed tokens back to it.
* **Fixed the app crashing on open:** the web UI and API now use the database in `/config/workout_tracker.db` (the one created at startup) instead of an empty file inside the container.
* Removed the unused `endurance-coach` CLI, which forced a slow C++ compile of `better-sqlite3`.

## 0.1.0 - Initial Release (The Megazord AI Coach)

Welcome to the AI Workout Tracker! This initial release combines five massive AI frameworks into a single, locally-hosted Home Assistant Add-on powered by Claude.

### 🌟 Features
* **Garmin Connect Integration:** Natively connects to Garmin to pull Resting Heart Rate, HRV, and recent activity logs securely into a local SQLite database, avoiding enterprise API costs.
* **Endurance Coach Engine:** Integrates Triathlon periodization, TSS (Training Stress Score) tracking, and Heart Rate Zone targeting.
* **Gym-Bro Explainable Planning:** AI will dynamically build workouts based on your symptoms and explain *why* it made each decision. Includes a button to generate portable HTML progress reports.
* **Physical Therapy Hard Gate:** Automatically halts workouts and prescribes recovery breathing if Left Kidney or Pelvic Floor pain metrics exceed safety thresholds.
* **Automated PT Referrals:** Dynamically links to the Pelvic Floor PT Directory if symptoms require a professional consultation.
* **Movement-Systems Biomechanics:** Support for video/image form uploads. Claude will use Shirley Sahrmann's frameworks to analyze spinal and pelvic alignment to protect Pyeloplasty adhesions.
* **Local Claude CLI Runner:** Uses your existing Claude session token to run inference entirely in the background terminal—zero API fees!

### 🔧 Security
* Strict `.gitignore` implementation ensuring OAuth tokens and databases remain strictly on your local Home Assistant instance.
* Dedicated `setup_garmin.py` for headless MFA resolution.
