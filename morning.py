"""morning.py -- the whole bid-morning refresh in one command, in the right order.

    python morning.py            # pulls + model + page  (then open site\\index.html, or ask Claude to publish)
    python morning.py --model    # skip the pulls, just rebuild the model and page from what is already in cache\\
    python morning.py --full     # same, but re-pull all history from the databases (automatic on Mondays)
    python morning.py --wind     # after ~07:40 MT: top up Meteologica wind, the NYISO DAM (~07:35 MT) and the latest IESO files, rebuild (about 2-3 min)

Run it after IESO's pre-DA Adequacy file for tomorrow is out, ideally after the NYISO DAM (about 07:35 MT). The IESO DAM closes
08:00 MT (10:00 EPT) all year. Clock notes (Nov 1 2026): IESO publishes on EST all year, so its pre-DA Adequacy (~07:50 EST) lands
about 05:50 MT in winter and 06:50 MT in summer. The Warehouse loads vendor load at 04:28 MT and wind at 07:18 MT year-round.
Bid-time cutoffs on IESO timestamps are D-1 09:00 EST: that is the 08:00 MT deadline in summer and 07:00 MT in winter (one hour
early, never after the bid). Load forecasts are keyed from their UTC stamp, so the fall-back day keeps all 24 hours."""
import subprocess, sys, time, os
from pathlib import Path
HERE = Path(__file__).resolve().parent
PY = sys.executable
FULL = time.localtime().tm_wday == 0 or '--full' in sys.argv   # Nov 5 2026: Mondays (or --full) re-pull all history; other days only the last 45 days
REC = [] if FULL else ['--recent', '45']
PULLS = [['pull_history.py', '--since', '2025-04-01'] + REC,
         ['pull_history.py', '--only', 'outages', '--since', '2025-05-01'] + REC,
         ['ieso_backfill.py']]
OPTIONAL_PULLS = [['ieso_fwd35.py'], ['model/wx_live.py']]   # Nov 5 2026: wx_live = bid-time temperatures for the Temp swing card point              # 35-day outlook (Outages tab only): a failure does not stop the run
OPTIONAL = [['model/checklist_xlsx.py'], ['model/congestion/cong_read.py', '--json'],
            ['model/research/physics_history.py', 'EAST'], ['model/research/physics_history.py', 'OTTAWA'], ['model/practice_data.py']]   # Nov 1 2026: practice page (site/practice.html) with the newest settled days   # congestion read for tomorrow (read-only, Oct 13 2026)          # failures here do not stop the morning run
MODEL = [['model/parse_archive.py'], ['model/update_intertie_actual.py'], ['model/adq_fallback.py'], ['model/load_edge.py'], ['model/outage_timeline.py'],
         ['model/supply_fc.py'], ['model/blocks.py'], ['model/zone_backtest.py', 'EAST', 'OTTAWA'],
         ['model/da_virtual_bt.py', 'EAST', 'OTTAWA'], ['model/da_cleared_ties.py'], ['model/run_model.py'], ['model/build_page.py']]
# Oct 31 2026 pipeline audit: these used to be one-off runs and had gone stale (hydro history Sep 27, block model + accuracy files Sep 24-28,
# East-Ottawa & Quebec tab Sep 27-28). blocks.py / zone_backtest.py are now in MODEL above (they feed the DA forecast); the tab extras below
# run every morning just before run_model, a failure there does not stop the ladders. pipeline_health.py flags any input that stops updating.
EXTRA = [['model/quebec.py'], ['model/quebec2.py'], ['model/qc_adq2x.py'], ['model/pipeline_health.py']]
WEEKLY = [['model/outage_priced.py'], ['model/fund_read.py', '--track'], ['model/research/physics_history_stats.py']]   # Nov 1 2026: refresh the tier record on the physics panel                              # Mondays (or with --weekly)
WEEKLY_PULLS = [['pull_history.py', '--only', 'horizon', '--since', '2025-05-01']]                    # outage lead history (Outages tab), Mondays

def run(cmd, optional=False):
    t = time.time(); print(f'\n>>> {" ".join(cmd)}', flush=True)
    r = subprocess.run([PY, '-X', 'utf8'] + cmd, cwd=HERE, env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'))   # Windows: write files as UTF-8
    print(f'<<< {cmd[0]} finished in {time.time()-t:.0f}s (exit {r.returncode})', flush=True)
    if r.returncode != 0 and optional: print(f'WARNING: {cmd[0]} failed; the ladders are fine, only this extra output is missing.'); return
    if r.returncode != 0: sys.exit(f'STOPPED: {cmd[0]} failed -- fix that step and re-run (use --model to skip the pulls).')

SOFT = {'model/quebec.py'}   # extras inside a required group: a failure only warns
def run_par(cmds, optional=False):
    """Nov 5 2026: run independent steps at the same time (each step's output is printed in full when it finishes, in order)."""
    if '--serial' in sys.argv or len(cmds) == 1:
        for c in cmds: run(c, optional)
        return
    from concurrent.futures import ThreadPoolExecutor
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'); t0 = time.time()
    def one(c):
        t = time.time(); r = subprocess.run([PY, '-X', 'utf8'] + c, cwd=HERE, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        return c, r, time.time() - t
    print(f'\n=== in parallel: {" | ".join(c[0].split("/")[-1] for c in cmds)}', flush=True)
    with ThreadPoolExecutor(max_workers=min(4, len(cmds))) as ex: res = list(ex.map(one, cmds))
    bad = []
    for c, r, dt_ in res:
        print(f'\n>>> {" ".join(c)}'); print((r.stdout or '').rstrip()); err = (r.stderr or '').rstrip()
        if err: print(err)
        print(f'<<< {c[0]} finished in {dt_:.0f}s (exit {r.returncode})', flush=True)
        if r.returncode != 0: bad.append(c[0])
    print(f'=== parallel group done in {time.time()-t0:.0f}s', flush=True)
    soft = [b_ for b_ in bad if b_ in SOFT]; bad = [b_ for b_ in bad if b_ not in SOFT]
    if soft: print(f'WARNING: {", ".join(soft)} failed; the ladders are fine, only that extra output is missing.')
    if bad and optional: print(f'WARNING: {", ".join(bad)} failed; the ladders are fine, only that extra output is missing.'); return
    if bad: sys.exit(f'STOPPED: {", ".join(bad)} failed -- fix that step and re-run (use --model to skip the pulls).')

if __name__ == '__main__':
    t0 = time.time()
    if '--wind' in sys.argv:
        run(['pull_history.py', '--only', 'windtopup'])
        run(['ieso_backfill.py', '--quick', '--nyiso'], optional=True)   # Nov 1 2026: NYISO DAM + newest IESO prices/Adequacy, so a late refresh has them
    elif '--model' not in sys.argv:
        run_par([PULLS[0], PULLS[2]])            # Warehouse/sandbox pull and the IESO public files at the same time (different folders)
        run(PULLS[1])
        for c in OPTIONAL_PULLS: run(c, optional=True)
        if time.localtime().tm_wday == 0 or '--weekly' in sys.argv:
            for c in WEEKLY_PULLS: run(c, optional=True)
    try:                                                # Meteologica wind for tomorrow lands in the Warehouse ~07:18 MT
        import pandas as pd, datetime as dt
        tom = (dt.date.today() + dt.timedelta(days=1)).isoformat(); w = pd.read_csv(HERE / 'cache' / 'ieso_wind_fc.csv', usecols=['DataSourceName', 'EffectiveDateTime'])
        if not ((w.DataSourceName == 'Meteologica') & w.EffectiveDateTime.astype(str).str.startswith(tom)).any():
            print(f'\nNOTE: Meteologica wind for {tom} is not in yet (the Warehouse loads it ~07:18 MT). After 07:20 MT run:  python morning.py --wind')
    except Exception as ex: print('Meteologica check skipped:', ex)
    # Nov 5 2026: same steps as before, independent ones run side by side (python morning.py --serial = the old one-at-a-time order)
    run(['model/parse_archive.py'])                                                    # everything below reads its outputs
    run_par([['model/update_intertie_actual.py'], ['model/adq_fallback.py'], ['model/load_edge.py'], ['model/outage_timeline.py'],
             ['model/supply_fc.py'], ['model/blocks.py'], ['model/da_cleared_ties.py']])
    run_par([['model/zone_backtest.py', 'EAST', 'OTTAWA'], ['model/da_virtual_bt.py', 'EAST', 'OTTAWA'], ['model/quebec.py']])   # needs blocks/load_edge | supply_fc/interties
    if time.localtime().tm_wday == 0 or '--weekly' in sys.argv:
        for c in WEEKLY: run(c, optional=True)
    run_par([['model/quebec2.py'], ['model/qc_adq2x.py'], ['model/pipeline_health.py'], ['model/congestion/cong_read.py', '--json']], optional=True)   # cong_read first so the Market changes box has today's outages
    for c in MODEL[-2:]: run(c)
    try:                                                # GitHub Pages serves /docs: keep a copy of the desk page there
        import shutil; d = HERE / 'docs'; d.mkdir(exist_ok=True); (d / '.nojekyll').touch()
        shutil.copyfile(HERE / 'site' / 'index.html', d / 'index.html')
    except Exception as ex: print('docs copy skipped:', ex)
    run_par([['model/checklist_xlsx.py'], ['model/research/physics_history.py', 'EAST'], ['model/research/physics_history.py', 'OTTAWA']], optional=True)
    run(['model/practice_data.py'], optional=True)                                      # needs both physics histories
    if '--push' in sys.argv:                      # save the refreshed code/page to GitHub (credentials blocked by .gitignore + check)
        if not (HERE / '.git').exists(): print('\n--push: this folder is not linked to GitHub yet (see GITHUB_SETUP.md)')
        else:
            # Nov 2 2026: no automatic 'git gc' (OneDrive locks .git/objects folders -> endless 'Deletion of directory ... failed' prompts)
            g = lambda *a: subprocess.run(['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false'] + list(a), cwd=HERE, env=dict(os.environ, GIT_ASK_YESNO='false'))
            lk = HERE / '.git' / 'index.lock'                 # stale lock left by a crashed git / OneDrive sync
            if lk.exists() and time.time() - lk.stat().st_mtime > 600:
                try: lk.unlink(); print('--push: removed a stale .git/index.lock')
                except Exception as ex: print('--push: could not remove .git/index.lock:', ex)
            g('add', '-A')
            if subprocess.run([PY, 'tools/check_secrets.py'], cwd=HERE).returncode != 0: print('--push: STOPPED by the secret check, nothing uploaded')
            else:
                g('commit', '-q', '-m', f'Daily refresh {time.strftime("%Y-%m-%d")}'); r = g('push', '-q')
                print('--push: pushed to GitHub' if r.returncode == 0 else '--push: push failed (run  git push  to see why)')
    print(f'\nDONE in {(time.time()-t0)/60:.1f} min. Open site\\index.html for the ladders and site\\Checklist_Deviations.xlsx for the pre-model checklist, or tell Claude to publish it.')
