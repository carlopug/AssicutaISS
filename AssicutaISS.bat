@echo off
rem AssicutaISS - avvio
setlocal
cd /d "%~dp0"
set "VENV=%~dp0.venv"

if not exist "%VENV%\Scripts\pythonw.exe" (
    echo Prima installazione: creo l'ambiente Python in %VENV% ...
    python -m venv "%VENV%" || (echo Python non trovato. Installa Python 3.11+ da python.org & pause & exit /b 1)
    rem esclude la venv dalla sincronizzazione Dropbox
    powershell -NoProfile -Command "Set-Content -Path '%VENV%' -Stream com.dropbox.ignored -Value 1" 2>nul
    "%VENV%\Scripts\python.exe" -m pip install --upgrade pip
)

rem installa eventuali dipendenze nuove (veloce se è già tutto presente)
"%VENV%\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt || (pause & exit /b 1)

start "" "%VENV%\Scripts\pythonw.exe" main.py
