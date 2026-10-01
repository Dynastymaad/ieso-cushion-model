p = 'model/page_template.html'; s = open(p, encoding='utf-8').read()
assert 'id="cksec"' not in s
html = '''  <div class="stats" id="stats"></div>

  <section id="cksec">
    <div class="sechead"><h2>Your checks before the model</h2><span class="muted small" id="cksub"></span></div>
    <div class="ckgrid" id="ckgrid"></div>
    <div class="small muted">Rules of thumb (tested, notes/Fundamentals_Wind_Solar_Temp_Load.md): RT−DA moves ≈ +$30 per GW of load above what DA expects, ≈ −$32 to −$45 per GW of extra wind (about double when headroom &lt; 7,000). Context only — none of this feeds the signal.</div>
  </section>
'''
anchor = '  <div class="stats" id="stats"></div>\n'
assert anchor in s; s = s.replace(anchor, html, 1)
css = '.ckgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}\n.ck{border:1px solid var(--line, #ccc);border-radius:6px;padding:10px 12px;display:flex;flex-direction:column;gap:4px}\n.ck h3{margin:0 0 4px;font-size:13px;text-transform:uppercase;letter-spacing:.04em}\n.ck .r{display:flex;justify-content:space-between;gap:10px;font-size:13px;font-variant-numeric:tabular-nums}\n.ck .r span:first-child{color:var(--muted, #666)}\n.ck .v{margin-top:4px;font-size:12.5px;font-weight:600}\n'
s = s.replace('.note{', css + '.note{', 1)
js = r'''function ckRender(){
  const K = B.checks; if (!K){ $('#cksec').hidden = true; return; } $('#cksec').hidden = false;
  const sg = v => v==null ? '–' : (v>0?'+':'')+fmt0(v), R = (a,b) => `<div class="r"><span>${a}</span><span>${b}</span></div>`;
  const T = K.temp || {}, L = K.load || {}, W = K.wind || {}, S = K.supply || {}, N = K.net || {}, lw = L.lastweek;
  $('#cksub').textContent = `${dlabel(K.date)} · ${K.day_type} · ${K.month}`;
  const card = (t, rows, v) => `<div class="ck"><h3>${t}</h3>${rows.join('')}${v?`<div class="v">${v}</div>`:''}</div>`;
  const c = [];
  // 1 calendar + temperature
  c.push(card('1 · Calendar &amp; temperature', [
    R('Day type', `${K.day_type}${K.day_type==='Tue-Thu'?'':' ('+sg(T.offset)+' MW vs Tue–Thu)'}`),
    R('Toronto high / low', T.tmax==null?'–':`${T.tmax}°F / ${T.tmin}°F`),
    R('Daily average', T.tavg==null?'–':`${T.tavg}°F — ${T.zone}`),
    R('Load per °F here', T.slope==null?'–':`${fmt0(Math.abs(T.slope))} MW`),
    R('±3°F bust', T.bust==null?'–':`±${fmt0(T.bust)} MW`)],
    T.bust==null ? '' : (T.bust < 500 ? 'Temperature is a small risk tomorrow.' : 'Temperature is a real load risk — check model spread.')));
  // 2 load
  c.push(card('2 · Load (peak)', [
    R(`IESO forecast (HE${L.ieso_he})`, fmt0(L.ieso)),
    R('IESO + its 30-day miss', `${fmt0(L.ieso_adj)} (${sg(L.bias30)})`),
    R('Tesla' + (L.tesla_stale?' <b>(stale)</b>':''), fmt0(L.tesla)),
    R('<b>Your estimate (blend)</b>', `<b>${fmt0(L.blend)}</b>`),
    R('Tesla vs usual gap, HE16–20', sg(L.vs_usual)),
    R(lw?`Last week (${dlabel(lw.date)}) actual`:'Last week actual', lw?`${fmt0(lw.peak)} at ${lw.tavg}°F`:'–'),
    R('… temp-adjusted vs IESO', lw?sg(lw.gap):'–')],
    L.vs_usual==null ? '' : (L.tesla_stale ? 'Tesla is stale — lean on IESO + bias.' : (L.vs_usual <= -300 ? 'Tesla unusually low: load likely lighter than IESO (bearish RT).' : L.vs_usual >= 300 ? 'Tesla unusually high: IESO likely right or low (bullish RT).' : 'Tesla gap normal: no load tilt.'))));
  // 3 clouds (Apr-Sep only)
  if (K.cloud) c.push(card('3 · Clouds (midday)', [R('Toronto cloud cover HE11–15', `${K.cloud.mid}%`)], K.cloud.mid>=75?'Overcast: midday load higher, solar lower (bullish midday).':K.cloud.mid<=25?'Clear: midday load lower (bearish midday).':'Mixed cloud.'));
  // 4 wind
  const pr = K.pressure || {};
  c.push(card('4 · Wind (HE17–20)', [
    R('IESO', `${fmt0(W.ieso)} MW`), R('Meteologica', W.meteo==null?'–':`${fmt0(W.meteo)} MW (${sg(W.gap)})`),
    R(`Normal for ${K.month}`, `${fmt0(W.normal)} MW`), R('Ramp HE15 → HE20 (IESO)', `${sg(W.ramp)} MW`),
    R('Pressure, Toronto', pr.avg==null?'–':`${pr.avg} hPa, ${pr.change>0?'rising':'falling'} ${Math.abs(pr.change)} over the day`)],
    (W.gap!=null && Math.abs(W.gap)>=300 ? `Vendors disagree by ${fmt0(Math.abs(W.gap))} MW — a wind miss is likely. ` : '') + (W.ramp!=null && W.ramp<=-300 ? 'Wind falls into the peak (tighter evening).' : '') + (pr.change!=null && Math.abs(pr.change)>=8 ? ' Big pressure change: a front is passing — check its timing.' : '')));
  // 5 supply
  const st = (S.steps||[]).map(x => `HE${x.he} ${x.fuel} ${sg(x.mw)}`).join(', ');
  const rk = o => o && o.v!=null ? `${fmt0(o.v)} (30d avg ${fmt0(o.mean)}, ${o.rank}/${o.n})` : '–';
  c.push(card('5 · Supply', [R('Total outages', rk(S.tot)), R('Nuclear out', rk(S.nuc)), R('Gas out', rk(S.gas)),
    R('Steps HE14–24 (≥150 MW)', st || 'none'), R('Trips since the bid', sg(S.trips))],
    (S.steps||[]).some(x => x.he>=16 && x.he<=21) ? 'An outage starts or ends in the peak.' : 'Nothing starts or ends in the evening peak.'));
  // net
  c.push(card('Net it', [
    R(`Lowest peak headroom (HE${N.peak_head_he})`, `${fmt0(N.peak_head)} MW`),
    R('Your load vs IESO + bias', `${sg(N.load_surprise)} MW ≈ ${sg((N.load_surprise||0)*0.03)} $/MWh`),
    R('Meteologica vs IESO wind', N.wind_surprise==null?'–':`${sg(N.wind_surprise)} MW ≈ ${sg(-(N.wind_surprise||0)*0.032)} $/MWh`)],
    N.peak_head < 7000 ? 'Tight: DA tends to over-price risk.' : N.peak_head < 9500 ? 'Middle band: DA tends to under-price risk.' : 'Loose: little edge either way.'));
  $('#ckgrid').innerHTML = c.join('');
}
function render(){'''
assert s.count('function render(){') == 1; s = s.replace('function render(){', js, 1)
s = s.replace('stats(); fan();', 'stats(); ckRender(); fan();', 1); assert 'ckRender(); fan' in s
open(p, 'w', encoding='utf-8').write(s); print('patched')

r = 'model/run_model.py'; t = open(r).read()
old = "    site = C.ROOT / 'site' / 'data'"
assert old in t and 'checks_panel' not in t
t = t.replace(old, """    try:
        import checks_panel as CK
        out['checks'] = CK.build(out['target'], out)
    except Exception as ex: print('checks panel skipped:', ex)
""" + old, 1)
open(r, 'w').write(t); print('run_model ok')
