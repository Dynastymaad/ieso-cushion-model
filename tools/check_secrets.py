"""Blocks a commit if a credential file or an obvious secret is staged.
Run by setup_github.bat and by the git pre-commit hook. It never prints secret values."""
import re, subprocess, sys
BAD_NAMES = re.compile(r'(^|/)(db\.json|nrg\.json|sv\.json|aeso_key\.txt|\.env)$|\.(key|pem)$', re.I)
BAD_TEXT = re.compile(r'(password|pwd|passwd|secret|api[_-]?key|token)\s*["\']?\s*[:=]\s*["\'][^"\'\s]{4,}', re.I)
files = subprocess.run(['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'], capture_output=True, text=True).stdout.split()
bad = []
for f in files:
    if BAD_NAMES.search(f): bad.append(f'{f}  (credential file)'); continue
    if f.endswith(('.csv', '.zip', '.gz', '.xlsx', '.png', '.xml')): continue
    try: txt = subprocess.run(['git', 'show', f':{f}'], capture_output=True, text=True, errors='ignore').stdout
    except Exception: continue
    if BAD_TEXT.search(txt): bad.append(f'{f}  (looks like it contains a password/key)')
if bad:
    print('STOPPED: these staged files look like credentials -- they were NOT committed:'); [print('   ', b) for b in bad]
    print('Remove them with:  git rm --cached <file>   and add the name to .gitignore'); sys.exit(1)
print(f'secret check ok ({len(files)} files)')
