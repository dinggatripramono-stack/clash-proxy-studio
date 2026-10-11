@echo off
setlocal enabledelayedexpansion
title CLASH LIVE PROXY STUDIO - PC AUDITOR

cd /d "%~dp0"

echo ======================================================================
echo          CLASH LIVE PROXY STUDIO - PC AUDITOR ^& CONFIG MANAGER
echo ======================================================================
echo.

REM ---- 0. UNIVERSAL GIT RESOLVER ----
set "GIT_BIN="
if exist "%LOCALAPPDATA%\hermes\git\cmd\git.exe" set "GIT_BIN=%LOCALAPPDATA%\hermes\git\cmd\git.exe"
if not defined GIT_BIN if exist "%LOCALAPPDATA%\hermes\git\bin\git.exe" set "GIT_BIN=%LOCALAPPDATA%\hermes\git\bin\git.exe"
if not defined GIT_BIN if exist "C:\Program Files\Git\cmd\git.exe" set "GIT_BIN=C:\Program Files\Git\cmd\git.exe"
if not defined GIT_BIN (
    where git >nul 2>&1 && for /f "delims=" %%I in ('where git 2^>nul') do if not defined GIT_BIN set "GIT_BIN=%%I"
)

REM ---- 1. AUTO-SYNC FROM GITHUB ----
if exist ".git" (
    echo [*] Memeriksa sinkronisasi update dari GitHub...
    if defined GIT_BIN (
        "!GIT_BIN!" pull --rebase origin main 2>nul
        if !errorlevel! equ 0 (
            echo [OK] Versi aplikasi up-to-date dengan GitHub.
        ) else (
            echo [*] Mode offline atau remote tidak terjangkau. Melanjutkan versi lokal...
        )
    ) else (
        echo [*] Git tidak ditemukan. Menjalankan versi lokal...
    )
)
echo.

REM ---- 2. UNIVERSAL PYTHON RESOLVER ----
set "PY_BIN="
if exist "%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe" set "PY_BIN=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
if not defined PY_BIN if exist "%APPDATA%\uv\python\cpython-3.11-windows-x86_64-none\python.exe" set "PY_BIN=%APPDATA%\uv\python\cpython-3.11-windows-x86_64-none\python.exe"
if not defined PY_BIN if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_BIN=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY_BIN if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_BIN=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY_BIN if exist "C:\Program Files\Python311\python.exe" set "PY_BIN=C:\Program Files\Python311\python.exe"
if not defined PY_BIN if exist "C:\Python311\python.exe" set "PY_BIN=C:\Python311\python.exe"
if not defined PY_BIN (
    where python >nul 2>&1 && for /f "delims=" %%I in ('where python 2^>nul') do if not defined PY_BIN set "PY_BIN=%%I"
)
if not defined PY_BIN (
    where py >nul 2>&1 && for /f "delims=" %%I in ('where py 2^>nul') do if not defined PY_BIN set "PY_BIN=%%I"
)

if not defined PY_BIN (
    echo [ERROR] Python runtime tidak ditemukan di PC ini!
    echo Mohon pastikan Hermes Agent atau Python 3.10+ telah terpasang.
    pause
    exit /b 1
)

echo [OK] Menggunakan Python: "!PY_BIN!"

REM ---- 3. CHECK REQUIREMENTS ----
echo [*] Memeriksa dependensi Python...
"!PY_BIN!" -c "import fastapi, uvicorn, yaml, requests, multipart" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Menginstall paket pendukung yang belum ada...
    "!PY_BIN!" -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Gagal menginstall dependensi. Cek koneksi internet.
        pause
        exit /b 1
    )
)

REM ---- 4. CHECK MIHOMO CORE ----
echo [*] Memeriksa core engine Mihomo...
"!PY_BIN!" download_core.py
if %errorlevel% neq 0 (
    echo [ERROR] Gagal menyiapkan engine Mihomo core.
    pause
    exit /b 1
)

REM ---- 5. CLEANUP PREVIOUS SERVER INSTANCE ----
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":8999" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)

REM ---- 6. OPEN BROWSER ----
echo.
echo [*] Membuka dashboard di browser: http://127.0.0.1:8999...
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8999"

REM ---- 7. LAUNCH FASTAPI SERVER ----
echo [*] Menjalankan server aplikasi...
echo [*] Tekan Ctrl+C di jendela ini untuk mematikan aplikasi.
echo.
"!PY_BIN!" -m uvicorn app:app --host 127.0.0.1 --port 8999

if %errorlevel% neq 0 (
    echo.
    echo [!] Server berhenti dengan kode: %errorlevel%
    pause
)
