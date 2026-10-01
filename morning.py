"""morning.py -- the whole bid-morning refresh in one command, in the right order.

    python morning.py            # pulls + model + page  (then open site\\index.html, or ask Claude to publish)
    python morning.py --model    # skip the pulls, just rebuild the model and page from what is already in cache\\

Run it after IESO's pre-DA Adequacy file for tomorrow is out (about 06:50 MT), ideally after the NYISO DAM
(about 07:35 MT). The IESO DAM closes 08:00 MT (10:00 EPT)."""
import subprocess, sys, time, os
from pathlib import Path
HERE = Path(__file__).resolve().parent
PY = sys.executable
PULLS = [['pull_history.py', '--since', '2025-04-01'],
         ['pull_history.py', '--only', 'outages', '--since', '2025-05-01'],
         ['ieso_backfill.py']]
OPTIONAL_PULLS = [['ieso_fwd35.py']]              # 35-day outlook (Outages tab only): a failure does not stop the run
OPTIONAL = [['model/checklist_xlsx.py']]          # failures here do not stop the morning run
MODEL = [['model/parse_archive.py'], ['model/adq_fallback.py'], ['model/load_edge.py'], ['model/outage_timeline.py'],
         ['model/da_virtual_bt.py', 'EAST', 'OTTAWA'], ['model/run_model.py'], ['model/build_page.py']]

def run(cmd, optional=False):
    t = time.time(); print(f'\n>>> {" ".join(cmd)}', flush=True)
    r = subprocess.run([PY, '-X', 'utf8'] + cmd, cwd=HERE, env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'))   # Windows: write files as UTF-8
    print(f'<<< {cmd[0]} finished in {time.time()-t:.0f}s (exit {r.returncode})', flush=True)
    if r.returncode != 0 and optional: print(f'WARNING: {cmd[0]} failed; the ladders are fine, only this extra output is missing.'); return
    if r.returncode != 0: sys.exit(f'STOPPED: {cmd[0]} failed -- fix that step and re-run (use --model to skip the pulls).')

if __name__ == '__main__':
    t0 = time.time()
    if '--model' not in sys.argv:
        for c in PULLS: run(c)
        for c in OPTIONAL_PULLS: run(c, optional=True)
    for c in MODEL: run(c)
    for c in OPTIONAL: run(c, optional=True)
    print(f'\nDONE in {(time.time()-t0)/60:.1f} min. Open site\\index.html for the ladders and site\\Checklist_Deviations.xlsx for the pre-model checklist, or tell Claude to publish it.')
