@echo off
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3.10+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
if not exist .venv python -m venv .venv
.venv\Scripts\python -m pip install -q --upgrade pip pywebview || (echo Install failed & pause & exit /b 1)
powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Metals.lnk');$s.TargetPath='%~dp0.venv\Scripts\pythonw.exe';$s.Arguments='app\main.py';$s.WorkingDirectory='%~dp0';$s.IconLocation='%~dp0assets\icon.ico';$s.Save()"
echo Done. Use the "Metals" shortcut on your desktop.
pause
