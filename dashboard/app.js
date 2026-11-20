/* USVI Hurricane Exposure - reads data/summary.json and data/estates.geojson (pipeline/step5_export.py) */
(async function () {
  const C = { ink: '#0E2A3B', coral: '#C8553D', coralL: '#E8836B', sea: '#2F7F86', seaL: '#8CC2C4', sand: '#D9CBB0', line: '#EFE9DE', muted: '#6B7C89', faint: '#9AA7B1' };
  const [S, GJ] = await Promise.all([
    fetch('data/summary.json').then((r) => r.json()).catch(() => null),
    fetch('data/estates.geojson').then((r) => r.json()).catch(() => null),
  ]);
  if (!S || !GJ) { document.getElementById('updated').textContent = 'Data files are missing - run the pipeline first.'; return; }

  const nf = (v, d = 0) => v == null ? '–' : Number(v).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const dateTxt = (s) => { if (!s) return '–'; const [y, m, d] = s.slice(0, 10).split('-').map(Number); return `${MON[m - 1]} ${d}, ${y}`; };
  // UTC "2026-11-20T05:31" -> "Nov 20, 1:31 AM AST"
  const astTxt = (s, year = false) => {
    if (!s) return '–';
    const t = new Date(s.length <= 16 ? `${s}:00Z` : s);
    return t.toLocaleString('en-US', { timeZone: 'America/St_Thomas', month: 'short', day: 'numeric', ...(year ? { year: 'numeric' } : {}), hour: 'numeric', minute: '2-digit' }) + ' AST';
  };
  const catClass = (kt) => kt >= 137 ? 'h5' : kt >= 113 ? 'h4' : kt >= 96 ? 'h3' : kt >= 83 ? 'h2' : kt >= 64 ? 'h1' : kt >= 34 ? 'ts' : 'td';
  const catTxt = (kt) => kt >= 64 ? `Cat ${kt >= 137 ? 5 : kt >= 113 ? 4 : kt >= 96 ? 3 : kt >= 83 ? 2 : 1}` : kt >= 34 ? 'Trop. storm' : 'Depression';
  const catPill = (kt) => `<span class="cat ${catClass(kt)}">${catTxt(kt)}</span> <small>${nf(Math.round(kt / 5) * 5)} kt</small>`;
  const m = S.meta;
  const EST = Object.fromEntries(S.estates.map((e) => [e.geoid, e]));
  const STORM = Object.fromEntries(S.storms.map((s) => [s.storm_id, s]));
  const health = Object.fromEntries(S.health.map((h) => [h.source, h]));
  const rel = /hurdat2-1851-\d{4}-(\d{2})(\d{2})(\d{2,4})\.txt/.exec(m.hurdat_file || '');
  const relTxt = rel ? `${MON[+rel[1] - 1]} ${+rel[2]}, ${rel[3].length === 2 ? '20' + rel[3] : rel[3]}` : '';

  document.getElementById('updated').textContent = `Storm record ${m.first_season}–${m.last_season} from NOAA's HURDAT2 (released ${relTxt}) · active storms checked every 3 hours, last ${astTxt(health.nhc_active?.last_success_utc, true)}`;
  document.getElementById('hurdatFile').textContent = m.hurdat_file;
  document.getElementById('built').textContent = `${nf(m.storms_total)} Atlantic storms and ${nf(m.track_points)} track points measured against ${nf(m.estates)} estates. Built ${astTxt(m.built_utc, true)}.`;

  /* ---------- Alerts and active storms ---------- */
  const cards = [];
  const sevTxt = { high: 'Alert', medium: 'Watch', low: 'Notice' };
  S.alerts.filter((a) => a.category !== 'storm').forEach((a) => cards.push(
    `<div class="alert ${a.severity}"><span class="sev">${sevTxt[a.severity]}</span><div><b>${esc(a.title)}</b><p>${esc(a.message)}</p></div></div>`));
  const threatText = (t) => `NHC advisory ${esc(t.advisory)} forecasts the centre to pass ${nf(t.closest_nmi_rounded)} nautical miles from ${esc(t.closest_estate)}, ${esc(t.closest_island)}, around ${astTxt(t.closest_utc)}, with maximum winds near ${nf(Math.round(t.wind_at_closest_kt / 5) * 5)} knots (${esc(t.category_at_closest)}).`;
  if (S.active.length) {
    S.active.forEach((t) => {
      const lvl = t.threat_level === 'direct' ? 'high' : t.threat_level === 'watch' ? 'medium' : '';
      cards.push(`<div class="alert ${lvl}"><span class="sev">${{ direct: 'Alert', watch: 'Watch', monitor: 'Active', passed: 'Passed' }[t.threat_level]}</span>
        <div><b>${esc(t.storm_name)}: closest forecast approach ${nf(t.closest_nmi_rounded)} nmi</b><p>${threatText(t)} Now ${nf(t.now_nmi_from_usvi)} nmi from the territory with ${nf(t.now_wind_kt)}-knot winds. Issued ${astTxt(t.issued_utc)}.</p></div></div>`);
    });
  } else {
    cards.push(`<div class="active-card"><span class="sev">All clear</span><div><b>No active Atlantic storms</b><p>The National Hurricane Center lists no active storm in the Atlantic. Every three hours this pipeline checks again; when one is forecast to pass within 150 nautical miles it opens an alert.</p></div></div>`);
    const r = S.replay;
    if (r && r.storm_id) cards.push(`<div class="active-card replay"><span class="sev">Example</span><div><b>What an alert looked like: ${esc(r.storm_name)}, ${dateTxt(r.issued_utc)}</b><p>Replayed from a saved advisory for the storm that became Ernesto. ${threatText(r)} It was then ${nf(r.now_nmi_from_usvi)} nmi away, ${nf(r.hours_to_closest)} hours out. Ernesto crossed the Virgin Islands as a tropical storm on Aug 13–14, 2024.</p></div></div>`);
  }
  document.getElementById('alerts').innerHTML = cards.join('');

  /* ---------- KPIs and headline ---------- */
  const ret = (first, lvl) => S.returns.find((r) => r.first_season === first && r.level_order === lvl) || {};
  const hu = ret(1851, 2), maj = ret(1851, 3), ts = ret(1851, 1);
  const worst = S.storms.filter((s) => s.pop_in_64kt != null).sort((a, b) => b.pop_in_64kt - a.pop_in_64kt)[0];
  const pctWorst = worst ? 100 * worst.pop_in_64kt / m.population : 0;
  const k = [
    ['Hurricanes passing near', nf(m.hurricanes_near), `Centre within 60 nmi, ${m.first_season}–${m.last_season} · of ${nf(m.storms_near)} storms of tropical-storm strength or more`],
    ['A hurricane passes near', `every ${nf(hu.return_period_years, 1)}<small>years</small>`, `On average since 1851 · ${nf(hu.pct_years_with_one, 0)}% of years had at least one`],
    ['Major hurricanes (Cat 3+)', nf(m.majors_near), `About one every ${nf(maj.return_period_years, 0)} years · most recent ${esc(maj.most_recent)}`],
    ['Residents in hurricane-force winds', worst ? nf(worst.pop_in_64kt) : '–', worst ? `${esc(worst.storm_label)} · ${nf(pctWorst, 1)}% of the ${nf(m.population)} people counted in 2020` : ''],
  ];
  document.getElementById('kpis').innerHTML = k.map(([l, v, note]) => `<div class="kpi"><p class="l">${l}</p><p class="v">${v}</p><p class="note">${note}</p></div>`).join('');

  const irma = STORM.AL112017, maria = STORM.AL152017, hugo = STORM.AL111989;
  document.getElementById('finding').innerHTML = `Since 1851, ${nf(m.hurricanes_near)} hurricanes have passed within 60 nautical miles of the Virgin Islands, <em>about one every ${nf(hu.return_period_years, 1)} years</em>. In 2017 Irma and Maria came two weeks apart, and Maria's hurricane-force winds reached ${nf(pctWorst, 1)}% of today's residents.`;
  const inhabited34 = S.storms.filter((s) => s.pop_in_34kt > 0).length;
  const maxTimes = Math.max(...S.estates.map((e) => e.times_in_64kt_since_2004));
  const hot = S.estates.filter((e) => e.times_in_64kt_since_2004 === maxTimes);
  const busiest = [...S.decades].sort((a, b) => b.storms - a.storms || b.major_hurricanes - a.major_hurricanes)[0];
  document.getElementById('facts').innerHTML = [
    [`${nf(hugo?.closest_nmi, 1)} nmi`, `How close Hugo's eye came to ${esc(hugo?.closest_island)} in 1989, at ${nf(hugo?.wind_at_closest_kt)} knots`],
    [nf(inhabited34), `Storms since 2004 whose tropical-storm-force winds reached homes`],
    [nf(hot.reduce((a, e) => a + e.population, 0)), `Residents of the ${nf(hot.length)} estates inside hurricane-force winds ${maxTimes} times since 2004`],
    [busiest.label, `Busiest decade on record: ${busiest.storms} storms passing near, ${busiest.major_hurricanes} of them major hurricanes`],
  ].map(([v, l]) => `<div><b>${v}</b><span>${l}</span></div>`).join('');
  document.getElementById('howFinding').textContent = `Irma passed ${nf(irma?.closest_nmi)} nmi from ${irma?.closest_island} and Maria ${nf(maria?.closest_nmi)} nmi from ${maria?.closest_island}, both at Category 5 strength, 14 days apart.`;

  /* ---------- Map ---------- */
  const map = L.map('map', { scrollWheelZoom: false, attributionControl: true, zoomSnap: 0.5 });
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 16, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(map);
  const SEQ = ['#F3EEE4', '#F6D3C7', '#EDA28C', '#D9694F', '#A63F2B', '#0E2A3B'];
  const MEASURES = {
    m_in64: { label: 'Times in hurricane-force winds, 2004 on', key: 'times_in_64kt_since_2004', note: 'Times each estate sat inside a storm\'s 64-knot wind radius, 2004 to ' + m.last_season + '.' },
    m_in34: { label: 'Times in tropical-storm-force winds, 2004 on', key: 'times_in_34kt_since_2004', note: 'Times each estate sat inside a storm\'s 34-knot wind radius, 2004 to ' + m.last_season + '.' },
    m_near: { label: 'Hurricanes passing within 60 nmi, 1851 on', key: 'hurricanes_near', note: 'Hurricanes whose centre came within 60 nautical miles of the estate. The islands are small, so this varies little.' },
    m_pop: { label: 'Residents, 2020 Census', key: 'population', bins: [0, 1, 100, 500, 1000, 2500], note: 'People counted in each estate in the 2020 Census.' },
  };
  const withTrack = S.storms.filter((s) => S.tracks[s.storm_id]);
  const modern = withTrack.filter((s) => S.fields[s.storm_id]).sort((a, b) => b.season - a.season || (b.closest_date_ast > a.closest_date_ast ? 1 : -1));
  const older = withTrack.filter((s) => !S.fields[s.storm_id] && s.is_near && s.is_hurricane).sort((a, b) => b.season - a.season);
  const pick = document.getElementById('mapPick');
  pick.innerHTML = `<optgroup label="Estate history">${Object.entries(MEASURES).map(([k, v]) => `<option value="${k}">${v.label}</option>`).join('')}</optgroup>`
    + `<optgroup label="One storm, with wind fields (2004 on)">${modern.map((s) => `<option value="${s.storm_id}">${esc(s.storm_label)}</option>`).join('')}</optgroup>`
    + `<optgroup label="One hurricane, track only (before 2004)">${older.map((s) => `<option value="${s.storm_id}">${esc(s.storm_label)}</option>`).join('')}</optgroup>`;

  const binsFor = (vals) => { const u = [...new Set(vals)].sort((a, b) => a - b); return u.length <= SEQ.length ? u : null; };
  let colorOf = () => SEQ[0];
  let tipOf = () => '';
  const layer = L.geoJSON(GJ, {
    style: () => ({ color: '#fff', weight: 0.6, fillOpacity: 0.82, fillColor: SEQ[0] }),
    onEachFeature: (f, l) => l.bindTooltip(() => tipOf(EST[f.properties.geoid]), { sticky: true }),
  }).addTo(map);
  const bounds = layer.getBounds();
  const fit = () => map.fitBounds(bounds, { padding: [8, 8] });
  fit();
  window.addEventListener('resize', () => { map.invalidateSize(); });
  let trackLayer = null;
  const side = document.getElementById('side');
  const baseTip = (e) => `<b>${esc(e.estate_name)}</b><br>${esc(e.island)} · ${nf(e.population)} residents`;

  const showMeasure = (key) => {
    const M = MEASURES[key];
    const vals = S.estates.map((e) => e[M.key]);
    let legend;
    if (M.bins) {
      const b = M.bins;
      const cls = (v) => { let i = 0; b.forEach((x, j) => { if (v >= x) i = j; }); return i; };
      colorOf = (e) => SEQ[cls(e[M.key])];
      legend = b.map((x, j) => [SEQ[j], j === 0 ? 'None' : j === b.length - 1 ? `${nf(x)} or more` : `${nf(x)}–${nf(b[j + 1] - 1)}`]);
    } else {
      const u = binsFor(vals);
      if (u) {
        const off = SEQ.length - u.length;
        colorOf = (e) => SEQ[Math.max(0, u.indexOf(e[M.key]) + (u[0] === 0 ? 0 : off))];
        legend = u.map((v) => [colorOf({ [M.key]: v }), v === 1 ? '1 time' : `${v} ${M.key === 'hurricanes_near' ? 'hurricanes' : 'times'}`]);
      } else {
        const lo = Math.min(...vals), hi = Math.max(...vals), step = (hi - lo) / SEQ.length || 1;
        colorOf = (e) => SEQ[Math.min(SEQ.length - 1, Math.floor((e[M.key] - lo) / step))];
        legend = SEQ.map((c, i) => [c, `${nf(lo + i * step)}–${nf(lo + (i + 1) * step)}`]);
      }
    }
    tipOf = (e) => `${baseTip(e)}<br>${M.label}: <b>${nf(e[M.key])}</b>`;
    layer.setStyle((f) => ({ fillColor: colorOf(EST[f.properties.geoid]) }));
    if (trackLayer) { trackLayer.remove(); trackLayer = null; fit(); }
    const top = [...S.estates].sort((a, b) => b[M.key] - a[M.key] || b.population - a.population).slice(0, 6);
    side.innerHTML = `<h3>${M.label}</h3><p class="lede">${M.note}</p>
      <div class="legend">${legend.map(([c, l]) => `<div><i style="background:${c}"></i>${l}</div>`).join('')}</div>
      <div><p class="mini">Highest, then most residents</p><ul class="top-list">${top.map((e) => `<li><span>${esc(e.estate_name)} <small class="mini">${esc(e.island)}</small></span><span>${nf(e[M.key])}</span></li>`).join('')}</ul></div>`;
  };

  const FIELD_C = { 64: '#A63F2B', 50: '#D9694F', 34: '#F2B9A6' };
  const showStorm = (id) => {
    const s = STORM[id];
    const f = S.fields[id];
    const inField = {};
    if (f) Object.entries(f).forEach(([kt, ids]) => ids.forEach((g) => { inField[g] = +kt; }));
    colorOf = (e) => FIELD_C[inField[e.geoid]] || (f ? '#F3EEE4' : '#EAE4D8');
    tipOf = (e) => `${baseTip(e)}${f ? `<br>${inField[e.geoid] ? `Inside ${inField[e.geoid]}-knot winds` : 'Outside the 34-knot winds'}` : ''}`;
    layer.setStyle((ft) => ({ fillColor: colorOf(EST[ft.properties.geoid]) }));
    if (trackLayer) trackLayer.remove();
    const pts = S.tracks[id] || [];
    trackLayer = L.layerGroup([
      L.polyline(pts.map((p) => [p[0], p[1]]), { color: C.ink, weight: 2.5, opacity: 0.85 }),
      ...pts.map((p) => L.circleMarker([p[0], p[1]], { radius: 5, color: '#fff', weight: 1.5, fillOpacity: 1, fillColor: p[2] >= 96 ? '#8E3424' : p[2] >= 64 ? C.coral : p[2] >= 34 ? C.coralL : C.faint })
        .bindTooltip(`<b>${esc(s.storm_label)}</b><br>${dateTxt(p[3])} ${p[3].slice(11)} UTC<br>${catTxt(p[2])} · ${nf(p[2])} kt`)),
    ]).addTo(map);
    // zoom out far enough to show the storm's path past the islands
    const near = pts.filter((p) => Math.abs(p[0] - 18.05) < 0.9 && Math.abs(p[1] + 64.83) < 1.0);
    map.fitBounds(L.latLngBounds([...near.map((p) => [p[0], p[1]]), bounds.getSouthWest(), bounds.getNorthEast()]), { padding: [10, 10] });
    const w = (kt, pop, hu) => `<div><b>${pop == null ? '–' : nf(pop)}</b><span>residents in ${kt}-kt winds${hu != null ? ` · ${nf(hu)} homes` : ''}</span></div>`;
    side.innerHTML = `<h3>${esc(s.storm_label)}</h3>
      <p class="lede">Closest on ${dateTxt(s.closest_date_ast)}: centre ${nf(s.closest_nmi, 1)} nmi from ${esc(s.closest_estate)}, ${esc(s.closest_island)}.</p>
      <dl><dt>Strength then</dt><dd>${catPill(s.wind_at_closest_kt)}</dd>
          <dt>Peak strength</dt><dd>${catPill(s.peak_wind_kt)}${s.min_pressure_mb ? ` <small class="mini">${nf(s.min_pressure_mb)} mb</small>` : ''}</dd>
          <dt>St. Croix</dt><dd>${nf(s.stx_nmi, 1)} nmi</dd><dt>St. Thomas</dt><dd>${nf(s.stt_nmi, 1)} nmi</dd><dt>St. John</dt><dd>${nf(s.stj_nmi, 1)} nmi</dd></dl>
      ${f ? `<div class="wind3">${w(34, s.pop_in_34kt, s.housing_in_34kt)}${w(50, s.pop_in_50kt)}${w(64, s.pop_in_64kt, s.housing_in_64kt)}</div>
      <div class="legend"><div><i style="background:${FIELD_C[64]}"></i>Hurricane-force winds (64 kt+)</div><div><i style="background:${FIELD_C[50]}"></i>50–63 kt</div><div><i style="background:${FIELD_C[34]}"></i>Tropical-storm-force (34–49 kt)</div><div><i style="background:#F3EEE4"></i>Outside the 34-kt winds</div></div>`
        : `<p class="mini">HURDAT2 has no wind radii before 2004, so only the track is shown.</p>`}
      <div class="legend"><div><i class="line" style="background:${C.ink}"></i>Track · dots every 6 hours, coloured by strength</div></div>`;
  };
  const choose = (v) => (MEASURES[v] ? showMeasure(v) : showStorm(v));
  pick.addEventListener('change', () => choose(pick.value));
  choose('m_in64');
  const selectStorm = (id) => {
    if (!S.tracks[id]) return;
    pick.value = id; choose(id);
    document.getElementById('map').scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  /* ---------- Charts ---------- */
  Chart.defaults.font.family = "'Satoshi', system-ui, sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.animation.duration = 300;
  Chart.defaults.color = C.muted;
  Chart.defaults.plugins.legend.labels.boxWidth = 10;
  Chart.defaults.plugins.legend.labels.boxHeight = 10;
  Chart.defaults.plugins.tooltip.backgroundColor = C.ink;
  Chart.defaults.plugins.tooltip.padding = 10;
  const grid = { color: C.line, drawTicks: false };
  new Chart(document.getElementById('cDecades'), {
    type: 'bar',
    data: { labels: S.decades.map((d) => d.label), datasets: [
      { label: 'Tropical storms', data: S.decades.map((d) => d.tropical_storms), backgroundColor: C.seaL },
      { label: 'Hurricanes (Cat 1–2)', data: S.decades.map((d) => d.hurricanes_cat12), backgroundColor: C.coralL },
      { label: 'Major (Cat 3+)', data: S.decades.map((d) => d.major_hurricanes), backgroundColor: '#8E3424' },
    ] },
    options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom' },
      tooltip: { callbacks: { footer: (it) => { const d = S.decades[it[0].dataIndex]; return d.years_covered < 10 ? `${d.years_covered} seasons so far` : ''; } } } },
      scales: { x: { stacked: true, grid: { display: false }, ticks: { autoSkip: true, maxRotation: 0 } }, y: { stacked: true, grid, ticks: { precision: 0 }, title: { display: true, text: 'Storms' } } } },
  });

  const popStorms = S.storms.filter((s) => s.pop_in_34kt > 0).sort((a, b) => a.closest_date_ast < b.closest_date_ast ? -1 : 1);
  const narrow = window.matchMedia('(max-width: 560px)').matches; // phones: bars run sideways
  const popAxis = { stacked: true, grid, max: Math.ceil(m.population / 10000) * 10000, ticks: { callback: (v) => `${v / 1000}k` }, title: { display: true, text: 'Residents (2020)' } };
  const nameAxis = { stacked: true, grid: { display: false }, ticks: { maxRotation: 60, minRotation: 0, autoSkip: false, font: { size: 11 } } };
  new Chart(document.getElementById('cPop'), {
    type: 'bar',
    data: { labels: popStorms.map((s) => s.storm_label), datasets: [
      { label: 'Hurricane-force (64 kt+)', data: popStorms.map((s) => s.pop_in_64kt), backgroundColor: '#A63F2B' },
      { label: '50–63 kt', data: popStorms.map((s) => s.pop_in_50kt - s.pop_in_64kt), backgroundColor: '#D9694F' },
      { label: 'Tropical-storm-force (34–49 kt)', data: popStorms.map((s) => s.pop_in_34kt - s.pop_in_50kt), backgroundColor: '#F2B9A6' },
    ] },
    options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom' },
      tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${nf(c.raw)} residents`, footer: (it) => `In 34-kt winds or stronger: ${nf(popStorms[it[0].dataIndex].pop_in_34kt)}` } } },
      onClick: (_, els) => { if (els.length) selectStorm(popStorms[els[0].index].storm_id); },
      indexAxis: narrow ? 'y' : 'x',
      scales: narrow ? { x: popAxis, y: nameAxis } : { x: nameAxis, y: popAxis } },
  });

  /* ---------- Return periods ---------- */
  const retBody = document.querySelector('#tReturns tbody');
  const drawRet = (first) => {
    retBody.innerHTML = S.returns.filter((r) => r.first_season === first).map((r) => `<tr>
      <td>${esc(r.level)}</td><td class="n">${nf(r.storms)}</td>
      <td class="n">${r.return_period_years == null ? '–' : `${nf(r.return_period_years, 1)} years`}</td>
      <td class="n">${nf(r.pct_years_with_one, 0)}% <small>${nf(r.years_with_one)} of ${nf(r.years)}</small></td>
      <td>${esc(r.most_recent || '–')}</td></tr>`).join('');
  };
  const toggle = (id, fn) => {
    const g = document.getElementById(id);
    g.addEventListener('click', (ev) => { const b = ev.target.closest('button'); if (!b) return;
      g.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); fn(b.dataset.k); });
  };
  toggle('retToggle', (k) => drawRet(+k));
  drawRet(1851);

  /* ---------- Storm table ---------- */
  let stormMode = 'hu', stormN = 12;
  const stormBody = document.querySelector('#tStorms tbody');
  const stormMore = document.getElementById('stormMore');
  const drawStorms = () => {
    const list = S.storms.filter((s) => s.is_near && s.is_ts_plus && (stormMode === 'all' || s.is_hurricane));
    stormBody.innerHTML = list.slice(0, stormN).map((s) => `<tr${S.tracks[s.storm_id] ? ` data-id="${s.storm_id}" class="click" tabindex="0"` : ''}>
      <td><b>${esc(s.storm_label)}</b></td><td>${dateTxt(s.closest_date_ast)}</td>
      <td class="n">${nf(s.closest_nmi, 0)} nmi<small>${esc(s.closest_island)}</small></td>
      <td>${catPill(s.wind_at_closest_kt)}</td>
      <td class="n">${s.pop_in_64kt == null ? '<small>before 2004</small>' : nf(s.pop_in_64kt)}</td></tr>`).join('');
    stormMore.hidden = list.length <= 12;
    stormMore.textContent = stormN < list.length ? `Show all ${list.length}` : 'Show fewer';
  };
  stormMore.addEventListener('click', () => { const list = S.storms.filter((s) => s.is_near && s.is_ts_plus && (stormMode === 'all' || s.is_hurricane)); stormN = stormN < list.length ? 999 : 12; drawStorms(); });
  stormBody.addEventListener('click', (ev) => { const tr = ev.target.closest('tr[data-id]'); if (tr) selectStorm(tr.dataset.id); });
  stormBody.addEventListener('keydown', (ev) => { const tr = ev.target.closest('tr[data-id]'); if (tr && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); selectStorm(tr.dataset.id); } });
  toggle('stormToggle', (k) => { stormMode = k; stormN = 12; drawStorms(); });
  drawStorms();

  /* ---------- Estate table ---------- */
  let estN = 12, q = '';
  const estBody = document.querySelector('#tEstates tbody');
  const estMore = document.getElementById('estMore');
  const estSorted = [...S.estates].sort((a, b) => b.times_in_64kt_since_2004 - a.times_in_64kt_since_2004 || b.population - a.population);
  const drawEst = () => {
    const list = q ? estSorted.filter((e) => `${e.estate_name} ${e.island}`.toLowerCase().includes(q)) : estSorted;
    estBody.innerHTML = list.slice(0, estN).map((e) => `<tr>
      <td>${esc(e.estate_name)}<small>${esc(e.island)}</small></td><td class="n">${nf(e.population)}</td>
      <td class="n">${nf(e.hurricanes_near)}</td><td class="n">${nf(e.times_in_64kt_since_2004)}</td>
      <td>${esc(e.last_in_64kt || '–')}</td></tr>`).join('') || '<tr><td colspan="5">No estate matches that name.</td></tr>';
    estMore.hidden = list.length <= 12;
    estMore.textContent = estN < list.length ? `Show all ${list.length}` : 'Show fewer';
  };
  estMore.addEventListener('click', () => { estN = estN >= 999 ? 12 : 999; drawEst(); });
  document.getElementById('estSearch').addEventListener('input', (ev) => { q = ev.target.value.trim().toLowerCase(); estN = 12; drawEst(); });
  drawEst();
})();
