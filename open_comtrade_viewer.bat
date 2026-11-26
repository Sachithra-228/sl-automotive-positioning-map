@echo off
REM Rebuilds the Comtrade viewer from the raw JSON files and opens it in the browser.
cd /d "%~dp0data_praveen\data\raw\comtrade"
python build_comtrade_viewer.py
start "" "%cd%\00_comtrade_viewer.html"
