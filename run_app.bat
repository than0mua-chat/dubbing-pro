@echo off
title Khởi chạy Antigravity Auto TTS & Subtitles
echo Đang kiểm tra môi trường và khởi chạy ứng dụng...

:: Đặt PYTHONPATH cho thư mục app
set PYTHONPATH=app
set PYTHONIOENCODING=utf-8

:: Chạy ứng dụng giao diện
start "" "venv\Scripts\pythonw.exe" app_gui.py

echo Ứng dụng đã được khởi động! Bạn có thể đóng cửa sổ terminal này.
timeout /t 3 >nul
exit
