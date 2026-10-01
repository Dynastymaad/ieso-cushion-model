"""open_checklist.py -- open the newest site/Checklist_Deviations*.xlsx (used by the Refresh .bat files)."""
import os, pathlib
p = sorted((pathlib.Path(__file__).resolve().parents[1] / 'site').glob('Checklist_Deviations*.xlsx'), key=lambda x: x.stat().st_mtime)
if p:
    print('opening', p[-1].name)
    try: os.startfile(p[-1])                     # Windows
    except AttributeError: print(p[-1])
else: print('no checklist workbook found in site\\')
