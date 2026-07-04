"""NAV TOOLS — Desktop AI Video/Image Generator.

Entry point for the application.
"""

from __future__ import annotations

import faulthandler
import io
import os
import sys

import subprocess

if os.name == "nt":
    _orig_Popen = subprocess.Popen
    _orig_run = subprocess.run

    class _patched_Popen_class(_orig_Popen):
        def __init__(self, *args, **kwargs):
            if "creationflags" not in kwargs:
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 134217728)
            super().__init__(*args, **kwargs)

    def _patched_run(*args, **kwargs):
        if "creationflags" not in kwargs:
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 134217728)
        return _orig_run(*args, **kwargs)

    subprocess.Popen = _patched_Popen_class
    subprocess.run = _patched_run

_log_dir = os.path.join(os.path.expanduser("~"), ".vidgen", "logs")
try:
    os.makedirs(_log_dir, exist_ok=True)
    _log_file = open(os.path.join(_log_dir, "app_output.log"), "a", encoding="utf-8", buffering=1)
except Exception:
    _log_file = open(os.devnull, "w", encoding="utf-8")

if sys.stdout is None or getattr(sys.stdout, "write", None) is None:
    sys.stdout = _log_file
if sys.stderr is None or getattr(sys.stderr, "write", None) is None:
    sys.stderr = _log_file

_IS_FROZEN = getattr(sys, "frozen", False)

if sys.platform == "win32":
    import ctypes

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("navtools.vidgen.1.0")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if _IS_FROZEN:
    _smoke_dir = os.path.join(os.path.expanduser("~"), ".vidgen", "logs")
    os.makedirs(_smoke_dir, exist_ok=True)
    with open(os.path.join(_smoke_dir, "dll_load.log"), "w", encoding="utf-8") as _log_f:
        _log_f.write("=== DLL Load Registration ===\n")
        _log_f.write(f"sys.executable: {sys.executable}\n")
        _log_f.write(f"sys.path: {sys.path}\n")
        # Add torch/lib to DLL search path on Windows for PyTorch C-extensions
        _torch_lib = os.path.join(getattr(sys, "_MEIPASS", ""), "torch", "lib")
        _log_f.write(f"Checking torch_lib path: {_torch_lib}\n")
        if os.path.isdir(_torch_lib):
            try:
                os.add_dll_directory(_torch_lib)
                _log_f.write(f"Successfully registered dll directory: {_torch_lib}\n")
            except Exception as e:
                _log_f.write(f"Failed to register dll directory: {e}\n")
        else:
            _log_f.write("torch_lib path does not exist!\n")

try:
    _exe_dir = os.path.dirname(sys.executable) if _IS_FROZEN else os.path.dirname(os.path.abspath(__file__))
    _bundled_u2net = os.path.join(_exe_dir, ".u2net")
    if os.path.isdir(_bundled_u2net) and "U2NET_HOME" not in os.environ:
        os.environ["U2NET_HOME"] = _bundled_u2net

    _bundled_cache = os.path.join(_exe_dir, ".cache")
    if os.path.isdir(os.path.join(_bundled_cache, "whisper")) and "XDG_CACHE_HOME" not in os.environ:
        os.environ["XDG_CACHE_HOME"] = _bundled_cache
except Exception:
    pass

try:
    if _IS_FROZEN:
        from pathlib import Path as _Path

        _crash_dir = _Path.home() / ".vidgen" / "logs"
        _crash_dir.mkdir(parents=True, exist_ok=True)
        _crash_fp = open(_crash_dir / "crash.log", "a", buffering=1)
        faulthandler.enable(file=_crash_fp)
    else:
        faulthandler.enable()
except Exception:
    pass


def _start_hang_watchdog():
    """Pure-Python watchdog: main thread updates a timestamp via event filter;
    a daemon thread checks it and dumps stacks if blocked for > 15s.

    An event filter on QApplication bumps the timestamp on EVERY Qt event
    processed. True idle states still produce events (cursor blink, focus,
    timers, etc.), so a stale heartbeat > 15s means Qt event loop is ACTUALLY
    blocked — a real hang. No idle-frame check needed (it was too lenient: a
    hang in Qt C++ code looks identical to idle from Python's perspective).

    Safe alternative to faulthandler.dump_traceback_later (which crashes on
    Windows/PySide6 when a thread is mid-C-call in importlib).
    """
    import sys as _sys
    import threading
    import time
    import traceback

    main_thread_heartbeat = {"t": time.time()}
    last_dump_at = {"t": 0}

    def _watchdog_loop():
        while True:
            time.sleep(5)
            age = time.time() - main_thread_heartbeat["t"]
            if age < 15:
                continue

            now = time.time()
            if now - last_dump_at["t"] < 30:
                continue
            last_dump_at["t"] = now

            frames = _sys._current_frames()
            print(f"[WATCHDOG] Main thread silent for {age:.1f}s — dumping stacks:", file=_sys.stderr, flush=True)
            for tid, frame in frames.items():
                print(f"\n--- Thread {tid} ---", file=_sys.stderr, flush=True)
                traceback.print_stack(frame, file=_sys.stderr)
            _sys.stderr.flush()

    t = threading.Thread(target=_watchdog_loop, daemon=True, name="hang-watchdog")
    t.start()
    return main_thread_heartbeat


_watchdog_heartbeat = _start_hang_watchdog()

from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from config.constants import (
    APP_NAME,
    APP_VERSION,
    BASE_DIR,
    DATA_DIR,
    DEFAULT_IMAGE_OUTPUT,
    DEFAULT_VIDEO_OUTPUT,
    FONT_BODY,
    LOG_DIR,
)
from config.settings import Settings
from models.database import Database
from utils.cleanup_orphans import cleanup_orphan_resources
from utils.logger import cleanup_old_logs, log


def main():
    """Application entry point."""
    if "--smoke-test" in sys.argv:
        import os as _os
        from pathlib import Path as _SPath

        _smoke_dir = _SPath.home() / ".vidgen" / "logs"
        _smoke_dir.mkdir(parents=True, exist_ok=True)
        _smoke_log = _smoke_dir / "smoke_test.log"
        _smoke_fh = open(_smoke_log, "w", encoding="utf-8")

        class _Tee:
            def __init__(self, *streams):
                self.streams = [s for s in streams if s is not None]

            def write(self, data):
                for s in self.streams:
                    try:
                        s.write(data)
                        s.flush()
                    except Exception:
                        pass
                return len(data)

            def flush(self):
                for s in self.streams:
                    try:
                        s.flush()
                    except Exception:
                        pass

        _original_stdout = sys.stdout if sys.stdout and hasattr(sys.stdout, "write") else None
        sys.stdout = _Tee(_original_stdout, _smoke_fh)
        sys.stderr = sys.stdout
        try:
            from scripts.bundle_smoke_test import run as _smoke_run
        except Exception as e:
            print(f"[smoke-test] failed to import test module: {type(e).__name__}: {e}")
            import traceback as _tb

            _tb.print_exc()
            _smoke_fh.close()
            sys.exit(1)

        exit_code = _smoke_run()
        print(f"\n[smoke-test] log saved to: {_smoke_log}")
        _smoke_fh.close()
        sys.exit(exit_code)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_IMAGE_OUTPUT.mkdir(parents=True, exist_ok=True)
    DEFAULT_VIDEO_OUTPUT.mkdir(parents=True, exist_ok=True)



    from utils.platform import get_playwright_browsers_path

    pw_path = get_playwright_browsers_path()
    log.info(f"{APP_NAME} v{APP_VERSION} starting...")
    if pw_path:
        log.info(f"Playwright browsers: {pw_path}")

    db = Database()
    db.connect()
    log.info("Database initialized")

    settings = Settings(db.conn)
    log.info(f"Theme: {settings.theme}")

    cleanup_old_logs(settings.get("log_retention_days", 30))
    cleanup_orphan_resources()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    from PySide6.QtCore import QObject, QTimer
    import time as _time

    class _HeartbeatFilter(QObject):
        def eventFilter(self, obj, event):
            _watchdog_heartbeat["t"] = _time.time()
            return False

    _hb_filter = _HeartbeatFilter()
    app.installEventFilter(_hb_filter)
    app._hb_filter = _hb_filter

    _hb_timer = QTimer()
    _hb_timer.timeout.connect(lambda: _watchdog_heartbeat.__setitem__("t", _time.time()))
    _hb_timer.start(1000)
    app._hb_timer = _hb_timer
    _watchdog_heartbeat["t"] = _time.time()

    for font_name in ("Inter", "Manrope", "JetBrains Mono"):
        QFontDatabase.addApplicationFont(f":/fonts/{font_name}")
    app.setFont(QFont(FONT_BODY, 13))
    
    # Force dark palette at the OS level to prevent white flashes during window/dialog exposure/creation
    from PySide6.QtGui import QPalette, QColor
    from PySide6.QtCore import Qt
    dark_palette = QPalette()
    dark_color = QColor(15, 23, 42) # Slate 900
    dark_palette.setColor(QPalette.ColorRole.Window, dark_color)
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(248, 250, 252))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(7, 11, 18)) # Slate 950
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(15, 23, 42))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(248, 250, 252))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(248, 250, 252))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(30, 41, 59)) # Slate 800
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(248, 250, 252))
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(37, 99, 235))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(37, 99, 235))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(dark_palette)

    app.setStyleSheet("QToolTip { color: #f8fafc; background-color: #0f172a; border: 1px solid #334155; padding: 4px; font-size: 12px; }")

    from config.constants import ASSETS_DIR

    # Try multiple icon locations (frozen bundle vs dev)
    for _icon_candidate in (
        ASSETS_DIR / "assets" / "navtools.ico",
        ASSETS_DIR / "navtools.ico",
        BASE_DIR / "assets" / "navtools.ico",
    ):
        if _icon_candidate.exists():
            app.setWindowIcon(QIcon(str(_icon_candidate)))
            log.info(f"App icon set: {_icon_candidate}")
            break

    from config.constants import API_BASE_URL, CLIENT_API_KEY

    sheets_auth = None
    try:
        from services.api_auth import ApiAuthService

        sheets_auth = ApiAuthService(API_BASE_URL, CLIENT_API_KEY)
        log.info(f"API auth service initialized (base_url={API_BASE_URL})")
    except Exception as e:
        log.error(f"API auth init failed: {e}")

    current_user = db.get_setting("current_user") or "user"
    log.info(f"Logged in as: {current_user} (Login bypassed)")

    splash = None
    try:
        from ui.widgets.loading_splash import LoadingSplash

        splash = LoadingSplash(title=f"{APP_NAME} v{APP_VERSION}")
        splash.set_progress(10, "Khởi tạo giao diện...")
        splash.show()
    except Exception as e:
        log.warning(f"Splash not shown: {e}")

    from ui.main_window import MainWindow

    try:
        from automation.browser_manager import BrowserManager
        from workers.task_manager import TaskManager
        
        browser_manager = BrowserManager()
        task_manager = TaskManager(db, browser_manager)
        
        if splash:
            splash.set_progress(40, "Tải các trang chính...")

        window = MainWindow(db=db, settings=settings, browser_manager=browser_manager)
        window.task_manager = task_manager
        
        window.setWindowTitle(APP_NAME)

        if splash:
            splash.set_progress(90, "Hoàn tất...")

        window.show()

        if splash:
            splash.set_progress(100, "Sẵn sàng!")
            from PySide6.QtCore import QTimer
            from PySide6.QtWidgets import QApplication as _Q

            _Q.processEvents()
            _splash_ref = splash
            QTimer.singleShot(0, _splash_ref.close)
            QTimer.singleShot(50, _splash_ref.deleteLater)
            _Q.processEvents()
            splash = None
    except Exception as e:
        log.error(f"Failed to create MainWindow: {e}")
        import traceback

        traceback.print_exc()
        db.close()
        sys.exit(1)

    log.info("Application started")

    # Start background warmup (pre-imports and playwright AV scans) after main window is shown
    try:
        from services.eager_warmup import start_warmup
        start_warmup()
    except Exception as e:
        log.warning(f"Eager warmup skipped: {e}")



    _watchdog_heartbeat["t"] = _time.time()
    exit_code = app.exec()
    
    # Cleanup background managers
    try:
        import asyncio
        if 'browser_manager' in locals():
            asyncio.run(browser_manager.stop())
    except Exception as e:
        log.warning(f"Error stopping browser_manager: {e}")
        
    db.close()
    log.info("Application closed")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
