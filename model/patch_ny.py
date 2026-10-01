p = 'model/page_template.html'; s = open(p, encoding='utf-8').read()
assert 'id="nysec"' not in s
html = '''  <section id="nysec">
    <div class="sechead"><h2>New York interchange</h2><span class="muted small" id="nysub"></span></div>
    <div class="small" id="nynote"></div>
    <div class="tablewrap"><table id="nyhrs"></table></div>
    <div class="grid2">
      <div class="panel"><h3>Last 10 days, peak HE16–21 average</h3><div class="tablewrap" style="border:0"><table id="nydays"></table></div><div class="small muted">Level = percentile vs the prior 60 days. NYISO column is NY's DAM schedule at the Ontario proxy; IESO column is what cleared in IESO's DAM.</div></div>
      <div class="panel"><h3>Does it matter? (model sell hours, Jul 2025 – now)</h3><div class="tablewrap" style="border:0"><table id="nytest"></table></div><div class="small muted" id="nytestn"></div></div>
    </div>
  </section>

  <section id="tesec">
    <div class="sechead"><h2>Load forecasts: Tesla vs IESO</h2><span class="muted small" id="tesub"></span></div>
    <div class="small" id="tenote"></div>
    <div class="tablewrap"><table id="tehrs"></table></div>
  </section>

  <section>
    <div class="sechead"><h2>Tomorrow's supply stack</h2>'''
anchor = '''  <section>
    <div class="sechead"><h2>Tomorrow's supply stack</h2>'''
assert anchor in s; s = s.replace(anchor, html, 1)

js = r'''function nyRender(){
  const N = B.ny, T = B.tesla;
  if (!N){ $('#nysec').hidden = true; } else {
    $('#nysec').hidden = false;
    const sg = v => v==null ? '–' : (v>0?'+':'')+fmt0(v);
    const lv = l => l==null ? '–' : l==='High' ? '<b>High</b>' : l;
    $('#nysub').textContent = N.posted ? `NYISO DAM schedule for ${dlabel(N.date)}` : `NYISO DAM schedule for ${dlabel(N.date)} not posted at run time — showing ${dlabel(N.ref_day)}`;
    const pk = N.hours.filter(h => h.he>=16 && h.he<=21), avg = k => { const v = pk.map(h=>h[k]).filter(x=>x!=null); return v.length ? v.reduce((a,b)=>a+b,0)/v.length : null; };
    const hi = pk.filter(h => h.lvl==='High').map(h=>'HE'+h.he);
    $('#nynote').innerHTML = `<div class="note">Peak HE16–21: Ontario → NY scheduled ${fmt0(avg('ny_oh'))} MW vs a usual ${fmt0(avg('med30'))} MW${hi.length? ' — <b>high</b> at '+hi.join(', '):''}${N.posted?'':' (yesterday\'s schedule, a guide only)'}. NY Zone A DA for ${dlabel(N.date)} averages $${fmt(avg('nyA'))} at the peak vs our East DA forecast $${fmt(avg('p_da'))} (spread ${sg(avg('spr'))} $/MWh). When NY clears well below Ontario, exports to NY lose their pull. Positive MW = Ontario exporting to NY.</div>`;
    let r = '<tr><th>HE</th><th>ON→NY MW</th><th>Usual (30d med)</th><th>Pct</th><th class="l">Level</th><th>NY Zone A DA</th><th>Usual</th><th>East DA fcst</th><th>NY − ON</th></tr>';
    for (const h of N.hours.filter(h=>h.he>=5 && h.he<=23)) r += `<tr><td>${h.he}</td><td>${sg(h.ny_oh)}</td><td>${sg(h.med30)}</td><td>${h.pct==null?'–':h.pct}</td><td class="l">${lv(h.lvl)}</td><td>${fmt(h.nyA)}</td><td>${fmt(h.nyA_med30)}</td><td>${fmt(h.p_da)}</td><td>${sg(h.spr)}</td></tr>`;
    $('#nyhrs').innerHTML = r;
    r = '<tr><th class="l">Day</th><th>NYISO ON→NY</th><th class="l">Level</th><th>IESO NY export</th><th class="l">Level</th><th>IESO NY import</th></tr>';
    for (const d of N.days.slice().reverse()) r += `<tr><td class="l">${dlabel(d.date)}</td><td>${sg(d.ny_pk)}</td><td class="l">${lv(d.ny_pk_lvl)}</td><td>${fmt0(d.ieso_exp_pk)}</td><td class="l">${lv(d.ieso_exp_lvl)}</td><td>${fmt0(d.ieso_imp_pk)}</td></tr>`;
    $('#nydays').innerHTML = r;
    const t = (N.test||{})[HUB] || {};
    r = '<tr><th class="l">Quartile</th><th>ON→NY MW</th><th>DA−RT</th><th>NY − ON $</th><th>DA−RT</th></tr>';
    for (let i=0;i<4;i++){ const a=(t.ny_dni_oh||[])[i]||{}, b=(t.spr||[])[i]||{}; r += `<tr><td class="l">Q${i+1}</td><td>${fmt0(a.lo)} to ${fmt0(a.hi)}</td><td>${fmt(a.mean,1)}</td><td>${fmt0(b.lo)} to ${fmt0(b.hi)}</td><td>${fmt(b.mean,1)}</td></tr>`; }
    $('#nytest').innerHTML = r;
    $('#nytestn').textContent = `Average DA−RT $/MWh on hours the model sold, ${ZN[HUB]}. Sells stayed positive in every quartile; high exports to NY did not hurt them. Best when NY cleared far below Ontario's forecast. Context only — not a model input.`;
  }
  if (!T){ $('#tesec').hidden = true; return; }
  $('#tesec').hidden = false;
  const sg = v => v==null ? '–' : (v>0?'+':'')+fmt0(v), b = T.bias || {};
  $('#tesub').textContent = `Tesla run issued ${T.issued || '–'} (latest loaded before the bid)`;
  const pk = T.hours.filter(h => h.he>=16 && h.he<=21), av = k => { const v = pk.map(h=>h[k]).filter(x=>x!=null); return v.length ? v.reduce((a,c)=>a+c,0)/v.length : null; };
  $('#tenote').innerHTML = `<div class="note">Tesla is normally <b>below</b> IESO: since July IESO's forecast has run ${sg((b.ieso_adq||{}).all)} MW above actual load (${sg((b.ieso_adq||{}).peak)} at HE16–20), Tesla ${sg((b.tesla||{}).all)} (${sg((b.tesla||{}).peak)} at the peak). So "Tesla below IESO" is the usual state, not a signal. What matters is the gap vs its usual level: at HE16–21 tomorrow Tesla is ${sg(av('gap'))} MW vs IESO's 07:50 Adequacy demand, against a usual ${sg(av('usual'))} — ${sg(av('vs_usual'))} MW vs normal${av('vs_usual')>150?' (Tesla relatively <b>high</b>: more load than IESO\'s usual over-forecast implies)':av('vs_usual')<-150?' (Tesla relatively <b>low</b>)':''}. Against IESO\'s own earlier day-ahead forecast Tesla is ${sg(av('gap_fc'))} MW.</div>`;
  let r = '<tr><th>HE</th><th>Tesla</th><th>IESO Adequacy 07:50</th><th>IESO forecast</th><th>Tesla − Adequacy</th><th>Usual gap (30d)</th><th>vs usual</th><th>Tesla − IESO fcst</th></tr>';
  for (const h of T.hours.filter(h=>h.he>=5 && h.he<=23)) r += `<tr><td>${h.he}</td><td>${fmt0(h.tesla)}</td><td>${fmt0(h.adq)}</td><td>${fmt0(h.ieso_fc)}</td><td>${sg(h.gap)}</td><td>${sg(h.usual)}</td><td>${sg(h.vs_usual)}</td><td>${sg(h.gap_fc)}</td></tr>`;
  $('#tehrs').innerHTML = r;
}
function render(){'''
assert s.count('function render(){') == 1; s = s.replace('function render(){', js, 1)
s = s.replace('eoRender(); otRender(); showTab();', 'eoRender(); otRender(); nyRender(); showTab();', 1)
assert 'nyRender(); showTab' in s
open(p, 'w', encoding='utf-8').write(s); print('patched')
