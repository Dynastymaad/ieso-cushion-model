@echo off
REM One-time: put this folder on GitHub as a PRIVATE repo. Credentials are excluded by .gitignore
REM and a secret check blocks the commit if one slips in. Run from this folder.
cd /d "%~dp0"
where git >nul 2>nul || (echo Git is not installed. Install it from https://git-scm.com/download/win then run this again. & pause & exit /b 1)
where gh  >nul 2>nul || (echo GitHub CLI is not installed. Install it from https://cli.github.com then run this again. & pause & exit /b 1)
gh auth status >nul 2>nul || (echo You are not logged in to GitHub. Run:  gh auth login   then run this again. & pause & exit /b 1)
set /p REPO=Repo name (e.g. ontario-cushion-model, or YOURORG/ontario-cushion-model): 
if "%REPO%"=="" set REPO=ontario-cushion-model
if not exist .git git init -b main
git config core.autocrlf true
copy /y tools\pre-commit .git\hooks\pre-commit >nul
git add -A
python tools\check_secrets.py || (pause & exit /b 1)
git commit -m "Ontario cushion model: initial import" || echo (nothing new to commit)
git remote get-url origin >nul 2>nul && (git push -u origin main) || (gh repo create %REPO% --private --source . --remote origin --push)
echo.
echo Done. Open it with:  gh repo view --web
pause
