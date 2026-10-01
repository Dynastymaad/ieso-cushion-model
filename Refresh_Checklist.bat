@echo off
rem Refresh_Checklist.bat -- runs every morning pull, the model, the desk page and the checklist workbook, then opens the workbook.
cd /d "%~dp0"
echo Running the morning pulls and the model. This takes 5-20 minutes; leave this window open.
python -X utf8 morning.py
echo.
python model\open_checklist.py
pause
