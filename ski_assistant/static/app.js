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

let RESORTS = [], SET = {}, FC = null;
const TABS = { forecast: 'Forecast', plan: 'Plan', radar: 'Radar', log: 'Season log', pass: 'Pass', learn: 'Learning to ski', gear: 'Gear', settings: 'Settings' };
const LOADERS = { forecast: () => {}, plan: () => {}, radar: loadRadar, log: loadDays, pass: loadPass, learn: loadLessons, gear: loadGear, settings: loadSettings };

function show(t) {
  for (const k in TABS) { $(k).classList.toggle('on', k === t); $('b_' + k).classList.toggle('on', k === t); }
  LOADERS[t]();
  try { localStorage.setItem('tab', t); } catch (e) {}
}
$('nav').innerHTML = Object.entries(TABS).map(([k, v]) => `<button id="b_${k}" onclick="show('${k}')">${v}</button>`).join('');
const rname = id => (RESORTS.find(r => r.id === id) || {}).name || id;
const ropts = blank => (blank ? '<option value="">(any)</option>' : '') + RESORTS.map(r => `<option value="${r.id}">${esc(r.name)}</option>`).join('');

async function init() {
  RESORTS = await api('resorts');
  SET = (await api('settings')).settings;
  fillDepartures();
  for (const id of ['d', 'ld', 'sd', 'gd']) $(id).value = today;
  $('lr').innerHTML = ropts(); $('sr').innerHTML = ropts(true);
  let t = 'forecast'; try { t = localStorage.getItem('tab') || 'forecast'; } catch (e) {}
  show(TABS[t] ? t : 'forecast');
  loadDailySnow(false); loadForecast(); loadAlerts(); rank();
  addEventListener('hashchange', route);
}
function fillDepartures() {
  $('dep').innerHTML = SET.departures.map(d => `<option ${d.name === SET.default_departure ? 'selected' : ''}>${esc(d.name)}</option>`).join('');
}

/* ---------- Forecast dashboard ---------- */
async function loadForecast() {
  try { FC = await api('forecast'); } catch (e) { $('frows').innerHTML = `<p class="mute">${esc(e.message)}</p>`; return; }
  renderForecast(); route();
}
async function loadAlerts() {
  const a = await api('alerts').catch(() => []);
  $('alerts').innerHTML = a.map(x => `<div class="alert"><b>Powder alert:</b> ${esc(x.resort)} ${x.snow_in}" from ${dayLabel(x.first_day)}</div>`).join('');
}
function reportLine(row) {
  const rep = row.reported || {}, sn = row.snotel;
  const bits = [];
  if (rep.status) bits.push(esc(rep.status));
  if (rep.base_in) bits.push(`base ${inch(rep.base_in)}`);
  if (rep.new_24h_in) bits.push(`${inch(rep.new_24h_in)} in 24h`);
  if (!rep.base_in && sn) bits.push(`SNOTEL ${inch(sn.depth_in)} on the ground`);
  return bits.join(' · ');
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
  $('frows').innerHTML = `<div class="frow head"><div>Resort</div><div class="tot c-past">Last 5</div><div class="tot">Next 5</div>
     <div class="tot">6-10</div><div class="tot">11-15</div><div class="c-strip">Daily snow (today marked)</div></div>` +
    rows.map(r => r.error ? `<div class="frow"><div class="name">${esc(r.name)}</div><div class="mute" style="grid-column:2/-1">${esc(r.error)}</div></div>` :
      `<div class="frow" onclick="location.hash='resort/${r.id}'">
        <div><div class="name">${esc(r.name)}${r.pass === 'keystone' ? '<span class="badge">Keystone</span>' : ''}</div>
          <div class="small">${reportLine(r)}</div></div>
        <div class="tot c-past">${inch(r.summary.last5_in)}</div><div class="tot"><b>${inch(r.summary.next5_in)}</b></div>
        <div class="tot">${inch(r.summary.days6_10_in)}</div><div class="tot mute">${inch(r.summary.days11_15_in)}</div>
        <div class="strip chart" id="strip_${r.id}"></div></div>`).join('');
  for (const r of rows) {
    if (r.error) continue;
    const s = r.summary;
    const bars = [...s.past.map(d => ({ v: d.snow_in, fill: 'var(--snow-past)', tip: snowTip(d, true) })),
                  ...s.future.map((d, i) => ({ v: d.snow_in, fill: i < 10 ? 'var(--snow)' : 'var(--snow-low)', tip: snowTip(d, false) }))];
    const el = $('strip_' + r.id);
    Charts.add(() => barChart(el, bars, { axis: false, height: 44, todayIndex: s.past.length, floorMax: 4, title: `${r.name} daily snow` }));
  }
}

/* ---------- Daily Snow ---------- */
async function loadDailySnow(refresh) {
  const box = $('dailysnow');
  box.innerHTML = '<p class="mute">Loading the Daily Snow...</p>';
  let r;
  try { r = await api('daily-snow' + (refresh ? '?refresh=true' : '')); } catch (e) { r = { error: e.message }; }
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
  if (m) { if ($('forecast').classList.contains('on') === false) show('forecast'); openResort(m[1], m[2] || 'mid'); }
  else { $('fdetail').hidden = true; $('flist').hidden = false; }
}
async function openResort(id, band) {
  $('flist').hidden = true; const box = $('fdetail'); box.hidden = false;
  box.innerHTML = '<p class="mute">Loading...</p>';
  let d;
  try { d = await api(`resort/${id}?band=${band}`); } catch (e) { box.innerHTML = `<button onclick="location.hash=''">Back</button><p>${esc(e.message)}</p>`; return; }
  const future = d.daily.filter(x => x.date >= today).slice(0, 15);
  const past = d.daily.filter(x => x.date < today).slice(-5);
  const rep = d.reported || {}, sn = d.snotel || {};
  const tile = (v, k) => v == null || v === '' ? '' : `<div class="tile"><div class="v">${v}</div><div class="k">${k}</div></div>`;
  const total = (a, b) => inch(future.slice(a, b).reduce((s, x) => s + x.snow_in, 0));
  box.innerHTML = `
   <div class="row spread"><div class="row"><button onclick="location.hash=''">&larr; All resorts</button><h2>${esc(d.resort.name)}</h2></div>
    <div class="row seg">${['base', 'mid', 'summit'].map(b => `<button class="${b === band ? 'on' : ''}" onclick="location.hash='resort/${id}/${b}'">${b[0].toUpperCase() + b.slice(1)} ${d.elevations[b].toLocaleString()} ft</button>`).join('')}</div></div>
   <div class="card"><div class="tiles">
     ${tile(total(0, 5), 'Next 5 days')}${tile(total(5, 10), 'Days 6-10')}${tile(total(10, 15), 'Days 11-15 (low confidence)')}
     ${tile(rep.base_in != null ? inch(rep.base_in) : null, 'Reported base')}${tile(rep.new_24h_in != null ? inch(rep.new_24h_in) : null, 'Reported 24h')}
     ${tile(rep.season_in ? inch(rep.season_in) : null, 'Season total')}
     ${tile(rep.lifts_total != null ? `${rep.lifts_open}/${rep.lifts_total}` : null, 'Lifts open')}
     ${tile(rep.terrain_open_pct != null ? rep.terrain_open_pct + '%' : null, 'Terrain open')}
     ${tile(sn.depth_in != null ? inch(sn.depth_in) : null, `SNOTEL depth${sn.as_of ? ' (' + esc(sn.as_of) + ')' : ''}`)}
     ${tile(sn.new_72h_in != null ? inch(sn.new_72h_in) : null, 'SNOTEL 72h change')}
   </div>${rep.status ? `<p class="small">Resort status: ${esc(rep.status)}${rep.conditions ? ' · ' + esc(rep.conditions) : ''}</p>` : ''}</div>
   <div class="card"><h3>Daily snow, next 15 days <span class="small">(${band}, ${d.elevations[band].toLocaleString()} ft; 6am to 6am)</span></h3>
     <div class="legend"><span><i class="box" style="background:var(--snow-past)"></i>Last 5 days (modelled)</span><span><i class="box" style="background:var(--snow)"></i>Days 1-10</span><span><i class="box" style="background:var(--snow-low)"></i>Days 11-15</span></div>
     <div class="chart" id="c_daily"></div></div>
   <div class="card"><h3>Model check: running snow total</h3>
     <div class="legend">${d.models.map((m, i) => `<span><i style="background:var(--s${i + 1})"></i>${esc(m)}</span>`).join('')}</div>
     <div class="chart" id="c_models"></div>
     <p class="small">When the two lines split apart, the forecast is uncertain. ECMWF ends a day earlier than GFS.</p></div>
   <div class="card"><h3>Next 48 hours: snow per hour</h3><div class="chart" id="c_h_snow"></div>
     <h3 style="margin-top:12px">Next 48 hours: temperature (&deg;F)</h3><div class="chart" id="c_h_temp"></div></div>
   <div class="card wrap"><h3>Day by day</h3><table>
     <tr><th>Day</th><th class="num">Snow</th><th class="num">Day / night</th><th>Quality</th><th class="num">High / low</th><th class="num">Wind / gust</th><th class="num">Freezing level</th></tr>
     ${future.map(x => `<tr><td>${dayLabel(x.date)}</td><td class="num"><b>${inch(x.snow_in)}</b></td><td class="num">${inch(x.snow_day_in)} / ${inch(x.snow_night_in)}</td>
       <td>${x.quality === 'rain' || x.quality === 'mixed' ? `<span class="warnnote">${esc(x.quality)}</span>` : esc(x.quality || '')}</td>
       <td class="num">${Math.round(x.tmax_f)}° / ${Math.round(x.tmin_f)}°</td><td class="num">${Math.round(x.wind_mph)} / ${Math.round(x.gust_mph)} mph</td>
       <td class="num">${x.freezing_ft ? x.freezing_ft.toLocaleString() + ' ft' : '-'}</td></tr>`).join('')}</table></div>
   <div class="card"><h3>Getting there</h3>${leaveText(d.leave_today)}
     ${d.transit.length ? '<ul>' + d.transit.map(x => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a>: <span class="mute">${esc(x.note)}</span></li>`).join('') + '</ul>' : ''}
     <p>${d.info.webcams_url ? `<a href="${esc(d.info.webcams_url)}" target="_blank" rel="noopener">Webcams</a>` : ''}
       ${d.info.openskimap_url ? ` · <a href="${esc(d.info.openskimap_url)}" target="_blank" rel="noopener">Trail map (OpenSkiMap)</a>` : ''}
       ${d.info.beginner_pct != null ? ` · <span class="mute">${d.info.beginner_pct}% of runs are green or blue</span>` : ''}</p></div>`;

  const bars = [...past.map(x => ({ v: x.snow_in, fill: 'var(--snow-past)', tip: snowTip(x, true) })),
                ...future.map((x, i) => ({ v: x.snow_in, fill: i < 10 ? 'var(--snow)' : 'var(--snow-low)', tip: snowTip(x, false) }))];
  const labels = [...past, ...future].map(x => dayLabel(x.date));
  Charts.add(() => barChart($('c_daily'), bars, { height: 170, labels, labelEvery: innerWidth < 600 ? 3 : 1, todayIndex: past.length, floorMax: 4, title: 'Daily snow' }));

  const cum = name => { let s = 0; return future.map(x => { const v = x.models[name]; if (v == null) return null; s += v; return Math.round(s * 10) / 10; }); };
  const series = d.models.map((m, i) => ({ name: m, color: `var(--s${i + 1})`, values: cum(m) }));
  Charts.add(() => lineChart($('c_models'), series, { height: 170, labels: future.map(x => dayLabel(x.date)), labelEvery: innerWidth < 600 ? 3 : 2,
    unit: '"', min: 0, floorMax: 4, directLabels: true, title: 'Model running totals',
    tip: i => `<b>${dayLabel(future[i].date)}</b>` + series.map(s => `<br>${esc(s.name)}: ${s.values[i] == null ? 'no data' : inch(s.values[i])}`).join('') }));

  const hrs = d.next48, hl = hrs.map(h => { const x = new Date(h.time); return x.getHours() === 0 ? DOW[x.getDay()] : (x.getHours() % 12 || 12) + (x.getHours() < 12 ? 'a' : 'p'); });
  const htip = h => { const x = new Date(h.time); return `<b>${DOW[x.getDay()]} ${t12(h.time.slice(11, 16))}</b><br>snow ${h.snow_in.toFixed(2)}"${h.rain_in > 0.01 ? `<br>rain ${h.rain_in.toFixed(2)}"` : ''}<br>${h.temp_f}°F · gust ${h.gust_mph} mph`; };
  Charts.add(() => barChart($('c_h_snow'), hrs.map(h => ({ v: h.snow_in, tip: htip(h) })), { height: 120, labels: hl, labelEvery: 6, floorMax: 0.5, title: 'Hourly snow' }));
  Charts.add(() => lineChart($('c_h_temp'), [{ name: 'Temperature', color: 'var(--s2)', values: hrs.map(h => h.temp_f) }],
    { height: 120, labels: hl, labelEvery: 6, unit: '°', title: 'Hourly temperature', tip: i => htip(hrs[i]) }));
  scrollTo(0, 0);
}

/* ---------- Radar ---------- */
let MAP = null, RLAYERS = [], RIDX = 0, RTIMER = null;
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
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 13, attribution: '&copy; OpenStreetMap contributors' }).addTo(MAP);
  RLAYERS = RFRAMES.map(f => L.tileLayer(`https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913${f ? '-' + f : ''}/{z}/{x}/{y}.png`,
    { opacity: 0, zIndex: 10, attribution: 'Radar: IEM NEXRAD' }).addTo(MAP));
  if (!FC) FC = await api('forecast').catch(() => []);
  for (const r of FC) {
    if (r.error) continue;
    L.marker([r.lat, r.lon], { icon: L.divIcon({ className: '', html: `<div class="snowpin">${esc(r.name)} ${inch(r.summary.next5_in)}</div>`, iconSize: null, iconAnchor: [0, 10] }) })
      .addTo(MAP).on('click', () => { show('forecast'); location.hash = 'resort/' + r.id; });
  }
  startRadar();
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
  const t = $('t'); t.innerHTML = '<tr><td>Loading...</td></tr>';
  const q = `best-days?date=${$('d').value}&skis=${$('skis').checked}&departure=${encodeURIComponent($('dep').value)}`;
  let rows;
  try { rows = await api(q); } catch (e) { t.innerHTML = `<tr><td>${esc(e.message)}</td></tr>`; return; }
  t.innerHTML = '<tr><th>Resort</th><th class="num">Score</th><th class="num">Fresh</th><th class="num">Gust</th><th class="num">High</th><th class="num">Base</th><th class="num">Lifts</th><th>Leave</th></tr>' +
    rows.map(r => r.error ? `<tr><td>${esc(r.resort)}</td><td colspan=7>${esc(r.error)}</td></tr>` :
      `<tr><td>${esc(r.resort)}</td><td class="num">${r.score}</td><td class="num">${inch(r.fresh_in)}</td><td class="num">${Math.round(r.gust_mph)}</td><td class="num">${Math.round(r.tmax_f)}°</td>
       <td class="num">${r.snowpack ? inch(r.snowpack.depth_in) : '-'}</td><td class="num">${r.live && r.live.lifts_total != null ? r.live.lifts_open + '/' + r.live.lifts_total : '-'}</td>
       <td>${t12(r.leave.leave_at)} <span class="mute">(${hm(r.leave.drive_min)})</span></td></tr>`).join('');
  const top = rows.find(r => !r.error);
  $('pick').innerHTML = top ? `<h3>${esc(top.resort)}</h3>${leaveText(top.leave)}
    <p><b>Wear</b> (feels like ${top.gear.feels_like_f}°F): ${top.gear.wear.map(esc).join(', ')}</p>
    ${top.gear.notes.length ? `<p><b>Also</b>: ${top.gear.notes.map(esc).join('; ')}</p>` : ''}
    ${top.beginner_pct != null ? `<p class="mute">${top.beginner_pct}% of runs are green or blue.</p>` : ''}
    ${top.transit.length ? '<p><b>Shuttle / transit</b></p><ul>' + top.transit.map(x => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a>: <span class="mute">${esc(x.note)}</span></li>`).join('') + '</ul>' : ''}` : '';
}
function leaveText(l) {
  let s = l.reason === 'traffic'
    ? `<p>Leave at <b>${t12(l.leave_at)}</b> to be on I-70 by ${t12(l.on_i70_by)}, ahead of the ${l.powder ? 'powder-day ' : ''}rush. You'll get there about ${t12(l.arrive_at)} (${hm(l.drive_min)}).</p>
       <p class="mute">Leave at 7:00am instead and it's about ${hm(l.if_later.drive_min)}.</p>`
    : `<p>Leave at <b>${t12(l.leave_at)}</b> to be on the lifts by ${t12(SET.arrive_by)}. Drive about ${hm(l.drive_min)}.</p>`;
  if (l.home) s += `<p class="mute">Heading home: leave before ${t12(l.home.leave_before)} or after ${t12(l.home.or_after)}. At 3pm it's about ${hm(l.home.drive_min_at_3pm)} (vs ${hm(l.home.base_min)} with no traffic).</p>`;
  return s;
}
async function askClaude() {
  $('ans').textContent = 'Thinking...';
  try {
    const r = await api('ask', { method: 'POST', body: JSON.stringify({ question: $('q').value || 'Where should I go?', date: $('d').value, skis: $('skis').checked, departure: $('dep').value }) });
    $('ans').textContent = r.answer;
  } catch (e) { $('ans').textContent = e.message; }
}

/* ---------- Season log ---------- */
async function loadDays() {
  const d = await api('days');
  $('days').innerHTML = '<tr><th>Date</th><th>Resort</th><th>On</th><th class="num">Vertical</th><th>Notes</th><th></th></tr>' +
    d.map(x => `<tr><td>${x.date}</td><td>${esc(rname(x.resort_id))}</td><td>${x.equipment}</td><td class="num">${x.vertical_ft ?? ''}</td><td>${esc(x.notes)}</td>
      <td><button onclick="delDay(${x.id})">Delete</button></td></tr>`).join('');
}
async function addDay() {
  await api('days', { method: 'POST', body: JSON.stringify({ date: $('ld').value, resort_id: $('lr').value, equipment: $('le').value,
    vertical_ft: $('lv').value ? +$('lv').value : null, notes: $('ln').value }) });
  $('ln').value = ''; $('lv').value = ''; loadDays();
}
async function delDay(id) { if (confirm('Delete this day?')) { await api('days/' + id, { method: 'DELETE' }); loadDays(); } }

/* ---------- Pass ---------- */
async function loadPass() {
  const p = await api('pass');
  const pr = (n, x) => `<p><b>${n}</b>: ${x.days} days${x.price ? ` · $${x.price} paid · ${x.cost_per_day != null ? '$' + x.cost_per_day + ' per day' : 'no days yet'}` : ' · add the price in Settings'}</p>`;
  $('passbox').innerHTML = `<h3>This season: ${p.total_days} days${p.vertical_ft ? ` · ${p.vertical_ft.toLocaleString()} ft` : ''}</h3>
    ${pr('Ikon', p.passes.ikon)}${pr('Keystone', p.passes.keystone)}
    ${p.limited_days.map(l => `<p class="mute">${esc(l.resort)}: ${l.used} of ${l.limit} Ikon days used</p>`).join('')}
    <table>${p.per_resort.map(r => `<tr><td>${esc(r.resort)}</td><td class="num">${r.days}</td></tr>`).join('')}</table>`;
}

/* ---------- Learning to ski ---------- */
async function loadLessons() {
  const l = await api('lessons');
  $('skillpick').innerHTML = l.skill_list.map(s => `<label class="inline"><input type="checkbox" value="${esc(s)}">${esc(s)}</label>`).join('');
  const s = l.summary;
  $('learnsum').innerHTML = `<h3>${s.ski_days} ski days · ${s.lessons} lessons</h3>
    <p>${Object.entries(s.skills).map(([k, v]) => `${esc(k)} (${v})`).join(', ') || 'No skills logged yet.'}</p>
    ${s.not_yet.length ? `<p class="mute">Not practiced yet: ${s.not_yet.map(esc).join(', ')}</p>` : ''}`;
  $('lessons').innerHTML = '<tr><th>Date</th><th>Resort</th><th>Skills</th><th>Notes</th><th></th></tr>' +
    l.lessons.map(x => `<tr><td>${x.date}</td><td>${esc(rname(x.resort_id))}</td><td>${esc(x.skills)}</td><td>${esc(x.notes)}</td>
      <td><button onclick="delLesson(${x.id})">Delete</button></td></tr>`).join('');
}
async function addLesson() {
  const skills = [...$('skillpick').querySelectorAll('input:checked')].map(i => i.value).join(', ');
  await api('lessons', { method: 'POST', body: JSON.stringify({ date: $('sd').value, resort_id: $('sr').value, skills, notes: $('sn').value }) });
  $('sn').value = ''; loadLessons();
}
async function delLesson(id) { if (confirm('Delete this lesson?')) { await api('lessons/' + id, { method: 'DELETE' }); loadLessons(); } }

/* ---------- Gear ---------- */
async function loadGear() {
  const g = await api('gear');
  $('upkeep').innerHTML = '<h3>Upkeep</h3>' + Object.entries(g).map(([eq, k]) => `<p><b>${eq === 'board' ? 'Board' : 'Skis'}</b>: ` +
    Object.entries(k).map(([kind, u]) => `<span class="${u.due ? 'due' : ''}">${kind} ${u.days_since}/${u.every} days${u.due ? ' (due)' : ''}</span>`).join(' · ') + '</p>').join('');
}
async function addService() { await api('gear', { method: 'POST', body: JSON.stringify({ date: $('gd').value, equipment: $('ge').value, kind: $('gk').value }) }); loadGear(); }
async function addShop() {
  try { await api('shopping', { method: 'POST', body: JSON.stringify({ item: $('shop').value }) }); $('shopmsg').textContent = 'Added.'; $('shop').value = ''; }
  catch (e) { $('shopmsg').textContent = e.message; }
}

/* ---------- Settings ---------- */
const FIELDS = [['arrive_by', 'On the lifts by (HH:MM)'], ['buffer_min', 'Buffer for parking and boots (min)', 'n'],
  ['ikon_price', 'Ikon pass price ($)', 'n'], ['keystone_price', 'Keystone pass price ($)', 'n'],
  ['phone_service', 'Phone notify service'], ['tts_entity', 'TTS entity (tts.*)'], ['speaker_entity', 'Speaker (media_player.*)'],
  ['wake_time', 'Powder wake-up time (HH:MM)'], ['tracker_entity', 'Phone tracker (device_tracker.*)'],
  ['climate_entity', 'Thermostat (climate.*)'], ['normal_temp_f', 'Normal temperature (F)', 'n'], ['claude_model', 'Claude model']];
async function loadSettings() {
  const r = await api('settings'); const s = r.settings; SET = s;
  $('setbox').innerHTML = `<h3>Settings</h3>${r.claude_ready ? '' : '<p class="due">No Anthropic API key yet: add it in the add-on Configuration tab.</p>'}
    ${r.phones.length ? `<p class="mute">Phone services found: ${r.phones.map(esc).join(', ')}</p>` : ''}
    <div class="row">${FIELDS.map(([k, l, t]) => `<label>${l}<input id="s_${k}" value="${esc(s[k])}" ${t ? 'type="number"' : ''}></label>`).join('')}</div>
    <label>Powder lights (comma separated entity ids)<input id="s_powder_lights" value="${esc(s.powder_lights.join(', '))}"></label>
    <label>Wax every (days on snow): board / skis<span class="row"><input id="w_b" type="number" value="${s.wax_every_days.board}"><input id="w_s" type="number" value="${s.wax_every_days.ski}"></span></label>
    <label>Tune every (days on snow): board / skis<span class="row"><input id="t_b" type="number" value="${s.tune_every_days.board}"><input id="t_s" type="number" value="${s.tune_every_days.ski}"></span></label>
    <h3>Departure points</h3><p class="mute">One per line: name, latitude, longitude. The first is your home.</p>
    <textarea id="s_deps">${s.departures.map(d => `${esc(d.name)}, ${d.lat}, ${d.lon}`).join('\n')}</textarea>
    <label>Default departure<input id="s_default_departure" value="${esc(s.default_departure)}"></label>
    <label class="inline"><input type="checkbox" id="s_drying" ${s.drying_reminder ? 'checked' : ''}> Boot and glove drying reminder after a logged day</label>
    <p><button onclick="saveSettings()">Save</button> <span id="setmsg" class="mute"></span></p>`;
}
async function saveSettings() {
  const p = {}; for (const [k, , t] of FIELDS) { const v = $('s_' + k).value; p[k] = t ? +v : v.trim(); }
  p.powder_lights = $('s_powder_lights').value.split(',').map(x => x.trim()).filter(Boolean);
  p.wax_every_days = { board: +$('w_b').value, ski: +$('w_s').value }; p.tune_every_days = { board: +$('t_b').value, ski: +$('t_s').value };
  p.departures = $('s_deps').value.split('\n').map(l => l.split(',').map(x => x.trim())).filter(a => a.length === 3 && !isNaN(+a[1]) && !isNaN(+a[2]))
    .map(([name, lat, lon]) => ({ name, lat: +lat, lon: +lon }));
  if (!p.departures.length) { $('setmsg').textContent = 'Add at least one departure point.'; return; }
  p.default_departure = $('s_default_departure').value.trim(); p.drying_reminder = $('s_drying').checked;
  await api('settings', { method: 'PUT', body: JSON.stringify(p) }); $('setmsg').textContent = 'Saved.';
  SET = (await api('settings')).settings; fillDepartures();
}

init();
