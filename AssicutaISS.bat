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

rem collegamento con l'icona del programma (si può copiare sul desktop o nella barra delle applicazioni)
if not exist "%~dp0AssicutaISS.lnk" if exist "%~dp0assets\icona.ico" (
    powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%~dp0AssicutaISS.lnk'); $s.TargetPath='%~dp0AssicutaISS.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0assets\icona.ico'; $s.WindowStyle=7; $s.Description='AssicutaISS - ISS SSTV Receiver for Robot36'; $s.Save()" 2>nul
)

start "" "%VENV%\Scripts\pythonw.exe" main.py
