@echo off
title NAV Tools - Khoi tao he thong
chcp 65001 > nul
cd /d "%~dp0"

:: 1. Kiem tra xem moi truong ao .venv da ton tai chua
if exist ".venv\Scripts\pythonw.exe" (
    echo Khởi chạy NAV Tools...
    start "" ".\.venv\Scripts\pythonw.exe" main.py > NAVTools.log 2>&1
    exit /b
)

:: 2. Neu chua co .venv, bat dau qua trinh tu dong thiet lap
echo ==============================================================
echo        ĐANG KHỞI TẠO MÔI TRƯỜNG TỰ ĐỘNG CHO NAV TOOLS
echo ==============================================================
echo.
echo Vui lòng đợi trong giây lát, quá trình này chỉ diễn ra ở lần chạy đầu tiên...
echo.

:: Kiem tra xem Python da duoc cai dat tren he thong chua
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [LỖI] Không tìm thấy Python trên máy tính của bạn!
    echo.
    echo Vui lòng tải và cài đặt Python 3.11 tại đường dẫn sau:
    echo https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo.
    echo QUAN TRỌNG: Hãy chắc chắn đã tích chọn "Add python.exe to PATH" khi cài đặt.
    echo.
    pause
    exit /b
)

:: 3. Tao moi truong ao .venv
echo [-] Đang tạo môi trường ảo Python (.venv)...
python -m venv .venv
if %errorlevel% neq 0 (
    echo [LỖI] Không thể tạo môi trường ảo. Vui lòng kiểm tra quyền thư mục hoặc phiên bản Python.
    pause
    exit /b
)

:: 4. Nang cap pip va cai dat cac thu vien tu requirements.txt
echo [-] Đang cài đặt các thư viện phụ thuộc (pip install)...
echo.
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [LỖI] Quá trình cài đặt thư viện gặp lỗi. Vui lòng kiểm tra kết nối mạng và thử lại.
    pause
    exit /b
)

:: 5. Cai dat playwright chromium
echo.
echo [-] Đang đăng ký trình điều khiển Playwright...
.\.venv\Scripts\playwright.exe install chromium

echo.
echo ==============================================================
echo        THIẾT LẬP THÀNH CÔNG! ĐANG KHỞI CHẠY ỨNG DỤNG...
echo ==============================================================
echo.

start "" ".\.venv\Scripts\pythonw.exe" main.py > NAVTools.log 2>&1
exit /b
