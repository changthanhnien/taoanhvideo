@echo off
title NAV Tools - Khoi tao he thong
cd /d "%~dp0"

:: 1. Kiem tra xem moi truong ao .venv da ton tai chua
if exist ".venv\Scripts\pythonw.exe" (
    echo Khoi chay NAV Tools...
    start "" ".\.venv\Scripts\pythonw.exe" main.py > NAVTools.log 2>&1
    exit /b
)

:: 2. Bat dau qua trinh tu dong thiet lap tai moi truong
echo ==============================================================
echo        DANG TAI VA KHOI TAO MOI TRUONG TU DONG CHO NAV TOOLS
echo ==============================================================
echo.
echo Vui long doi trong giay lat, dang tu dong thiet lap (chi chay o lan dau tien)...
echo.

:: Kiem tra xem Python da duoc cai dat tren he thong chua
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Khong tim thay Python tren may tinh cua ban!
    echo.
    echo Vui long tai va cai dat Python 3.11 tai duong dan sau:
    echo https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo.
    echo LUU Y QUAN TRONG: Nho tich chon "Add python.exe to PATH" khi cai dat.
    echo.
    pause
    exit /b
)

:: 3. Tao moi truong ao .venv
echo [-] Dang tao moi truong ao Python (.venv)...
python -m venv .venv
if %errorlevel% neq 0 (
    echo [LOI] Khong the tao moi truong ao. Vui long kiem tra quyen thu muc hoac phien ban Python.
    pause
    exit /b
)

:: 4. Nang cap pip va cai dat cac thu vien tu requirements.txt
echo [-] Dang cai dat cac thu vien phu thuoc (pip install)...
echo.
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [LOI] Qua trinh cai dat thu vien gap loi. Vui long kiem tra ket noi mang va thu lai.
    pause
    exit /b
)

:: 5. Cai dat playwright chromium
echo.
echo [-] Dang dang ky trinh dieu khien Playwright...
.\.venv\Scripts\playwright.exe install chromium

echo.
echo ==============================================================
echo        THIET LAP THANH CONG! DANG KHOI CHAY UNG DUNG...
echo ==============================================================
echo.

start "" ".\.venv\Scripts\pythonw.exe" main.py > NAVTools.log 2>&1
exit /b
