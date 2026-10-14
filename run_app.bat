@echo off
REM Double-click or run from the project folder (Command Prompt).
cd /d "%~dp0"
call .sales\Scripts\activate.bat
python -m streamlit run app.py
