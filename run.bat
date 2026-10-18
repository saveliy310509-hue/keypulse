@echo off
chcp 65001 >nul
title KeyPulse Bot
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Создаю виртуальное окружение...
    python -m venv .venv
    echo [2/3] Ставлю зависимости...
    .venv\Scripts\python.exe -m pip install --upgrade pip >nul
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)

echo [3/3] Запускаю бота...
.venv\Scripts\python.exe main.py
pause
