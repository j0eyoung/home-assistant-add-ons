// Ski Assistant UI. Relative URLs so it works behind Home Assistant ingress.
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const api = async (p, o = {}) => {
  const r = await fetch('api/' + p, { headers: { 'Content-Type': 'application/json' }, ...o });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || r.status);
  return j;
};
const today = new Date().toLocaleDateString('en-CA');
const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const dayLabel = iso => { const d = new Date(iso + 'T12:00'); return `${DOW[d.getDay()]} ${d.getDate()}`; };
const inch = v => v == null ? '-' : (Math.round(v * 10) / 10) + '"';
const t12 = s => { const [h, m] = s.split(':').map(Number); return `${h % 12 || 12}:${String(m).padStart(2, '0')}${h < 12 ? 'am' : 'pm'}`; };
const hm = n => n >= 60 ? `${Math.floor(n / 60)}h${String(n % 60).padStart(2, '0')}` : `${n} min`;
const isoPlus = n => { const d = new Date(today + 'T12:00'); d.setDate(d.getDate() + n); return d.toLocaleDateString('en-CA'); };
const dayName = (iso, long) => iso === today ? 'Today' : iso === isoPlus(1) ? 'Tomorrow'
  : new Date(iso + 'T12:00').toLocaleDateString('en-US', { weekday: long ? 'long' : 'short' });
// Index ranges of Saturdays and Sundays, for the shaded weekend bands behind the snow bars
const weekendBands = dates => {
  const out = [];
  dates.forEach((iso, i) => {
    const w = new Date(iso + 'T12:00').getDay();
    if (w !== 0 && w !== 6) return;
    const last = out[out.length - 1];
    if (last && last[1] === i - 1) last[1] = i; else out.push([i, i]);
  });
  return out;
};
const monthDay = iso =>new Date(iso + 'T12:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
// "2:15pm", with the day in front when it isn't today
const clock = s => { const d = new Date(s * 1000), t = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }).replace(' ', '').toLowerCase();
  return d.toLocaleDateString('en-CA') === today ? t : `${DOW[d.getDay()]} ${t}`; };
// Per-browser copy of the last forecast, so the page paints at once while the add-on fetches a fresh one
const stash = (k, data) => { try { localStorage.setItem('ski_' + k, JSON.stringify({ at: Date.now(), data })); } catch (e) {} };
const unstash = (k, maxH = 12) => { try { const v = JSON.parse(localStorage.getItem('ski_' + k)); return v && Date.now() - v.at < maxH * 3600e3 ? v.data : null; } catch (e) { return null; } };

let RESORTS = [], SET = {}, FC = null, OUT = null, HERO_DATE = null;
const TABS = { forecast: 'Forecast', plan: 'Plan', radar: 'Radar', log: 'Season', more: 'More' };
const ICONS = {  // 24px line icons, drawn with currentColor
  forecast: '<path d="M12 2v20M3.3 7l17.4 10M3.3 17l17.4-10M9.5 3.5 12 6l2.5-2.5M9.5 20.5 12 18l2.5 2.5"/>',
  plan: '<circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h7.5a3.5 3.5 0 0 0 0-7h-7a3.5 3.5 0 0 1 0-7H16"/>',
  radar: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 12l6.4-6.4"/><circle cx="12" cy="12" r="1"/>',
  log: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4M8 14h3M8 17h6"/>',
  more: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
};
// More holds Gear and Settings
const LOADERS = { forecast: () => route(), plan: loadRoads, radar: loadRadar, log: () => { loadStats(); loadDays(); },
  more: () => { loadGear(); loadClaude(); loadGarmin(); loadSettings(); } };
const ARROW_R = '<svg class="ar" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12h16M13 5l7 7-7 7"/></svg>';
const ARROW_L = ARROW_R.replace('M4 12h16M13 5l7 7-7 7', 'M20 12H4M11 5l-7 7 7 7');
const SEP = '<span class="sep">·</span>';
const ARROW = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20V4M5 11l7-7 7 7"/></svg>';

function paint(t) {
  for (const k in TABS) {
    $(k).classList.toggle('on', k === t);
    const b = $('b_' + k); b.classList.toggle('on', k === t);
    if (k === t) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  }
}
function show(t) {
  paint(t);
  LOADERS[t]();
  try { localStorage.setItem('tab', t); } catch (e) {}
  const want = t === 'forecast' ? (location.hash.startsWith('#resort/') ? location.hash : '') : '#' + t;
  if (location.hash !== want) history.replaceState(null, '', want || location.pathname + location.search);
}
$('nav').innerHTML = Object.entries(TABS).map(([k, v]) => `<button id="b_${k}" onclick="show('${k}')">` +
  `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[k]}</svg>` +
  `<span>${v}</span></button>`).join('');
const rname = id => id === 'other' ? 'Other' : (RESORTS.find(r => r.id === id) || {}).name || id;
const ropts = blank => (blank ? '<option value="">(any)</option>' : '') + RESORTS.map(r => `<option value="${r.id}">${esc(r.name)}</option>`).join('');

async function init() {
  let t = 'forecast'; try { t = localStorage.getItem('tab') || 'forecast'; } catch (e) {}
  if (t === 'gear' || t === 'settings') t = 'more';
  const h = location.hash.slice(1);
  if (TABS[h]) t = h; else if (h.startsWith('resort/')) t = 'forecast';
  if (!TABS[t]) t = 'forecast';
  paint(t);
  $('today').textContent = new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  const fc = unstash('forecast'), ol = unstash('outlook');
  if (fc) { FC = fc; renderForecast(); }
  if (ol) { OUT = ol; renderHero(); }
  RESORTS = await api('resorts');
  SET = (await api('settings')).settings;
  fillDepartures();
  homeNote();
  for (const id of ['d', 'ld', 'gd']) $(id).value = today;
  $('lr').innerHTML = ropts();
  show(t);
  loadDailySnow(false); loadForecast(); loadOutlook(); rank();
  addEventListener('hashchange', route);
}
// Leave times start from the first departure point; the default is a placeholder in downtown Denver
function homeNote() {
  const h = (SET.departures || [])[0] || {};
  const placeholder = Math.abs(h.lat - 39.7392) < 1e-4 && Math.abs(h.lon + 104.9903) < 1e-4;
  $('homenote').hidden = !placeholder;
  if (placeholder) $('homenote').innerHTML = `Leave times start from a placeholder in downtown Denver. <a href="#" onclick="show('more'); return false">Set your home under More</a> (Departure points).`;
}
function fillDepartures() {
  $('dep').innerHTML = SET.departures.map(d => `<option ${d.name === SET.default_departure ? 'selected' : ''}>${esc(d.name)}</option>`).join('');
}

/* ---------- Forecast dashboard ---------- */
let FC_FRESH = false;
async function loadForecast() {
  try { FC = await api('forecast'); } catch (e) { if (!FC) $('frows').innerHTML = `<p class="mute">${esc(e.message)}</p>`; return; }
  FC_FRESH = true; stash('forecast', FC);
  renderForecast(); route();
}
function asOfLine() {
  const ats = (FC || []).filter(r => r.summary && r.summary.as_of).map(r => r.summary.as_of);
  if (!FC_FRESH) return ats.length ? `Showing the forecast from ${clock(Math.min(...ats))} while a fresh one loads…` : '';
  if (!ats.length) return '';
  const oldest = Math.min(...ats);
  return `Forecast from ${clock(oldest)}.` + (Date.now() / 1000 - oldest > 5400 ? ' Open-Meteo hasn’t answered since then, so this is the last good forecast.' : '');
}

/* ---------- Best bet (top of the Forecast tab) ---------- */
async function loadOutlook() {
  try { OUT = await api('outlook'); } catch (e) { if (!OUT) $('hero').innerHTML = `<h3>Best bet</h3><p class="mute">${esc(e.message)}</p>`; return; }
  stash('outlook', OUT);
  renderHero();
}
// Inches with a proper double prime for display figures
const ip = v => inch(v).replace('"', '″');
// "1 hr 40 min" for the message board
const hrs = n => n >= 60 ? `${Math.floor(n / 60)} hr${n % 60 ? ` ${n % 60} min` : ''}` : `${n} min`;
// Short names riders use, for the day plates
const SHORT = { abasin: 'A-Basin', aspen_snowmass: 'Aspen', copper: 'Copper', winter_park: 'Winter Park' };
const FLAKE = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M12 2v20M3.3 7l17.4 10M3.3 17l17.4-10M9.5 3.5 12 6l2.5-2.5M9.5 20.5 12 18l2.5 2.5"/></svg>';

// The amber message board: when to leave and how long the drive is. Reserved for the next move.
function vmsLeave(l, name, action = '') {
  const sub = `${hrs(l.drive_min)} to ${esc(name)}${l.reason === 'traffic' ? ', ahead of the I-70 rush' : ''}`;
  return `<div class="vms"><div class="msg">Leave ${t12(l.leave_at)}<small>${sub}</small></div>${action}</div>`;
}

let HERO_SHOWN = null;
function renderHero() {
  const box = $('hero');
  const days = ((OUT && OUT.days) || []).filter(x => x.date >= today);
  if (!days.length) { box.innerHTML = '<div class="sign"><div class="sign-in"><p class="dim">No resort forecast yet. It shows here once Open-Meteo answers.</p></div></div>'; return; }
  const best = days.find(x => x.date === OUT.best_date) || days.reduce((a, b) => (b.score > a.score ? b : a));
  const sel = days.find(x => x.date === HERO_DATE) || best;
  const swap = HERO_SHOWN && HERO_SHOWN !== sel.date;
  HERO_SHOWN = sel.date;
  const powderIn = OUT.powder_in || 6;
  box.innerHTML = `
    <div class="sign"><div class="sign-in">
      <h2 class="rtab">${ARROW}${esc(sel.resort)}</h2>
      <div class="big"><span class="n">${ip(sel.fresh_in)}</span>
        <span class="u">fresh ${sel.date === today ? 'today' : 'by<br>' + dayName(sel.date, true)}${sel.fresh_in >= powderIn ? '<br><span class="powder">Powder day</span>' : ''}</span></div>
      <div class="facts"><span><b>${Math.round(sel.tmax_f)}°F</b> high</span><span><b>${Math.round(sel.gust_mph)} mph</b> gusts</span>
        ${sel.next_best ? `<span>next best <b>${esc(sel.next_best)}</b></span>` : ''}
        ${sel.busy ? `<span>your calendar: <b>${esc(sel.busy)}</b></span>` : ''}</div>
    </div></div>
    ${vmsLeave(sel.leave, SHORT[sel.id] || sel.resort, `<button onclick="going('${sel.date}', '${esc(sel.id)}', false, this)">I'm going</button>`)}
    <p class="goingmsg dim" role="status"></p>
    <div class="plates" role="group" aria-label="Pick a day">${days.map(x => `
      <button class="plate${x === sel ? ' on' : ''}${x.busy ? ' busy' : ''}" aria-pressed="${x === sel}" onclick="HERO_DATE='${x.date}'; renderHero()"${x.busy ? ` title="Busy: ${esc(x.busy)}"` : ''}>
        <span class="dn">${dayName(x.date)}</span><span class="dv">${ip(x.fresh_in)}</span>
        <span class="dr">${esc(SHORT[x.id] || x.resort)}</span>${x === best ? '<span class="best">Best</span>' : x.busy ? '<span class="best">Busy</span>' : ''}</button>`).join('')}</div>
    <div class="hero-links"><a href="#" onclick="planDay('${sel.date}'); return false">All resorts ${sel.date === today ? 'today' : 'on ' + dayName(sel.date, true)} ${ARROW_R}</a>
      <span>${monthDay(sel.date)}</span></div>
    ${(OUT.alerts || []).map(x => `<div class="alert">${FLAKE}<span><b>Powder alert:</b> ${esc(x.resort)}, ${x.snow_in}″ from ${dayLabel(x.first_day)}</span></div>`).join('')}`;
  if (swap) box.querySelector('.vms').classList.add('swap');
}
function planDay(date) {
  $('d').value = date;
  location.hash = '';
  show('plan'); rank();
  scrollTo(0, 0);
}
function reportLine(row) {
  const rep = row.reported || {}, sn = row.snotel;
  const bits = [];
  if (rep.status) bits.push(esc(rep.status));
  if (rep.base_in) bits.push(`base ${inch(rep.base_in)}`);
  if (rep.new_24h_in) bits.push(`${inch(rep.new_24h_in)} in 24h`);
  if (!rep.base_in && sn) bits.push(`SNOTEL ${inch(sn.depth_in)} on the ground`);
  return bits.join(SEP);
}
function snowTip(d, past) {
  let s = `<b>${dayLabel(d.date)}</b>: ${inch(d.snow_in)}${past ? ' (modelled)' : ''}`;
  if (!past && d.snow_in > 0) s += `<br>day ${inch(d.snow_day_in)} · night ${inch(d.snow_night_in)}`;
  if (d.quality) s += `<br>${esc(d.quality)}`;
  if (d.rain_in > 0.05) s += `<br>rain ${d.rain_in.toFixed(2)}"`;
  if (d.tmax_f != null) s += `<br>${Math.round(d.tmax_f)}° / ${Math.round(d.tmin_f)}°F`;
  return s;
}
function renderForecast() {
  if (!FC) return;
  const key = $('fsort').value;
  const rows = [...FC].sort((a, b) => key === 'name' ? a.name.localeCompare(b.name) : ((b.summary || {})[key] || 0) - ((a.summary || {})[key] || 0));
  const kk = key === 'name' ? 'next5_in' : key;
  const col = (k, v) => `<div class="tot t-${k}${k === kk ? ' k-on' : ''}">${v}</div>`;
  $('fhead').textContent = { last5_in: 'Last 5 days', days6_10_in: 'Days 6-10', days11_15_in: 'Days 11-15' }[kk] || 'Next 5 days';
  $('frows').innerHTML = `<div class="frow head"><div class="name">Resort</div>${col('last5_in', 'Last 5')}${col('next5_in', 'Next 5')}${col('days6_10_in', '6-10')}${col('days11_15_in', '11-15')}<div class="strip">Daily snow, today marked</div></div>` +
    rows.map(r => r.error ? `<div class="frow"><div class="name">${esc(r.name)}</div><div class="mute err">No forecast yet: Open-Meteo didn’t answer (${esc(r.error)}). It tries again in a minute.</div></div>` :
      `<a class="frow" href="#resort/${r.id}">
        <div class="name">${esc(r.name)}</div>
        <div class="rep">${r.pass === 'keystone' ? 'Keystone pass' + (reportLine(r) ? SEP : '') : ''}${reportLine(r)}</div>
        ${col('last5_in', ip(r.summary.last5_in))}${col('next5_in', `<b>${ip(r.summary.next5_in)}</b>`)}
        ${col('days6_10_in', ip(r.summary.days6_10_in))}${col('days11_15_in', ip(r.summary.days11_15_in))}
        <div class="strip chart" id="strip_${r.id}"></div></a>`).join('');
  for (const r of rows) {
    if (r.error) continue;
    const s = r.summary;
    const bars = [...s.past.map(d => ({ v: d.snow_in, fill: 'var(--snow-past)', tip: snowTip(d, true) })),
                  ...s.future.map((d, i) => ({ v: d.snow_in, fill: i < 10 ? 'var(--snow)' : 'var(--snow-low)', tip: snowTip(d, false) }))];
    const el = $('strip_' + r.id);
    const bands = weekendBands([...s.past, ...s.future].map(d => d.date));
    Charts.add(() => barChart(el, bars, { axis: false, height: innerWidth <= 720 ? 30 : 40, todayIndex: s.past.length, floorMax: 4, bands, title: `${r.name} daily snow` }));
  }
  $('fasof').textContent = asOfLine();
}

/* ---------- Daily Snow ---------- */
async function loadDailySnow(refresh) {
  const box = $('dailysnow');
  if (refresh) box.innerHTML = '<p class="mute">Rewriting the Daily Snow…</p>';
  let r;
  try { r = await api('daily-snow' + (refresh ? '?refresh=true' : '')); } catch (e) { r = { error: e.message }; }
  // Not connected to Claude: a quiet line under the forecast instead of an empty card at the top
  const off = r.error && /connect claude/i.test(r.error);
  box.hidden = off; $('dsoff').hidden = !off;
  if (off) { $('dsoff').innerHTML = `Daily Snow is off. <a href="#" onclick="show('more'); return false">Connect Claude under More</a> to get it each morning.`; return; }
  if (r.error) { box.innerHTML = `<h3>Daily Snow</h3><p class="mute">${esc(r.error)}</p>`; return; }
  const lines = r.text.split('\n'), head = lines.shift();
  box.classList.add('collapsed');
  box.innerHTML = `<div class="row spread"><h3>Daily Snow <span class="small">written ${esc(r.created)}</span></h3>
     <div class="row"><button onclick="$('dailysnow').classList.toggle('collapsed')">More / less</button>
     <button onclick="if(confirm('Rewrite today\\'s Daily Snow? It makes one Claude call.'))loadDailySnow(true)">Rewrite</button></div></div>
    <div class="headline">${esc(head)}</div><div class="body">${esc(lines.join('\n').trim())}</div>`;
}

/* ---------- Resort detail ---------- */
function route() {
  const m = location.hash.match(/^#resort\/([\w-]+)(?:\/(base|mid|summit))?/);
  if (m) { if ($('forecast').classList.contains('on') === false) paint('forecast'); openResort(m[1], m[2] || 'mid'); }
  else { $('fdetail').hidden = true; $('flist').hidden = false; }
}
async function openResort(id, band) {
  $('flist').hidden = true; const box = $('fdetail'); box.hidden = false;
  box.innerHTML = '<p class="mute">Loading…</p>';
  let d;
  try { d = await api(`resort/${id}?band=${band}`); } catch (e) { box.innerHTML = `<button onclick="location.hash=''">Back</button><p>${esc(e.message)}</p>`; return; }
  const future = d.daily.filter(x => x.date >= today).slice(0, 15);
  const past = d.daily.filter(x => x.date < today).slice(-5);
  const rep = d.reported || {}, sn = d.snotel || {};
  const total = (a, b) => ip(future.slice(a, b).reduce((s, x) => s + x.snow_in, 0));
  const ledger = [['Reported base', rep.base_in != null ? ip(rep.base_in) : null], ['Reported last 24 hours', rep.new_24h_in != null ? ip(rep.new_24h_in) : null],
    ['Season total', rep.season_in ? ip(rep.season_in) : null], ['Lifts open', rep.lifts_total != null ? `${rep.lifts_open} of ${rep.lifts_total}` : null],
    ['Terrain open', rep.terrain_open_pct != null ? rep.terrain_open_pct + '%' : null],
    [`SNOTEL snow depth${sn.as_of ? ', ' + monthDay(String(sn.as_of).slice(0, 10)) : ''}`, sn.depth_in != null ? ip(sn.depth_in) : null],
    ['SNOTEL change, last 72 hours', sn.new_72h_in != null ? ip(sn.new_72h_in) : null]].filter(([, v]) => v != null && v !== '');
  const snow48 = d.next48.reduce((s, h) => s + h.snow_in, 0);
  box.innerHTML = `
   <div class="rhead"><button onclick="location.hash=''">${ARROW_L}All resorts</button>
    <div class="seg" role="group" aria-label="Elevation">${['base', 'mid', 'summit'].map(b => `<button class="${b === band ? 'on' : ''}" aria-pressed="${b === band}" onclick="location.hash='resort/${id}/${b}'">${b[0].toUpperCase() + b.slice(1)} ${d.elevations[b].toLocaleString()} ft</button>`).join('')}</div></div>
   <div class="split rsplit">
    <div class="col-a">
     <div class="sign"><div class="sign-in">
       <h2 class="rtab">${ARROW}${esc(d.resort.name)}</h2>
       <div class="big"><span class="n">${total(0, 5)}</span><span class="u">next 5 days<br>${band}, ${d.elevations[band].toLocaleString()} ft</span></div>
       <div class="facts"><span>days 6-10 <b>${total(5, 10)}</b></span><span>days 11-15 <b>${total(10, 15)}</b>, less sure</span></div>
     </div></div>
     ${vmsLeave(d.leave_today, SHORT[id] || d.resort.name, `<button onclick="going('${today}', '${esc(id)}', false, this)">I'm going</button>`)}
     <p class="goingmsg dim" role="status"></p>
    </div>
    <div class="col-b"><div class="panel"><h3>On the mountain</h3>
     ${ledger.length ? `<dl class="ledger">${ledger.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl>` : '<p class="mute">No report from the resort right now.</p>'}
     ${rep.status ? `<p class="fine">Resort status: ${esc(rep.status)}${rep.conditions ? SEP + esc(rep.conditions) : ''}</p>` : ''}
     ${d.as_of ? `<p class="fine">Forecast from ${clock(d.as_of)}.${Date.now() / 1000 - d.as_of > 5400 ? ' Open-Meteo hasn’t answered since then, so this is the last good forecast.' : ''}</p>` : ''}</div></div>
   </div>
   <div class="card"><h3>Daily snow, next 15 days <span class="small">(${band}, ${d.elevations[band].toLocaleString()} ft; 6am to 6am)</span></h3>
     <div class="legend"><span><i class="box" style="background:var(--snow-past)"></i>Last 5 days (modelled)</span><span><i class="box" style="background:var(--snow)"></i>Days 1-10</span><span><i class="box" style="background:var(--snow-low)"></i>Days 11-15 (low confidence)</span><span><i class="box wkend"></i>Weekend</span></div>
     <div class="chart" id="c_daily"></div></div>
   <div class="card"><h3>Getting there today</h3>
     ${leaveText(d.leave_today, true)}${trafficText(d.traffic)}
     ${d.transit.length ? '<ul>' + d.transit.map(x => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a>: <span class="mute">${esc(x.note)}</span></li>`).join('') + '</ul>' : ''}
     <p>${d.info.webcams_url ? `<a href="${esc(d.info.webcams_url)}" target="_blank" rel="noopener">Webcams</a>` : ''}
       ${d.info.openskimap_url ? `${SEP}<a href="${esc(d.info.openskimap_url)}" target="_blank" rel="noopener">Trail map (OpenSkiMap)</a>` : ''}
       ${d.info.beginner_pct != null ? `${SEP}<span class="mute">${d.info.beginner_pct}% of runs are green or blue</span>` : ''}</p></div>
   ${d.info.webcam_images.length ? `<div class="card"><h3>Webcams right now</h3><div class="cams">${d.info.webcam_images.map(u =>
     `<a href="${esc(d.info.webcams_url || u)}" target="_blank" rel="noopener"><img loading="lazy" width="640" height="360" alt="${esc(d.resort.name)} webcam" src="${esc(u)}${u.includes('?') ? '&' : '?'}t=${Math.floor(Date.now() / 300000)}"></a>`).join('')}</div></div>` : ''}
   <div class="card"><h3>Next 48 hours: snow per hour</h3>${snow48 >= 0.05 ? '<div class="chart" id="c_h_snow"></div>' : '<p class="mute">No snow in the next 48 hours.</p>'}
     <h3 style="margin-top:12px">Next 48 hours: temperature (&deg;F)</h3><div class="chart" id="c_h_temp"></div></div>
   <div class="card"><h3>Model check: running snow total</h3>
     <div class="legend">${d.models.map((m, i) => `<span><i style="background:var(--s${i + 1})"></i>${esc(m)}</span>`).join('')}</div>
     <div class="chart" id="c_models"></div>
     <p class="small">When the two lines split apart, the forecast is uncertain. ECMWF ends a day earlier than GFS.</p>
     <p class="small">${Object.entries(d.accuracy).some(([, v]) => v.days) ? 'Checked against SNOTEL, last 30 days: ' + Object.entries(d.accuracy).map(([m, v]) =>
       `${esc(m)} ${v.mean_miss_in != null ? 'off by ' + v.mean_miss_in + '" water a day' : 'no data'} over ${v.days} wet days, weight ${Math.round(v.weight * 100)}%`).join(SEP)
       : 'Each model gets checked against SNOTEL every day; the blend leans toward the better one once there are 5 wet days to judge.'}</p></div>
   <div class="card wrap"><h3>Day by day</h3><table class="daytable">
     <tr><th>Day</th><th class="num">Snow</th><th class="num">Day / night</th><th>Quality</th><th class="num">High / low</th><th class="num">Wind / gust</th><th class="num">Freezing level</th></tr>
     ${future.map(x => `<tr><td>${dayLabel(x.date)}</td><td class="num"><b>${inch(x.snow_in)}</b></td><td class="num">${inch(x.snow_day_in)} / ${inch(x.snow_night_in)}</td>
       <td>${x.quality === 'rain' || x.quality === 'mixed' ? `<span class="warnnote">${esc(x.quality)}</span>` : esc(x.quality || '')}</td>
       <td class="num">${Math.round(x.tmax_f)}° / ${Math.round(x.tmin_f)}°</td><td class="num">${Math.round(x.wind_mph)} / ${Math.round(x.gust_mph)} mph</td>
       <td class="num">${x.freezing_ft ? x.freezing_ft.toLocaleString() + ' ft' : '-'}</td></tr>`).join('')}</table></div>`;

  const bars = [...past.map(x => ({ v: x.snow_in, fill: 'var(--snow-past)', tip: snowTip(x, true) })),
                ...future.map((x, i) => ({ v: x.snow_in, fill: i < 10 ? 'var(--snow)' : 'var(--snow-low)', tip: snowTip(x, false) }))];
  const labels = [...past, ...future].map(x => dayLabel(x.date));
  const bands = weekendBands([...past, ...future].map(x => x.date));
  Charts.add(() => barChart($('c_daily'), bars, { height: 170, labels, labelEvery: innerWidth < 600 ? 3 : 1, todayIndex: past.length, floorMax: 4,
    bands, valueLabels: true, title: 'Daily snow' }));

  const cum = name => { let s = 0; return future.map(x => { const v = x.models[name]; if (v == null) return null; s += v; return Math.round(s * 10) / 10; }); };
  const series = d.models.map((m, i) => ({ name: m, color: `var(--s${i + 1})`, values: cum(m) }));
  Charts.add(() => lineChart($('c_models'), series, { height: 170, labels: future.map(x => dayLabel(x.date)), labelEvery: innerWidth < 600 ? 3 : 2,
    unit: '"', min: 0, floorMax: 4, directLabels: true, title: 'Model running totals',
    tip: i => `<b>${dayLabel(future[i].date)}</b>` + series.map(s => `<br>${esc(s.name)}: ${s.values[i] == null ? 'no data' : inch(s.values[i])}`).join('') }));

  const hrs = d.next48, hl = hrs.map(h => { const x = new Date(h.time); return x.getHours() === 0 ? DOW[x.getDay()] : (x.getHours() % 12 || 12) + (x.getHours() < 12 ? 'a' : 'p'); });
  const htip = h => { const x = new Date(h.time); return `<b>${DOW[x.getDay()]} ${t12(h.time.slice(11, 16))}</b><br>snow ${h.snow_in.toFixed(2)}"${h.rain_in > 0.01 ? `<br>rain ${h.rain_in.toFixed(2)}"` : ''}<br>${h.temp_f}°F · gust ${h.gust_mph} mph`; };
  if ($('c_h_snow')) Charts.add(() => barChart($('c_h_snow'), hrs.map(h => ({ v: h.snow_in, tip: htip(h) })), { height: 120, labels: hl, labelEvery: 6, floorMax: 0.5, title: 'Hourly snow' }));
  Charts.add(() => lineChart($('c_h_temp'), [{ name: 'Temperature', color: 'var(--s2)', values: hrs.map(h => h.temp_f) }],
    { height: 120, labels: hl, labelEvery: 6, unit: '°', title: 'Hourly temperature', tip: i => htip(hrs[i]) }));
  scrollTo(0, 0);
}

/* ---------- Radar ---------- */
let MAP = null, RLAYERS = [], RIDX = 0, RTIMER = null, PINS = [];
// Resorts close together (Keystone and A-Basin, Eldora and Winter Park) would cover each other's tabs: working
// top to bottom, a tab that would land on one already placed drops below it, with a white leader back up to its point.
function declutterPins() {
  const placed = [];
  const items = PINS.map(m => ({ el: m.getElement() && m.getElement().firstElementChild, p: MAP.latLngToContainerPoint(m.getLatLng()) }))
    .filter(x => x.el).sort((a, b) => a.p.y - b.p.y);
  for (const x of items) {
    x.el.style.marginTop = '0px'; x.el.style.setProperty('--dy', '0px');
    const w = x.el.offsetWidth, h = x.el.offsetHeight;
    let top = x.p.y - 10;
    for (let i = 0; i < 12; i++) {
      const hit = placed.find(o => x.p.x < o.r + 4 && x.p.x + w > o.l - 4 && top < o.b + 3 && top + h > o.t - 3);
      if (!hit) break;
      top = hit.b + 3;
    }
    const dy = Math.round(top - (x.p.y - 10));
    x.el.style.marginTop = dy + 'px'; x.el.style.setProperty('--dy', dy + 'px');
    placed.push({ l: x.p.x, r: x.p.x + w, t: top, b: top + h });
  }
}
const RFRAMES = ['m50m', 'm40m', 'm30m', 'm20m', 'm10m', ''];
function loadLeaflet() {
  return new Promise((ok, fail) => {
    const css = document.createElement('link'); css.rel = 'stylesheet';
    css.href = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css'; document.head.appendChild(css);
    const s = document.createElement('script'); s.src = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js';
    s.onload = ok; s.onerror = () => fail(new Error('Could not load the map library')); document.head.appendChild(s);
  });
}
async function loadRadar() {
  if (MAP) { setTimeout(() => MAP.invalidateSize(), 50); return; }
  try { if (!window.L) await loadLeaflet(); } catch (e) { $('map').textContent = e.message; return; }
  MAP = L.map('map').setView([39.65, -106.2], 8);
  // With a CARTO key (add-on option) use CARTO's basemap, light or dark to match the page. Without one fall back
  // to OpenStreetMap, which returns an "Access blocked" picture when a request has no Referer (Home Assistant
  // ingress sends none), so referrerPolicy 'origin' makes the tile requests carry the page's origin.
  const cfg = await api('map').catch(() => ({ carto_key: '' }));
  if (cfg.carto_key) {
    const style = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark_all' : 'voyager';
    L.tileLayer(`https://basemaps.cartocdn.com/rastertiles/${style}/{z}/{x}/{y}{r}.png?key=${encodeURIComponent(cfg.carto_key)}`,
      { maxZoom: 13, attribution: '&copy; OpenStreetMap contributors &copy; CARTO' }).addTo(MAP);
  } else {
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      { maxZoom: 13, referrerPolicy: 'origin', attribution: '&copy; OpenStreetMap contributors' }).addTo(MAP);
  }
  RLAYERS = RFRAMES.map(f => L.tileLayer(`https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913${f ? '-' + f : ''}/{z}/{x}/{y}.png`,
    { opacity: 0, zIndex: 10, attribution: 'Radar: IEM NEXRAD' }).addTo(MAP));
  if (!FC) FC = await api('forecast').catch(() => []);
  for (const r of FC) {
    if (r.error) continue;
    PINS.push(L.marker([r.lat, r.lon], { icon: L.divIcon({ className: '', html: `<div class="snowpin">${esc(SHORT[r.id] || r.name)} ${ip(r.summary.next5_in)}</div>`, iconSize: null, iconAnchor: [0, 10] }) })
      .addTo(MAP).on('click', () => { show('forecast'); location.hash = 'resort/' + r.id; }));
  }
  // Frame every resort; the tabs hang to the right of their point, so leave room on that side
  const pts = FC.filter(r => !r.error).map(r => [r.lat, r.lon]);
  if (pts.length) MAP.fitBounds(pts, { paddingTopLeft: [16, 24], paddingBottomRight: [120, 24], maxZoom: 9 });
  MAP.on('zoomend', declutterPins);
  setTimeout(declutterPins, 50);
  // Reduced motion: show the latest frame and let Play start the loop
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) { RIDX = RLAYERS.length - 1; radarFrame(); $('rplay').textContent = 'Play'; }
  else startRadar();
}
function radarFrame() {
  RLAYERS.forEach((l, i) => l.setOpacity(i === RIDX ? 0.65 : 0));
  const mins = [50, 40, 30, 20, 10, 0][RIDX];
  $('rtime').textContent = mins ? `about ${mins} min ago` : 'latest';
  RIDX = (RIDX + 1) % RLAYERS.length;
}
function startRadar() { radarFrame(); RTIMER = setInterval(radarFrame, 700); $('rplay').textContent = 'Pause'; }
function toggleRadar() {
  if (RTIMER) { clearInterval(RTIMER); RTIMER = null; RIDX = RLAYERS.length - 1; radarFrame(); $('rplay').textContent = 'Play'; }
  else startRadar();
}

/* ---------- Plan ---------- */
async function rank() {
  const t = $('t'); t.innerHTML = '<tr><td>Loading…</td></tr>';
  const q = `best-days?date=${$('d').value}&skis=${$('skis').checked}&departure=${encodeURIComponent($('dep').value)}`;
  let rows;
  try { rows = await api(q); } catch (e) { t.innerHTML = `<tr><td>${esc(e.message)}</td></tr>`; return; }
  t.innerHTML = '<tr><th>Resort</th><th class="num">Score</th><th class="num">Fresh</th><th class="num">Gust</th><th class="num">High</th><th class="num">Base</th><th class="num">Lifts</th><th>Leave</th></tr>' +
    rows.map(r => r.error ? `<tr><td>${esc(r.resort)}</td><td colspan=7>${esc(r.error)}</td></tr>` :
      `<tr${r.not_open ? ' class="notopen"' : ''}><td>${esc(r.resort)}${r.not_open ? ' <span class="mute">not open yet</span>' : ''}</td><td class="num">${r.not_open ? '-' : r.score}</td><td class="num">${inch(r.fresh_in)}</td><td class="num">${Math.round(r.gust_mph)}</td><td class="num">${Math.round(r.tmax_f)}°</td>
       <td class="num">${r.snowpack ? inch(r.snowpack.depth_in) : '-'}</td><td class="num">${r.live && r.live.lifts_total != null ? r.live.lifts_open + '/' + r.live.lifts_total : '-'}</td>
       <td>${t12(r.leave.leave_at)} <span class="mute">(${hm(r.leave.drive_min)})</span></td></tr>`).join('');
  const top = rows.find(r => !r.error && !r.not_open) || rows.find(r => !r.error);
  $('pick').innerHTML = top ? `<div class="pickgrid">
    <div class="sign"><div class="sign-in">
      <h2 class="rtab">${ARROW}${esc(top.resort)}</h2>
      <div class="big"><span class="n">${ip(top.fresh_in)}</span><span class="u">fresh ${$('d').value === today ? 'today' : 'by<br>' + dayName($('d').value, true)}</span></div>
      <div class="facts"><span><b>${Math.round(top.tmax_f)}°F</b> high</span><span><b>${Math.round(top.gust_mph)} mph</b> gusts</span><span>score <b>${top.score}</b></span></div>
    </div></div>
    <div class="col-a">
      ${vmsLeave(top.leave, SHORT[top.id] || top.resort, `<button onclick="going($('d').value, '${esc(top.id)}', $('skis').checked, this)">I'm going</button>`)}
      <p class="goingmsg dim" role="status"></p>
      <div class="panel">${leaveText(top.leave, true)}${trafficText(top.traffic)}
        <p><b>Wear</b> (feels like ${top.gear.feels_like_f}°F): ${top.gear.wear.map(esc).join(', ')}</p>
        ${top.gear.notes.length ? `<p><b>Also</b>: ${top.gear.notes.map(esc).join('; ')}</p>` : ''}
        ${top.beginner_pct != null ? `<p class="mute">${top.beginner_pct}% of runs are green or blue.</p>` : ''}
        ${top.transit.length ? '<p><b>Shuttle / transit</b></p><ul>' + top.transit.map(x => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a>: <span class="mute">${esc(x.note)}</span></li>`).join('') + '</ul>' : ''}</div>
    </div></div>` : '';
}
function alertLines(al, limit) {
  const now = al.filter(a => a.status !== 'later'), later = al.length - now.length;
  const line = a => {
    const road = [a.road, a.direction].filter(Boolean).join(' ');
    const what = a.what ? a.what.charAt(0).toLowerCase() + a.what.slice(1) : a.kind.toLowerCase();
    return `<li>${esc(road)}${a.where ? ', ' + esc(a.where) : ''}: ${esc(what)} <span>${esc(a.when)}${a.status === 'soon' ? ' (soon)' : ''}</span></li>`;
  };
  let h = now.length ? '<ul>' + now.slice(0, limit).map(line).join('') + '</ul>' : '';
  if (now.length > limit) h += `<p>+${now.length - limit} more right now or soon</p>`;
  if (later) h += `<p>${later} more planned later this week</p>`;
  return h ? `<div class="vms list" role="status">${h}</div>` : '';
}
function trafficText(tr) {
  if (!tr) return '';
  let s = '';
  if (tr.waze) s += `<p><b>Waze right now:</b> ${hm(tr.waze.minutes)}${tr.waze.route ? ' via ' + esc(tr.waze.route) : ''}.</p>`;
  const al = (tr.cotrip && tr.cotrip.alerts) || [];
  if (al.length) s += alertLines(al, 3);
  else if (tr.cotrip && tr.cotrip.configured) s += `<p class="mute">No CDOT alerts on ${esc(tr.roads.join(', '))} right now.</p>`;
  return s;
}
async function loadRoads() {
  const box = $('roads');
  let t;
  try { t = await api('traffic'); } catch (e) { box.innerHTML = `<h3>Roads right now</h3><p class="mute">${esc(e.message)}</p>`; return; }
  const al = t.cotrip.alerts || [];
  let h = '<h3>Roads right now</h3>';
  if (!t.cotrip.configured) h += '<p class="mute">Add a free COtrip key (manage-api.cotrip.org) in the add-on Configuration tab for live CDOT incidents, chain laws and closures.</p>';
  else if (t.cotrip.error && !al.length) h += `<p class="due">COtrip: ${esc(t.cotrip.error)}</p>`;
  else h += al.length ? alertLines(al, 6) : '<p>No CDOT incidents or closures on your routes.</p>';
  const tt = t.travel_times.filter(x => x.minutes > 0 && !/VMS/i.test(x.name));
  if (tt.length) h += '<p class="small">' + tt.slice(0, 6).map(x => `${esc(x.name)}: ${hm(Math.round(x.minutes))}${x.usual_minutes ? ` (usually ${hm(Math.round(x.usual_minutes))})` : ''}`).join(SEP) + '</p>';
  const w = Object.entries(t.waze).filter(([, v]) => v);
  h += w.length ? '<p class="small">Waze now: ' + w.map(([id, v]) => `${esc(rname(id))} ${hm(v.minutes)}`).join(SEP) + '</p>'
               : `<p class="small">${t.waze_sensors.length ? 'Waze sensors found, but none matched a resort: pick them under More.' : 'No Waze Travel Time sensors found in Home Assistant.'}</p>`;
  box.innerHTML = h;
}

function leaveText(l, rest = false) {
  if (rest) {
    let s = l.reason === 'traffic' ? `<p>Be on I-70 by <b>${t12(l.on_i70_by)}</b>, ahead of the ${l.powder ? 'powder-day ' : ''}rush, and you're there about ${t12(l.arrive_at)}. Leave at 7:00am instead and it's about ${hm(l.if_later.drive_min)}.</p>`
                                   : `<p>That gets you on the lifts by ${t12(SET.arrive_by)}.</p>`;
    if (l.home) s += `<p class="mute">Heading home: leave before ${t12(l.home.leave_before)} or after ${t12(l.home.or_after)}. At 3pm it's about ${hm(l.home.drive_min_at_3pm)} (vs ${hm(l.home.base_min)} with no traffic).</p>`;
    return s;
  }
  let s = l.reason === 'traffic'
    ? `<p>Leave at <b>${t12(l.leave_at)}</b> to be on I-70 by ${t12(l.on_i70_by)}, ahead of the ${l.powder ? 'powder-day ' : ''}rush. You'll get there about ${t12(l.arrive_at)} (${hm(l.drive_min)}).</p>
       <p class="mute">Leave at 7:00am instead and it's about ${hm(l.if_later.drive_min)}.</p>`
    : `<p>Leave at <b>${t12(l.leave_at)}</b> to be on the lifts by ${t12(SET.arrive_by)}. Drive about ${hm(l.drive_min)}.</p>`;
  if (l.home) s += `<p class="mute">Heading home: leave before ${t12(l.home.leave_before)} or after ${t12(l.home.or_after)}. At 3pm it's about ${hm(l.home.drive_min_at_3pm)} (vs ${hm(l.home.base_min)} with no traffic).</p>`;
  return s;
}
async function askClaude() {
  $('ans').textContent = 'Thinking…';
  try {
    const r = await api('ask', { method: 'POST', body: JSON.stringify({ question: $('q').value || 'Where should I go?', date: $('d').value, skis: $('skis').checked, departure: $('dep').value }) });
    $('ans').textContent = r.answer;
  } catch (e) { $('ans').textContent = e.message; }
}

/* ---------- Season log ---------- */
async function going(date, resortId, skis = false, btn = null) {
  const r = await api('going', { method: 'POST', body: JSON.stringify({ date, resort_id: resortId, skis }) }).catch(e => ({ note: e.message }));
  const host = btn && (btn.closest('.vms') ? btn.closest('.vms').parentElement : btn.parentElement);
  const msg = host && host.querySelector('.goingmsg');
  if (msg) msg.textContent = r.note || '';
}

async function loadStats() {
  const s = await api('stats').catch(() => null);
  if (!s) return;
  const t = s.this_season, l = s.last_season_to_date, full = s.last_season;
  const row = (k, label, fmt) => `<tr><td>${label}</td><td class="num"><b>${fmt(t[k])}</b></td><td class="num">${fmt(l[k])}</td><td class="num mute">${fmt(full[k])}</td></tr>`;
  const n = v => v == null ? '-' : Number(v).toLocaleString();
  $('statsbox').innerHTML = `<div class="row spread"><h3>Season stats</h3><button class="primary" onclick="Recap.open()">Season recap</button></div><div class="wrap"><table>
     <tr><th></th><th class="num">This season</th><th class="num">Last season, same date</th><th class="num">All last season</th></tr>
     ${row('days', 'Days', n)}${row('board_days', 'Board days', n)}${row('ski_days', 'Ski days', n)}
     ${row('vertical_ft', 'Vertical (ft)', n)}${row('top_speed_mph', 'Top speed (mph)', n)}${row('distance_mi', 'Distance (mi)', n)}${row('hours', 'Hours on snow', n)}</table></div>
     ${s.ski_progress.length > 1 ? '<h3 style="margin-top:12px">Skiing: top speed per ski day (mph)</h3><div class="chart" id="c_ski"></div>' : ''}
     <p class="small">Vertical, speed, distance and hours come from Garmin (connect it under More).</p>`;
  const sp = s.ski_progress.filter(x => x.top_speed_mph != null);
  if (sp.length > 1) Charts.add(() => lineChart($('c_ski'), [{ name: 'Top speed', color: 'var(--s1)', values: sp.map(x => x.top_speed_mph) }],
    { height: 130, labels: sp.map(x => x.date.slice(5)), labelEvery: Math.max(1, Math.ceil(sp.length / 8)), min: 0, unit: '',
      title: 'Ski top speed by day', tip: i => `<b>${esc(sp[i].date)}</b><br>${sp[i].top_speed_mph} mph${sp[i].vertical_ft ? `<br>${Number(sp[i].vertical_ft).toLocaleString()} ft vertical` : ''}` }));
}

async function loadDays() {
  const d = await api('days');
  if (!d.length) { $('days').innerHTML = '<tr><td class="mute">No days yet. Add one above, or connect Garmin under More and your rides come in on their own.</td></tr>'; return; }
  $('days').innerHTML = '<tr><th>Date</th><th>Resort</th><th>On</th><th class="num">Vertical</th><th>Notes</th><th></th></tr>' +
    d.map(x => `<tr><td>${new Date(x.date + 'T12:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</td><td>${esc(rname(x.resort_id))}</td><td><button title="Switch board / skis" onclick="flipDay(${x.id}, '${x.equipment === 'board' ? 'ski' : 'board'}')">${x.equipment === 'board' ? 'Board' : 'Skis'}</button></td><td class="num">${x.vertical_ft ? Number(x.vertical_ft).toLocaleString() + ' ft' : ''}</td><td>${esc(x.notes)}${x.garmin_ids ? '<span class="badge">Garmin</span>' : ''}</td>
      <td><button onclick="delDay(${x.id})">Delete</button></td></tr>`).join('');
}
/* Garmin import: ski and snowboard activities become days automatically */
async function loadGarmin(msg) {
  const g = await api('garmin').catch(() => ({ connected: false }));
  const last = g.last_sync || {};
  let h = '<h3>Garmin</h3>';
  const form = `<p class="mute">Sign in once and every Ski or Snowboard activity you record becomes a day here, with resort, board or skis, and vertical. Your password is only used to sign in and isn't saved.</p>
    <div class="row"><input id="gemail" type="email" placeholder="Garmin email" autocomplete="username" spellcheck="false" aria-label="Garmin email">
    <input id="gpass" type="password" placeholder="Garmin password" autocomplete="current-password" aria-label="Garmin password"><button onclick="garminConnect()">Connect Garmin</button></div>`;
  if (g.needs_mfa) h += `<p>Garmin sent you a verification code.</p><div class="row"><input id="gcode" inputmode="numeric" autocomplete="one-time-code" spellcheck="false" placeholder="123456" aria-label="Garmin verification code"><button onclick="garminMfa()">Verify</button></div>`;
  else if (g.connected) {
    h += `<p>Connected${g.source === 'workout tracker' ? ' (using the Workout Tracker’s Garmin login)' : ''}.
      ${last.at ? `Last checked ${esc(last.at)}${last.added ? `, ${last.added} new` : ''}.` : ''}
      <button onclick="garminSync()">Sync now</button>${g.source === 'own' ? ' <button onclick="garminDisconnect()">Disconnect</button>' : ''}</p>`;
    if (last.error) h += `<p class="due">${esc(last.error)}</p>` + form;
  } else h += form;
  if (msg) h += `<p class="mute">${esc(msg)}</p>`;
  $('garminbox').innerHTML = h;
}
async function garminConnect() {
  const r = await api('garmin/connect', { method: 'POST', body: JSON.stringify({ email: $('gemail').value, password: $('gpass').value }) }).catch(e => ({ error: e.message }));
  loadGarmin(r.error || (r.needs_mfa ? '' : 'Connected. Your Garmin days are being imported.')); loadDays();
}
async function garminMfa() {
  const r = await api('garmin/mfa', { method: 'POST', body: JSON.stringify({ code: $('gcode').value }) }).catch(e => ({ error: e.message }));
  loadGarmin(r.error || 'Connected.'); loadDays();
}
async function garminSync() {
  $('garminbox').insertAdjacentHTML('beforeend', '<p class="mute">Checking Garmin…</p>');
  const r = await api('garmin/sync', { method: 'POST' }).catch(e => ({ error: e.message }));
  loadGarmin(r.error || `${r.added} new day${r.added === 1 ? '' : 's'} imported.`); loadDays();
}
async function garminDisconnect() { if (confirm('Disconnect Garmin from this add-on?')) { await api('garmin/disconnect', { method: 'POST' }); loadGarmin(); } }

async function addDay() {
  await api('days', { method: 'POST', body: JSON.stringify({ date: $('ld').value, resort_id: $('lr').value, equipment: $('le').value,
    vertical_ft: $('lv').value ? +$('lv').value : null, notes: $('ln').value }) });
  $('ln').value = ''; $('lv').value = ''; loadDays();
}
async function flipDay(id, eq) { await api('days/' + id, { method: 'PATCH', body: JSON.stringify({ equipment: eq }) }); loadDays(); }
async function delDay(id) { if (confirm('Delete this day?')) { await api('days/' + id, { method: 'DELETE' }); loadDays(); } }

/* ---------- Gear ---------- */
async function loadGear() {
  const g = await api('gear');
  $('upkeep').innerHTML = '<h3>Upkeep</h3>' + Object.entries(g).map(([eq, k]) => `<p><b>${eq === 'board' ? 'Board' : 'Skis'}</b>: ` +
    Object.entries(k).map(([kind, u]) => `<span class="${u.due ? 'due' : ''}">${kind} ${u.days_since}/${u.every} days${u.due ? ' (due)' : ''}</span>`).join(SEP) + '</p>').join('');
}
async function addService() { await api('gear', { method: 'POST', body: JSON.stringify({ date: $('gd').value, equipment: $('ge').value, kind: $('gk').value }) }); loadGear(); }

/* ---------- Settings ---------- */
const FIELDS = [['arrive_by', 'On the lifts by (HH:MM)'], ['buffer_min', 'Buffer for parking and boots (min)', 'n'],
  ['phone_service', 'Phone notify service'], ['tts_entity', 'TTS entity (tts.*)'], ['speaker_entity', 'Speaker (media_player.*)'],
  ['wake_time', 'Powder wake-up time (HH:MM)'], ['tracker_entity', 'Phone tracker (device_tracker.*)'],
  ['climate_entity', 'Thermostat (climate.*)'], ['normal_temp_f', 'Normal temperature (F)', 'n'],
  ['outlook_time', 'Thursday weekend outlook at (HH:MM)'], ['packing_todo', 'Packing list (todo.*, blank = shopping list)'],
  ['calendar_entity', 'Calendar for free days (calendar.*, blank = off)']];
async function loadSettings() {
  const r = await api('settings'); const s = r.settings; SET = s;
  $('setbox').innerHTML = `<h3>Settings</h3>
    ${r.phones.length ? `<p class="mute">Phone services found: ${r.phones.map(esc).join(', ')}</p>` : ''}
    <div class="fields">${FIELDS.map(([k, l, t]) => `<label>${l}<input id="s_${k}" value="${esc(s[k])}" ${t ? 'type="number"' : ''}></label>`).join('')}
      <div class="pair" role="group" aria-label="Wax every (days on snow)"><span class="pl">Wax every (days on snow)</span>
        <label>Board<input id="w_b" type="number" value="${s.wax_every_days.board}"></label><label>Skis<input id="w_s" type="number" value="${s.wax_every_days.ski}"></label></div>
      <div class="pair" role="group" aria-label="Tune every (days on snow)"><span class="pl">Tune every (days on snow)</span>
        <label>Board<input id="t_b" type="number" value="${s.tune_every_days.board}"></label><label>Skis<input id="t_s" type="number" value="${s.tune_every_days.ski}"></label></div></div>
    <label class="wide">Powder lights (comma separated entity ids)<input id="s_powder_lights" value="${esc(s.powder_lights.join(', '))}"></label>
    <h3>Departure points</h3><p class="mute">One per line: name, latitude, longitude. The first is your home.</p>
    <textarea id="s_deps">${s.departures.map(d => `${esc(d.name)}, ${d.lat}, ${d.lon}`).join('\n')}</textarea>
    <label class="wide">Default departure<input id="s_default_departure" value="${esc(s.default_departure)}"></label>
    <h3>Waze travel times</h3><div id="wazemap" class="row"><span class="mute">Looking for Waze sensors…</span></div>
    <label class="inline"><input type="checkbox" id="s_drying" ${s.drying_reminder ? 'checked' : ''}> Boot and glove drying reminder after a logged day</label>
    <label class="inline"><input type="checkbox" id="s_outlook" ${s.weekend_outlook ? 'checked' : ''}> Thursday weekend outlook on my phone</label>
    <label class="inline"><input type="checkbox" id="s_storm" ${s.storm_alerts ? 'checked' : ''}> Storm trending up alerts</label>
    <p><button onclick="saveSettings()">Save</button> <span id="setmsg" class="mute" role="status"></span></p>`;
  const t = await api('traffic').catch(() => null);
  const ws = t ? t.waze_sensors : [];
  $('wazemap').innerHTML = !ws.length ? '<span class="mute">No Waze Travel Time sensors in Home Assistant. Add one per resort (Settings &gt; Devices &amp; services &gt; Waze Travel Time) and they show up here.</span>'
    : RESORTS.map(r => `<label>${esc(r.name)}<select data-resort="${r.id}"><option value="">Match by name</option>${ws.map(w =>
        `<option value="${esc(w.entity_id)}" ${(s.waze_sensors || {})[r.id] === w.entity_id ? 'selected' : ''}>${esc(w.name)}</option>`).join('')}</select></label>`).join('');
}
/* Claude Code sign-in: Daily Snow and Ask Claude run on your Claude subscription */
async function loadClaude() {
  const s = await api('claude').catch(() => ({ cli: false }));
  const l = s.login;
  let h = '<h3>Claude</h3><p class="mute">Daily Snow and Ask Claude run through Claude Code on your Claude subscription (no API fees).</p>';
  if (!s.cli) h += '<p class="due">Claude Code is not installed here (it is inside the add-on).</p>';
  else if (l && !l.done) {
    h += l.url ? `<p><a href="${esc(l.url)}" target="_blank" rel="noopener">Open this link and approve</a>, then paste the code it shows.</p>
      <div class="row"><input id="ccode" placeholder="Paste the code…" autocomplete="off" spellcheck="false" aria-label="Claude sign-in code" style="flex:1;min-width:200px"><button onclick="claudeCode()">Connect</button>
      <button onclick="claudeCancel()">Cancel</button></div>` : '<p class="mute">Starting sign-in…</p>';
    if (!l.url) setTimeout(loadClaude, 2000);
  } else if (s.signed_in) h += '<p>Connected to your Claude account. <button onclick="claudeLogout()">Sign out</button></p>';
  else {
    if (l && l.done && l.result) h += `<p class="mute">${esc(l.result)}</p>`;
    h += s.token ? '<p>Using the token from the add-on Configuration tab. <button onclick="claudeLogin()">Connect your account instead</button></p>'
                 : '<p><button onclick="claudeLogin()">Connect Claude</button></p>';
  }
  $('claudebox').innerHTML = h;
}
async function claudeLogin() { await api('claude/login', { method: 'POST' }); loadClaude(); }
async function claudeCode() { await api('claude/code', { method: 'POST', body: JSON.stringify({ code: $('ccode').value }) }); loadClaude(); }
async function claudeCancel() { await api('claude/cancel', { method: 'POST' }); loadClaude(); }
async function claudeLogout() { if (confirm('Sign Claude out of this add-on?')) { await api('claude/logout', { method: 'POST' }); loadClaude(); } }

async function saveSettings() {
  const p = {}; for (const [k, , t] of FIELDS) { const v = $('s_' + k).value; p[k] = t ? +v : v.trim(); }
  p.powder_lights = $('s_powder_lights').value.split(',').map(x => x.trim()).filter(Boolean);
  p.wax_every_days = { board: +$('w_b').value, ski: +$('w_s').value }; p.tune_every_days = { board: +$('t_b').value, ski: +$('t_s').value };
  p.departures = $('s_deps').value.split('\n').map(l => l.split(',').map(x => x.trim())).filter(a => a.length === 3 && !isNaN(+a[1]) && !isNaN(+a[2]))
    .map(([name, lat, lon]) => ({ name, lat: +lat, lon: +lon }));
  if (!p.departures.length) { $('setmsg').textContent = 'Add at least one departure point.'; return; }
  p.default_departure = $('s_default_departure').value.trim(); p.drying_reminder = $('s_drying').checked;
  p.weekend_outlook = $('s_outlook').checked; p.storm_alerts = $('s_storm').checked;
  const wm = {}; document.querySelectorAll('#wazemap select').forEach(el => { if (el.value) wm[el.dataset.resort] = el.value; });
  if (document.querySelector('#wazemap select')) p.waze_sensors = wm;
  await api('settings', { method: 'PUT', body: JSON.stringify(p) }); $('setmsg').textContent = 'Saved.';
  SET = (await api('settings')).settings; fillDepartures(); homeNote();
}

init();
