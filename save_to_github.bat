@echo off
REM Daily/whenever: save your latest changes to GitHub.
cd /d "%~dp0"
git add -A
python tools\check_secrets.py || (pause & exit /b 1)
set /p MSG=Describe the change (Enter = "update"): 
if "%MSG%"=="" set MSG=update
git commit -m "%MSG%" && git push
pause
