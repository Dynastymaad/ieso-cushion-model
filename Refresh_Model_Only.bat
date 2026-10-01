@echo off
rem Refresh_Model_Only.bat -- skips the pulls; rebuilds the model, the desk page and the checklist workbook, then opens the workbook.
cd /d "%~dp0"
echo Rebuilding from the data already pulled (about 2 minutes); leave this window open.
python -X utf8 morning.py --model
echo.
python model\open_checklist.py
pause
