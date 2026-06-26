@echo off
title Build Standalone Executable (PyInstaller)
echo =======================================================
echo     DUBBING PRO - STANDALONE BUILD SCRIPT
echo =======================================================
echo.
echo Step 1: Installing PyInstaller in virtualenv...
venv\Scripts\pip install pyinstaller

echo.
echo Step 2: Cleaning up old build folders...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo Step 3: Compiling Dubbing Pro and Backend Server to standalone package...
:: Using pyinstaller to compile app_gui.py with backend path and all necessary GUI dependencies
venv\Scripts\pyinstaller --paths=app --noconsole --name "DubbingPro" --collect-all mutagen --collect-all docx --collect-all requests --collect-all youtube_transcript_api --collect-all imageio_ffmpeg app_gui.py

echo.
echo =======================================================
echo BUILD COMPLETED SUCCESSFULLY!
echo Standalone files are located in: dist\DubbingPro
echo Launch the application via: dist\DubbingPro\DubbingPro.exe
echo =======================================================
pause
