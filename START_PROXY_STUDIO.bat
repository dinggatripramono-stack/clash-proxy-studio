@echo off
setlocal enabledelayedexpansion
title CLASH LIVE PROXY STUDIO - PC AUDITOR

cd /d "%~dp0"

echo ======================================================================
echo          CLASH LIVE PROXY STUDIO - PC AUDITOR ^& CONFIG MANAGER
echo ======================================================================
echo.

:: 0. Auto-Sync Latest Updates from GitHub (Cross-PC Parity: Rumah ^<^=^> Kantor)
if exist ".git" (
    echo [*] Memeriksa update terbaru dari GitHub...
    git --version >nul 2>&1
    if !errorlevel! equ 0 (
        git fetch origin main >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "tokens=*" %%a in ('git rev-list HEAD..origin/main --count 2^>nul') do set "BEHIND=%%a"
            if defined BEHIND (
                if !BEHIND! gtr 0 (
                    echo [*] Ditemukan !BEHIND! pembaruan baru dari GitHub! Mengunduh update...
                    git pull --rebase origin main
                    echo [OK] Aplikasi berhasil disinkronkan ke versi terbaru!
                ) else (
                    echo [OK] Aplikasi sudah versi paling mutakhir (UP TO DATE).
                )
            )
        ) else (
            echo [!] Jaringan offline / remote tidak terjangkau. Melanjutkan versi lokal...
        )
    )
)
echo.

:: 1. Detect Python
set "PYTHON_EXE=python"
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=py"
    ) else (
        echo [ERROR] Python tidak ditemukan! Mohon install Python 3.10+ terlebih dahulu.
        pause
        exit /b 1
    )
)

:: 2. Check and Install Requirements
echo [*] Memeriksa dependensi Python...
!PYTHON_EXE! -c "import fastapi, uvicorn, yaml, requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Menginstall paket pendukung (fastapi, uvicorn, pyyaml, requests)...
    !PYTHON_EXE! -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Gagal menginstall dependensi. Cek koneksi internet.
        pause
        exit /b 1
    )
)

:: 3. Check Mihomo Core
echo [*] Memeriksa core engine Mihomo...
!PYTHON_EXE! download_core.py
if %errorlevel% neq 0 (
    echo [ERROR] Gagal menyiapkan engine Mihomo core.
    pause
    exit /b 1
)

:: 4. Start Browser in Background after short delay
echo.
echo [*] Membuka dashboard di browser (http://127.0.0.1:8999)...
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8999"

:: 5. Launch FastAPI Server
echo [*] Menjalankan server aplikasi...
echo [*] Tekan Ctrl+C di jendela ini untuk mematikan aplikasi.
echo.
!PYTHON_EXE! -m uvicorn app:app --host 127.0.0.1 --port 8999
