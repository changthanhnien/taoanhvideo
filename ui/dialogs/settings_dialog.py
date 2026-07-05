"""NAV TOOLS - Settings dialog with Google account management."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QMetaObject, QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QTextEdit,
    QHBoxLayout,
)

from config.constants import APP_NAME, ASSETS_DIR, BASE_DIR, BROWSER_PROFILE_DIR
from config.settings import Settings
from models.account import Account
from models.database import Database
from utils.logger import log
from utils.platform import find_chrome


# Stealth JS script to bypass Cloudflare Turnstile detection
_STEALTH_JS = """
// === 1. navigator.webdriver ===
Object.defineProperty(navigator, 'webdriver', {
    get: () => false,
    configurable: true
});
try {
    const proto = Object.getPrototypeOf(navigator);
    if (proto) {
        delete proto.webdriver;
        Object.defineProperty(proto, 'webdriver', {
            get: () => false,
            configurable: true
        });
    }
} catch(e) {}

// === 2. Clean CDP / Playwright artifacts ===
(function() {
    const cleanObj = (obj) => {
        try {
            const keys = Object.getOwnPropertyNames(obj);
            for (const key of keys) {
                if (/^cdc_|^\\$cdc_|__playwright|__driver_|__selenium|__webdriver/.test(key)) {
                    delete obj[key];
                }
            }
        } catch(e) {}
    };
    cleanObj(document);
    cleanObj(window);
    const observer = new MutationObserver(() => {
        cleanObj(document);
        cleanObj(window);
    });
    observer.observe(document.documentElement || document, {
        childList: true, subtree: true
    });
})();

// === 3. Permissions API ===
if (navigator.permissions) {
    const originalQuery = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = (params) => {
        if (params.name === 'notifications') {
            return Promise.resolve({ state: Notification.permission });
        }
        return originalQuery(params);
    };
}

// === 4. window.chrome ===
if (!window.chrome || !window.chrome.runtime) {
    window.chrome = window.chrome || {};
    window.chrome.runtime = window.chrome.runtime || {
        connect: function() {},
        sendMessage: function() {},
        onMessage: { addListener: function() {} },
        onConnect: { addListener: function() {} },
        id: undefined
    };
}

// === 5. Fix iframe contentWindow ===
try {
    const iframeProto = HTMLIFrameElement.prototype;
    const origCW = Object.getOwnPropertyDescriptor(iframeProto, 'contentWindow');
    if (origCW) {
        Object.defineProperty(iframeProto, 'contentWindow', {
            get: function() {
                const win = origCW.get.call(this);
                if (win) {
                    try {
                        Object.defineProperty(win, 'chrome', {
                            value: window.chrome,
                            writable: true,
                            configurable: true
                        });
                        Object.defineProperty(win.navigator, 'webdriver', {
                            get: () => false,
                            configurable: true
                        });
                    } catch(e) {}
                }
                return win;
            }
        });
    }
} catch(e) {}

// === 6. navigator.plugins ===
try {
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const arr = [
                { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer',
                  description: 'Portable Document Format',
                  length: 1, item: () => null, namedItem: () => null,
                  0: { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: null }},
                { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer',
                  description: 'Portable Document Format',
                  length: 1, item: () => null, namedItem: () => null,
                  0: { type: 'application/pdf', suffixes: 'pdf', description: '', enabledPlugin: null }},
            ];
            arr.item = (i) => arr[i] || null;
            arr.namedItem = (n) => arr.find(p => p.name === n) || null;
            arr.refresh = () => {};
            return arr;
        },
        configurable: true
    });
} catch(e) {}

// === 7. navigator.languages ===
try {
    Object.defineProperty(navigator, 'languages', {
        get: () => ['vi-VN', 'vi', 'en-US', 'en'],
        configurable: true
    });
} catch(e) {}

// === 8. Mask Error.stack sourceURL ===
try {
    const origPrepare = Error.prepareStackTrace;
    Error.prepareStackTrace = function(err, stack) {
        const filtered = stack.filter(frame => {
            const fn = frame.getFileName() || '';
            return !fn.includes('playwright') && !fn.includes('pptr:') && !fn.includes('__puppeteer');
        });
        if (origPrepare) return origPrepare(err, filtered);
        return err.toString() + '\\n' + filtered.map(f => '    at ' + f.toString()).join('\\n');
    };
} catch(e) {}

// === 9. Prevent detection via toString() ===
const origToString = Function.prototype.toString;
const nativeToString = function() {
    if (this === navigator.permissions.query) return 'function query() { [native code] }';
    return origToString.call(this);
};
Function.prototype.toString = nativeToString;
try {
    Object.defineProperty(Function.prototype, 'toString', {
        value: nativeToString, writable: false, configurable: false
    });
} catch(e) {}
"""

async def apply_stealth_to_context(context):
    await context.add_init_script(_STEALTH_JS)
    async def _handle_route(route):
        url = route.request.url
        if any(h in url for h in ["127.0.0.1", "localhost", "::1"]):
            await route.abort()
        else:
            await route.continue_()
    await context.route("**/*", _handle_route)

STEALTH_CHROME_ARGS = [
    "--window-size=1024,768",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-default-apps",
    "--disable-infobars",
    "--disable-extensions",
    "--disable-features=TranslateUI,GlobalMediaControls",
    "--disable-dev-shm-usage",
    "--disable-component-update",
    "--disable-hang-monitor",
    "--disable-prompt-on-repost",
    "--disable-background-networking",
    "--disable-sync",
    "--metrics-recording-only",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-field-trial-config",
    "--password-store=basic",
    "--use-mock-keychain",
]


def find_email_in_obj(obj):
    import re
    email_regex = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    blacklisted = {"support@grok.com", "info@grok.com", "billing@grok.com", "privacy@grok.com"}
    if isinstance(obj, str):
        match = email_regex.search(obj)
        if match:
            email = match.group(0)
            if email.lower() not in blacklisted:
                return email
    elif isinstance(obj, dict):
        for k, v in obj.items():
            res = find_email_in_obj(v)
            if res:
                return res
            res = find_email_in_obj(k)
            if res:
                return res
    elif isinstance(obj, list):
        for item in obj:
            res = find_email_in_obj(item)
            if res:
                return res
    return None


async def detect_email_from_page(page):
    js_detect = """
    () => {
        const regex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/;
        const blacklisted = ["support@grok.com", "info@grok.com", "billing@grok.com", "privacy@grok.com"];
        
        const check = (val) => {
            if (val && regex.test(val)) {
                const email = val.match(regex)[0];
                if (!blacklisted.includes(email.toLowerCase())) {
                    return email;
                }
            }
            return null;
        };

        // Check localStorage
        try {
            for (let i = 0; i < localStorage.length; i++) {
                const val = localStorage.getItem(localStorage.key(i));
                const res = check(val);
                if (res) return res;
            }
        } catch(e){}
        // Check sessionStorage
        try {
            for (let i = 0; i < sessionStorage.length; i++) {
                const val = sessionStorage.getItem(sessionStorage.key(i));
                const res = check(val);
                if (res) return res;
            }
        } catch(e){}
        // Check document.cookie
        try {
            const res = check(document.cookie);
            if (res) return res;
        } catch(e){}
        // Check window globals
        try {
            if (window.__NEXT_DATA__) {
                const s = JSON.stringify(window.__NEXT_DATA__);
                const res = check(s);
                if (res) return res;
            }
        } catch(e){}
        return null;
    }
    """
    try:
        email = await page.evaluate(js_detect)
        if email:
            return email
    except:
        pass
    return None


async def detect_grok_tier_from_page(page):
    js_tier = """
    () => {
        try {
            // Priority 1: Check __NEXT_DATA__ state
            if (window.__NEXT_DATA__) {
                const s = JSON.stringify(window.__NEXT_DATA__);
                if (/SUPER_GROK|SuperGrok/i.test(s)) return "Super Grok";
                if (/HEAVY_GROK|HeavyGrok/i.test(s)) return "Heavy Grok";
            }
            
            // Priority 2: Check global window variables or redux state if any
            if (window.__NEXT_REDUX_WRAPPER_STORE__) {
                const state = JSON.stringify(window.__NEXT_REDUX_WRAPPER_STORE__.getState());
                if (/SUPER_GROK|SuperGrok/i.test(state)) return "Super Grok";
                if (/HEAVY_GROK|HeavyGrok/i.test(state)) return "Heavy Grok";
            }

            const text = document.body.innerText || "";
            const html = document.body.innerHTML || "";

            // Priority 3: Scan visible text elements specifically for user tier or supergrok title
            const headings = Array.from(document.querySelectorAll('h1, h2, h3, div, span, p, a, button'));
            
            let foundSuper = false;
            let foundHeavy = false;
            let hasUpgradeSuper = false;
            let hasUpgradeHeavy = false;

            for (const el of headings) {
                const txt = el.textContent || "";
                const elHtml = el.innerHTML || "";
                
                // If it's a button or link to upgrade
                if (/upgrade to|nâng cấp lên/i.test(txt)) {
                    if (/super\s*grok/i.test(txt)) hasUpgradeSuper = true;
                    if (/heavy\s*grok/i.test(txt)) hasUpgradeHeavy = true;
                } else {
                    if (/super\s*grok/i.test(txt) || /supergrok/i.test(txt) || /supergrok/i.test(elHtml)) {
                        foundSuper = true;
                    }
                    if (/heavy\s*grok/i.test(txt) || /heavygrok/i.test(txt) || /heavygrok/i.test(elHtml)) {
                        foundHeavy = true;
                    }
                }
            }

            if (foundSuper && !hasUpgradeSuper) return "Super Grok";
            if (foundHeavy && !hasUpgradeHeavy) return "Heavy Grok";

            // Fallback check of raw text
            if (/supergrok/i.test(text) && !/upgrade to\s*supergrok|nâng cấp lên\s*supergrok/i.test(text)) {
                return "Super Grok";
            }
            if (/heavygrok/i.test(text) && !/upgrade to\s*heavygrok|nâng cấp lên\s*heavygrok/i.test(text)) {
                return "Heavy Grok";
            }
        } catch(e) {
            // ignore
        }
        return "Grok";
    }
    """
    try:
        tier = await page.evaluate(js_tier)
        if tier:
            return tier
    except Exception as e:
        log.warning(f"Error evaluating grok tier: {e}")
    return "Grok"


def _read_chrome_cookies(profile_dir: Path):
    """Read email and cookie expiry from a Chrome profile."""
    info = {"email": None, "cookie_exp": None}
    profile_dir = Path(profile_dir)
    for prefs_name in ("Default/Preferences", "Default/Secure Preferences"):
        prefs_file = profile_dir / prefs_name
        if not prefs_file.exists() or info["email"]:
            continue
        try:
            with prefs_file.open("r", encoding="utf-8") as f:
                prefs = json.load(f)
            account_info = prefs.get("account_info") or []
            if account_info:
                info["email"] = account_info[0].get("email")
            signin = prefs.get("signin") or {}
            info["email"] = info["email"] or signin.get("allowed_username") or signin.get("username")
        except Exception as e:
            log.warning(f"Could not read {prefs_file}: {e}")

    cookies_db = profile_dir / "Default" / "Network" / "Cookies"
    tmp_db = profile_dir / "cookies_copy.db"
    if cookies_db.exists():
        try:
            shutil.copy2(cookies_db, tmp_db)
            conn = sqlite3.connect(str(tmp_db))
            row = conn.execute("SELECT MAX(expires_utc) FROM cookies WHERE host_key LIKE '%google.com%'").fetchone()
            conn.close()
            if row and row[0]:
                chrome_epoch = datetime(1601, 1, 1)
                info["cookie_exp"] = chrome_epoch + timedelta(microseconds=int(row[0]))
        except Exception as e:
            log.warning(f"Could not read Cookies DB: {e}")
        finally:
            try:
                os.remove(tmp_db)
            except Exception:
                pass
    return info


class _LoginSignals(QObject):
    success = Signal(str, str, object, object, object)
    status = Signal(str)
    failed = Signal(str)
    finished = Signal()


class _RenewSignals(QObject):
    success = Signal(int, object, object, object)
    failed = Signal(int, str)
    finished = Signal()


class PremiumCheckBox(QCheckBox):
    def __init__(self, text="", parent=None):
        if isinstance(text, QWidget):
            parent = text
            text = ""
        super().__init__(text, parent)
        self.setStyleSheet("background: transparent;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor, QPen, QBrush
        from PySide6.QtCore import QRect, Qt
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        size = 18
        
        if self.text():
            x = 4
        else:
            x = (w - size) // 2
        y = (h - size) // 2
        
        rect = QRect(x, y, size, size)
        
        if self.isChecked():
            painter.setBrush(QBrush(QColor("#2563eb")))
            painter.setPen(QPen(QColor("#2563eb"), 1))
            painter.drawRoundedRect(rect, 4, 4)
            
            pen = QPen(QColor("white"), 2.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            
            painter.drawLine(x + 5, y + 9, x + 8, y + 12)
            painter.drawLine(x + 8, y + 12, x + 13, y + 5)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#64748b"), 2))
            painter.drawRoundedRect(rect, 4, 4)
            
        if self.text():
            painter.setPen(QColor("#f3f4f6"))
            painter.setFont(self.font())
            text_rect = QRect(x + 26, 0, w - (x + 26), h)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
            
        painter.end()


class SettingsDialog(QDialog):
    """Settings and account management dialog."""

    # Custom signals for thread-safe UI updates
    login_status_changed = Signal(str, bool)  # text, is_running
    grok_login_status_changed = Signal(str, bool)  # text, is_running

    def __init__(self, db: Database, settings: Settings | None = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.settings = settings or Settings(db)
        self.accounts: list[Account] = []
        self._login_thread = None
        self._renew_thread = None
        self.google_proc = None
        self.grok_proc = None
        self.edit_procs = {}
        self._manual_sync_accounts = set()
        
        # Connect signals for thread-safe button updates
        self.login_status_changed.connect(self._update_google_btn)
        self.grok_login_status_changed.connect(self._update_grok_btn)
        self.setWindowTitle(f"{APP_NAME} — Cài đặt hệ thống")
        self.setMinimumSize(950, 550)
        self.setModal(True)
        self._init_ui()
        self._load_accounts()
        self._load_grok_accounts()
        self._apply_theme()

    def _apply_theme(self):
        theme = str(self.settings.get("theme", "dark"))
        if theme == "dark":
            self.setStyleSheet("""
                QDialog { background: #0b0f19; color: #f3f4f6; font-family: 'Segoe UI', Arial, sans-serif; }
                QLabel { color: #9ca3af; font-size: 13px; }
                QLineEdit, QComboBox { background: #111827; color: #f3f4f6; border: 1px solid #374151; padding: 6px 12px; border-radius: 6px; font-size: 13px; }
                QLineEdit:focus, QComboBox:focus { border-color: #3b82f6; }
                QTabWidget::pane { border: 1px solid #1f2937; background: #0b0f19; border-radius: 8px; top: -1px; }
                QTabBar::tab { background: #111827; color: #9ca3af; padding: 10px 20px; border: 1px solid #1f2937; border-bottom: none; border-top-left-radius: 8px; border-top-right-radius: 8px; font-weight: 600; font-size: 13px; margin-right: 4px; }
                QTabBar::tab:hover { background: #1f2937; color: #ffffff; }
                QTabBar::tab:selected { background: #2563eb; color: #ffffff; border: 1px solid #2563eb; border-bottom: none; }
                QTableWidget { background: #0b0f19; color: #f3f4f6; border: 1px solid #1f2937; gridline-color: #1f2937; border-radius: 8px; font-size: 13px; outline: none; }
                QTableWidget::item { padding: 8px 12px; border-bottom: 1px solid #1f2937; outline: none; }
                QTableWidget::item:focus { border: none; outline: none; }
                QTableWidget::item:selected { background: transparent; border: none; outline: none; }
                QHeaderView::section { background: #111827; color: #9ca3af; border: none; border-bottom: 1px solid #1f2937; padding: 8px; font-weight: 600; font-size: 11px; text-transform: uppercase; }
                QPushButton { background: #111827; color: #f3f4f6; border: 1px solid #374151; padding: 8px 16px; border-radius: 6px; font-weight: 600; font-size: 13px; }
                QPushButton:hover { background: #1f2937; border-color: #4b5563; }
                QPushButton:pressed { background: #111827; }
                QPushButton#save_btn { background: #2563eb; color: white; border: 1px solid #2563eb; }
                QPushButton#save_btn:hover { background: #1d4ed8; }
                QPushButton#add_btn, QPushButton#grok_add_btn { background: #2563eb; color: white; border: 1px solid #2563eb; }
                QPushButton#add_btn:hover, QPushButton#grok_add_btn:hover { background: #1d4ed8; }
                QCheckBox { color: #f3f4f6; font-size: 13px; }
                QCheckBox::indicator { width: 18px; height: 18px; border: 2px solid #64748b; border-radius: 4px; background-color: #111827; }
                QCheckBox::indicator:hover { border-color: #3b82f6; }
                QCheckBox::indicator:checked { background-color: #3b82f6; border-color: #3b82f6; image: url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27white%27%20stroke-width%3D%274%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Cpolyline%20points%3D%2720%206%209%2017%204%2012%27%3E%3C%2Fpolyline%3E%3C%2Fsvg%3E"); }
            """)
        else:
            self.setStyleSheet("")

    @Slot(str, bool)
    def _update_google_btn(self, text, is_running):
        if hasattr(self, 'add_google_btn') and self.add_google_btn:
            self.add_google_btn.setText(text)
            self.add_google_btn.setEnabled(not is_running)
            if not is_running:
                self.add_google_btn.setStyleSheet("")

    @Slot(str, bool)
    def _update_grok_btn(self, text, is_running):
        if hasattr(self, 'add_grok_btn') and self.add_grok_btn:
            self.add_grok_btn.setText(text)
            self.add_grok_btn.setEnabled(not is_running)
            if not is_running:
                self.add_grok_btn.setStyleSheet("")

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        
        self._build_accounts_tab(self.tabs)
        self._build_grok_accounts_tab(self.tabs)
        
        actions = QHBoxLayout()
        actions.addStretch()
        
        save_btn = QPushButton("Lưu")
        save_btn.setObjectName("save_btn")
        save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn.clicked.connect(self._save_settings)
        
        close_btn = QPushButton("Đóng")
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.accept)
        
        actions.addWidget(save_btn)
        actions.addWidget(close_btn)
        root.addLayout(actions)

    def _build_accounts_tab(self, tabs):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        top = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Tìm email tài khoản...")
        self.search_edit.textChanged.connect(self._filter_accounts)
        
        self.add_google_btn = QPushButton("Thêm tài khoản Google")
        self.add_google_btn.setObjectName("add_btn")
        self.add_google_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_google_btn.clicked.connect(self._add_account)
        
        top.addWidget(self.search_edit)
        top.addWidget(self.add_google_btn)
        layout.addLayout(top)

        # Removed Cookie Exp column -> 4 columns total
        self.accounts_table = QTableWidget(0, 4)
        self.accounts_table.setHorizontalHeaderLabels(["Email", "Tài khoản", "Bật", "Thao tác"])
        self.accounts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.accounts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.accounts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.accounts_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        
        self.accounts_table.setColumnWidth(1, 200)
        self.accounts_table.setColumnWidth(2, 60)
        self.accounts_table.setColumnWidth(3, 140)
        
        self.accounts_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.accounts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.accounts_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.accounts_table.verticalHeader().setDefaultSectionSize(38)
        self.accounts_table.verticalHeader().setVisible(False)
        self.accounts_table.setStyleSheet("QTableWidget::item:selected { background-color: transparent; }")
        layout.addWidget(self.accounts_table)
        tabs.addTab(tab, "🌐 Tài khoản Google")

    def _build_general_tab(self, tabs):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        self.gemini_key_edit = QLineEdit(str(self.settings.get("gemini_api_key", "") or ""))
        self.gemini_key_edit.setPlaceholderText("Nhập Gemini API Key...")
        self.gemini_key_edit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        
        self.auto_retry = PremiumCheckBox("Tự retry tác vụ lỗi")
        self.auto_retry.setChecked(bool(self.settings.get("auto_retry_on_error", True)))
        
        guide_btn = QPushButton("Hướng dẫn lấy Gemini API key")
        guide_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        guide_btn.clicked.connect(self._show_gemini_key_guide)
        
        lbl = QLabel("Gemini API key (Dùng cho tính năng dịch hình ảnh Ảnh → Prompt)")
        lbl.setStyleSheet("font-weight: bold; color: #dae2fd;")
        
        layout.addWidget(lbl)
        layout.addWidget(self.gemini_key_edit)
        layout.addWidget(self.auto_retry)
        layout.addWidget(guide_btn)
        layout.addStretch()
        tabs.addTab(tab, "🔑 Cấu hình API Key")

    def _toggle_inline_gemini_guide(self):
        self._show_gemini_key_guide()

    def _load_gemini_screenshot(self, label, filename, width):
        path = Path(ASSETS_DIR) / filename
        if path.exists():
            pix = QPixmap(str(path))
            if not pix.isNull():
                label.setPixmap(pix.scaledToWidth(width, Qt.SmoothTransformation))
                return True
        return False

    def _show_gemini_key_guide(self):
        QMessageBox.information(
            self,
            "Gemini API key",
            "Mở Google AI Studio, tạo API key rồi dán vào ô Gemini API key.",
        )

    def _try_fetch_gemini_key(self, account_id=None):
        return None

    def _start_clipboard_watch_for_gemini_key(self):
        return None

    def _get_or_fetch_qr(self):
        qr = Path(ASSETS_DIR) / "donate_qr.png"
        return qr if qr.exists() else None

    def _build_donate_tab(self, tabs):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Ủng hộ NAV Tools"))
        qr = QLabel()
        if self._get_or_fetch_qr():
            self._load_gemini_screenshot(qr, "donate_qr.png", 260)
        layout.addWidget(qr)
        layout.addStretch()
        tabs.addTab(tab, "❤️ Ủng hộ team")

    def _copy_to_clipboard(self, text, button=None):
        app = self.window().windowHandle()
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(str(text or ""))
        if button:
            old = button.text()
            button.setText("Copied")
            QThread.msleep(150)
            button.setText(old)

    def _make_tier_widget(self, account):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        tier_str = str(account.tier).upper()
        if "ULTRA" in tier_str:
            display = "Ultra"
            color = "#f59e0b"  # amber
        elif "PAYGATE" in tier_str or "PRO" in tier_str or "TIER_TWO" in tier_str:
            display = "Pro"
            color = "#a78bfa"  # purple
        else:
            display = "Thường"
            color = "#94a3b8"  # gray
            
        label = QLabel(display)
        label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")
        
        sync_btn = QPushButton("Đồng bộ")
        sync_btn.setToolTip("Đồng bộ loại tài khoản (Pro/Ultra) từ nền tảng")
        sync_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        sync_btn.setStyleSheet("QPushButton { color: #3b82f6; font-size: 11px; font-weight: bold; background: transparent; border: 1px solid #3b82f6; border-radius: 4px; padding: 3px 8px; } QPushButton:hover { background: #1e3a8a; color: white; }")
        def _on_sync_clicked():
            sync_btn.setEnabled(False)
            sync_btn.setStyleSheet("QPushButton { color: #f59e0b; font-size: 11px; font-weight: bold; background: transparent; border: 1px solid #f59e0b; border-radius: 4px; padding: 3px 8px; }")
            
            from PySide6.QtCore import QTimer
            timer = QTimer(sync_btn)
            frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            timer.frame = 0
            def animate():
                sync_btn.setText(f"{frames[timer.frame]} Đang đồng bộ...")
                timer.frame = (timer.frame + 1) % len(frames)
                
            timer.timeout.connect(animate)
            timer.start(100)
            sync_btn._anim_timer = timer
            
            self._sync_account_tier(account, sync_btn)
            
        sync_btn.clicked.connect(_on_sync_clicked)
        
        layout.addStretch()
        layout.addWidget(label)
        layout.addWidget(sync_btn)
        layout.addStretch()
        return box

    def _sync_account_tier(self, account, btn):
        if btn is not None:
            self._manual_sync_accounts.add(account.id)
        async def _run_test():
            import subprocess
            import socket
            from playwright.async_api import async_playwright
            from utils.platform import find_chrome
            
            cookie_path = account.cookie_path
            chrome = find_chrome()
            if not chrome:
                return "Không tìm thấy Chrome"
                
            # Wait 1.5 seconds initially to allow previous browser to fully release profile locks
            await asyncio.sleep(1.5)
            
            # Find a free port
            s = socket.socket()
            s.bind(('', 0))
            port = s.getsockname()[1]
            s.close()
            
            # Launch native Chrome in headed mode offscreen to bypass any headless bot checks
            proc = subprocess.Popen([
                chrome,
                f"--user-data-dir={cookie_path}",
                f"--remote-debugging-port={port}",
                "--window-size=400,300",
                "--window-position=-3000,-3000",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-features=LockProfileCookieDatabase"
            ])
            
            browser = None
            try:
                async with async_playwright() as p:
                    # Connect over CDP
                    for attempt in range(15):
                        if proc.poll() is not None:
                            return "Chrome exited prematurely"
                        try:
                            browser = await p.chromium.connect_over_cdp(f"http://localhost:{port}")
                            break
                        except:
                            await asyncio.sleep(0.5)
                    
                    if not browser:
                        return "Failed to connect over CDP"
                        
                    contexts = browser.contexts
                    if contexts:
                        page = contexts[0].pages[0] if contexts[0].pages else await contexts[0].new_page()
                        
                        # LAYER 1: GOOGLE SESSION
                        await page.goto('https://myaccount.google.com/', wait_until='domcontentloaded')
                        await asyncio.sleep(2)
                        google_ok = not await page.evaluate("""!!document.querySelector('input[type="email"]') || document.body.innerText.includes("Đăng nhập") || document.body.innerText.includes("Sign in")""")
                        
                        # LAYER 2 & 3: NextAuth API
                        await page.goto("https://labs.google/fx/vi/tools/flow", wait_until="domcontentloaded")
                        await asyncio.sleep(2)
                        session = await page.evaluate('''async () => { try { const r = await fetch('/fx/api/auth/session', {credentials: "include"}); if (!r.ok) return {}; return await r.json(); } catch(e) { return {}; } }''')
                        token = (session or {}).get('accessToken') or (session or {}).get('access_token')
                        video_fx_ok = google_ok and bool(token)
                        
                        if not google_ok or not video_fx_ok:
                            return "Tài khoản cần cấp quyền Video FX. Vui lòng bấm 'Sửa' để đăng nhập lại."
                            
                        # LAYER 3: PLAN DETECTOR
                        tier = 'Thường' 
                        
                        plan_found = False
                        if token:
                            api_res = await page.evaluate('''async ({url, token}) => { try { const r = await fetch(url, { headers: {'Authorization': 'Bearer ' + token} }); return r.ok ? await r.json() : {}; } catch(e) { return {}; } }''', {'url': 'https://labs.google/fx/api/trpc/videoFx.getUser?input=%7B%7D', 'token': token})
                            data = str(((api_res or {}).get('result', {}).get('data', {}).get('json')) or {}).lower()
                            if 'ultra' in data: tier = 'Ultra'; plan_found = True
                            elif 'tier_two' in data or 'pro' in data or 'paygate' in data: tier = 'Pro'; plan_found = True
                        
                        if not plan_found:
                            texts = await page.evaluate('() => document.body.innerText.toLowerCase()')
                            if 'ultra' in texts: tier = 'Ultra'
                            elif 'pro' in texts or 'tier 2' in texts: tier = 'Pro'
                            
                        return tier
                    return "No browser contexts"
            except Exception as e:
                return str(e)
            finally:
                if browser:
                    try: await browser.close()
                    except: pass
                # Clean shutdown of Chrome process
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                except:
                    try: proc.terminate()
                    except: pass
                    
        import threading
        def worker():
            import asyncio
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            try:
                tier = asyncio.run(_run_test())
            except Exception as e:
                tier = str(e)
                
            if tier in ('Pro', 'Ultra', 'Thường'):
                QMetaObject.invokeMethod(self, '_on_sync_success', Qt.QueuedConnection, Q_ARG(int, account.id), Q_ARG(str, tier))
            else:
                QMetaObject.invokeMethod(self, '_on_sync_failed', Qt.QueuedConnection, Q_ARG(int, account.id), Q_ARG(str, tier))
                
        threading.Thread(target=worker, daemon=True).start()

    @Slot(int, str)
    def _on_sync_success(self, account_id: int, tier: str):
        try:
            account = self.db.get_account(account_id)
            if account:
                account.tier = tier
                self.db.update_account(account)
            self._load_accounts()
            if account_id in self._manual_sync_accounts:
                self._manual_sync_accounts.discard(account_id)
                QMessageBox.information(self, "Thành công", f"Đã đồng bộ loại tài khoản: {tier}")
        except Exception as e:
            log.error(f"Lỗi cập nhật tier: {e}")

    @Slot(int, str)
    def _on_sync_failed(self, account_id: int, error: str):
        self._load_accounts()
        is_manual = account_id in self._manual_sync_accounts
        if is_manual:
            self._manual_sync_accounts.discard(account_id)
        if "cấp quyền Video FX" in error or "Đăng nhập lại" in error or "Sửa" in error:
            if is_manual:
                reply = QMessageBox.question(self, "Cần thao tác", f"{error}\n\nBạn có muốn MỞ TRÌNH DUYỆT ngay bây giờ để xử lý không?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    account = self.db.get_account(account_id)
                    if account:
                          self._edit_account(account)
        else:
            if is_manual:
                QMessageBox.warning(self, "Lỗi đồng bộ", f"Đồng bộ thất bại.\nChi tiết lỗi: {error}")

    def _make_action_buttons(self, account):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        edit = QPushButton("Sửa")
        edit.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        edit.setStyleSheet("QPushButton { padding: 4px 12px; font-size: 11px; font-weight: 600; background: #1f2937; border: 1px solid #374151; color: #9ca3af; border-radius: 4px; } QPushButton:hover { background: #374151; color: #f3f4f6; }")
        edit.setToolTip("Mở trình duyệt để đổi tài khoản")
        delete = QPushButton("Xóa")
        delete.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        delete.setStyleSheet("QPushButton { padding: 4px 12px; font-size: 11px; font-weight: 600; background: transparent; border: 1px solid #ef4444; color: #f87171; border-radius: 4px; } QPushButton:hover { background: #7f1d1d; color: white; }")
        delete.setToolTip("Xóa tài khoản khỏi NAVTools")
        edit.clicked.connect(lambda _, a=account: self._edit_account(a))
        delete.clicked.connect(lambda _, a=account: self._delete_account(a))
        layout.addWidget(edit)
        layout.addWidget(delete)
        return box

    def _load_accounts(self):
        log.info(f"[UI_REFRESH_START] [{datetime.now().isoformat()}] Loading Google accounts from DB to table widget...")
        try:
            self.accounts = self.db.get_accounts()
        except Exception as e:
            log.warning(f"Could not load accounts: {e}")
            self.accounts = []
        self.accounts_table.setRowCount(0)
        for row, account in enumerate(self.accounts):
            self.accounts_table.insertRow(row)
            self.refresh_account_row(row, account)
        log.info(f"[UI_REFRESH_DONE] [{datetime.now().isoformat()}] Google accounts successfully loaded. Count={len(self.accounts)}")

    def refresh_account_row(self, row, account):
        email_item = QTableWidgetItem(account.email)
        email_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.accounts_table.setItem(row, 0, email_item)
        self.accounts_table.setCellWidget(row, 1, self._make_tier_widget(account))
        enabled = PremiumCheckBox()
        enabled.setChecked(bool(account.enabled))
        enabled.toggled.connect(lambda checked, a=account: self._toggle_account(a, checked))
        self.accounts_table.setCellWidget(row, 2, self._center(enabled))
        self.accounts_table.setCellWidget(row, 3, self._make_action_buttons(account))

    def _center(self, widget):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(widget)
        layout.addStretch()
        return box

    def _filter_accounts(self, text):
        needle = str(text or "").lower()
        for row, account in enumerate(self.accounts):
            self.accounts_table.setRowHidden(row, needle not in account.email.lower())

    def _find_free_port(self):
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def _delete_profile_session_cookie(self, profile_path, cookie_name):
        import sqlite3
        import os
        import psutil
        from pathlib import Path
        
        # Kill any orphan Chrome processes using this profile first
        try:
            abs_profile = os.path.abspath(profile_path).lower()
            for proc in psutil.process_iter(attrs=['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline']
                        if cmdline and any(abs_profile in str(arg).lower() for arg in cmdline):
                            log.info(f"[sync] Killing orphan Chrome process {proc.info['pid']} using profile: {profile_path}")
                            proc.kill()
                except Exception:
                    pass
        except Exception as pe:
            log.warning(f"[sync] Failed to kill orphan processes: {pe}")

        # Delete SingletonLock to avoid Chrome profile lock errors
        lock_file = os.path.join(profile_path, "SingletonLock")
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                log.info(f"[sync] Removed SingletonLock file for {profile_path}")
            except Exception as le:
                log.warning(f"[sync] Failed to remove SingletonLock: {le}")

        # Delete cookie
        for rel_path in ("Default/Network/Cookies", "Default/Cookies"):
            cookie_file = Path(profile_path) / rel_path
            if cookie_file.exists():
                try:
                    conn = sqlite3.connect(cookie_file)
                    conn.execute("DELETE FROM cookies WHERE name = ?", (cookie_name,))
                    conn.commit()
                    conn.close()
                    log.info(f"[sync] Successfully deleted old session cookie '{cookie_name}' from {cookie_file} to prevent auto-close loop.")
                except Exception as e:
                    log.warning(f"[sync] Failed to delete cookie from {cookie_file}: {e}")

    def _start_chrome_monitor(self, proc, profile_path, target_cookie, port=0):
        log.info(f"[MONITOR_START] Starting file-based monitor for cookie '{target_cookie}' (PID={proc.pid})...")
        def monitor_task():
            import time
            import sqlite3
            import shutil
            import subprocess
            from pathlib import Path
            
            profile_path_obj = Path(profile_path)
            found = False
            
            # Poll every 1.5 seconds up to 5 minutes (200 attempts)
            for i in range(200):
                if proc.poll() is not None:
                    log.info("[MONITOR_FILE] Chrome process exited natively.")
                    break
                    
                for cookies_rel in ("Default/Network/Cookies", "Default/Cookies"):
                    cookies_file = profile_path_obj / cookies_rel
                    if cookies_file.exists():
                        try:
                            # Copy to temp file to avoid locks
                            temp_ck = str(cookies_file) + ".sync_mon_tmp"
                            shutil.copy2(str(cookies_file), temp_ck)
                            
                            # Copy WAL file if exists to ensure database has latest commits
                            wal_file = Path(str(cookies_file) + "-wal")
                            temp_wal = temp_ck + "-wal"
                            wal_copied = False
                            if wal_file.exists():
                                try:
                                    shutil.copy2(str(wal_file), temp_wal)
                                    wal_copied = True
                                except Exception:
                                    pass
                                    
                            conn = sqlite3.connect(temp_ck)
                            cursor = conn.cursor()
                            if target_cookie == "sso":
                                cursor.execute(
                                    "SELECT 1 FROM cookies WHERE name = ? AND host_key LIKE ?",
                                    ("sso", "%grok.com%")
                                )
                            else:
                                cursor.execute(
                                    "SELECT 1 FROM cookies WHERE name IN ('__Secure-next-auth.session-token', 'next-auth.session-token') AND host_key LIKE ?",
                                    ("%google%",)
                                )
                            row = cursor.fetchone()
                            conn.close()
                            
                            try: os.remove(temp_ck)
                            except: pass
                            if wal_copied:
                                try: os.remove(temp_wal)
                                except: pass
                                
                            if row:
                                found = True
                                log.info(f"[COOKIE_FOUND] [{datetime.now().isoformat()}] Target session cookie found via sqlite polling.")
                                break
                        except Exception as e:
                            log.debug(f"[MONITOR_FILE] Failed to read cookies: {e}")
                            
                if found:
                    break
                time.sleep(1.5)
                
            if found:
                time.sleep(2.0)
                log.info(f"[AUTO_CLOSE] Closing Chrome browser (PID={proc.pid}) cleanly to sync...")
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                except Exception as close_err:
                    log.warning(f"[AUTO_CLOSE] taskkill failed: {close_err}")
                    try: proc.terminate()
                    except: pass
                    
        import threading
        threading.Thread(target=monitor_task, daemon=True).start()


    def _add_account(self):
        log.info(f"[LOGIN_BUTTON_CLICK] [{datetime.now().isoformat()}] User clicked add_google_btn (Google account setup)")
        if self.google_proc is not None:
            # User clicked "Đã đăng nhập xong"
            log.info(f"[LOGIN_VERIFIED] [{datetime.now().isoformat()}] User clicked 'Đăng nhập xong' button manually.")
            proc = self.google_proc
            self.google_proc = None
            
            # Kill Chrome process tree to release the lock
            import subprocess
            try:
                log.info(f"[BROWSER_CLOSE_START] [{datetime.now().isoformat()}] Force killing Chrome process tree (PID={proc.pid}) to release sqlite database lock...")
                kill_res = subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, text=True)
                log.info(f"[BROWSER_CLOSE_DONE] [{datetime.now().isoformat()}] Taskkill result: stdout={kill_res.stdout.strip()}, stderr={kill_res.stderr.strip()}")
            except Exception as kill_err:
                log.warning(f"[BROWSER_CLOSE_ERROR] Failed taskkill, trying terminate: {kill_err}")
                try: proc.terminate()
                except: pass
                
            # Start sync
            self.add_google_btn.setText("Đang đồng bộ...")
            self.add_google_btn.setEnabled(False)
            self._monitor_login_and_fetch(self.temp_google_profile_path)
            return

        chrome = find_chrome()
        if not chrome:
            QMessageBox.warning(self, "Không tìm thấy Chrome", "Đăng nhập Google cần Chrome.")
            return
        import time
        profile_path = BROWSER_PROFILE_DIR / f"google_{int(time.time())}"
        profile_path.mkdir(parents=True, exist_ok=True)
        self.temp_google_profile_path = profile_path
        
        import subprocess
        try:
            log.info(f"[LOGIN_START] [{datetime.now().isoformat()}] Google Login: Launching Chrome native...")
            port = self._find_free_port()
            proc = subprocess.Popen([
                chrome,
                f"--user-data-dir={profile_path}",
                "--no-first-run",
                "--disable-gpu",
                "--no-sandbox",
                "--no-default-browser-check",
                "--disable-sync",
                "--disable-signin-promo",
                "--disable-features=LockProfileCookieDatabase,BackgroundMode",
                "--password-store=basic",
                "https://labs.google/fx/vi/tools/flow"
            ])
            self.google_proc = proc
            log.info(f"[LOGIN_WINDOW_OPEN] [{datetime.now().isoformat()}] Chrome browser opened successfully. PID={proc.pid}")
            
            # Start background monitor to close automatically if they succeed without clicking
            self._start_chrome_monitor(proc, profile_path, "__Secure-next-auth.session-token", port)
            
            self.add_google_btn.setText("Đăng nhập xong (Click vào đây)")
            self.add_google_btn.setStyleSheet("QPushButton { padding: 6px 16px; font-weight: bold; background: #10b981; border: 1px solid #059669; color: white; border-radius: 6px; } QPushButton:hover { background: #059669; }")
            
            def wait_task():
                log.info(f"[wait_task] [{datetime.now().isoformat()}] Waiting for Google Chrome process to exit...")
                proc.wait()
                log.info(f"[wait_task] [{datetime.now().isoformat()}] Google Chrome process exited. ExitCode={proc.returncode}")
                if self.google_proc == proc: # If not already handled by click
                    log.info(f"[LOGIN_VERIFIED] [{datetime.now().isoformat()}] Chrome browser closed by user. Triggering sync process.")
                    self.google_proc = None
                    self.login_status_changed.emit("Đang đồng bộ...", True)
                    self._monitor_login_and_fetch(profile_path)
                
            threading.Thread(target=wait_task, daemon=True).start()
            
        except Exception as e:
            log.error(f"[LOGIN_FAILED] [{datetime.now().isoformat()}] Failed to launch Google Chrome: {e}")
            self.google_proc = None
            self.add_google_btn.setText("Thêm tài khoản Google")
            self.add_google_btn.setEnabled(True)
            self.add_google_btn.setStyleSheet("")
            QMessageBox.warning(self, "Lỗi", f"Không thể mở trình duyệt: {e}")

    def _monitor_login_and_fetch(self, profile_path):
        thread = threading.Thread(target=lambda: self._sync_account_from_profile(profile_path, "google"), daemon=True)
        thread.start()
        self._login_thread = thread

    def _sync_account_from_profile(self, profile_path, account_type, email_hint=None, is_edit=False):
        """Read account data directly from Chrome profile (no Playwright needed).
        
        After the user logs in via native Chrome and Chrome is closed/killed,
        we read the email from Preferences/Login Data and verify login via Cookies DB.
        """
        import time as _time
        for attempt in range(15):
            try:
                # Test opening Preferences to see if locks are released
                p_file = Path(profile_path) / "Default" / "Preferences"
                if p_file.exists():
                    with p_file.open("r", encoding="utf-8") as f:
                        pass
                break
            except PermissionError:
                _time.sleep(0.1)
        
        log.info(f"[SESSION_EXTRACT_START] [{datetime.now().isoformat()}] Starting credentials extraction from Chrome profile SQLite databases. path={profile_path}")
        detected_email = email_hint or getattr(self, "temp_detected_email", None)
        if hasattr(self, "temp_detected_email"):
            self.temp_detected_email = None
        log.info(f"[sync] Starting profile sync: type={account_type}, path={profile_path}, hint={email_hint}, detected_from_cdp={detected_email}")
        
        # === Step 1: Detect email ===
        # Method 1: Chrome Preferences (account_info / signin)
        if not detected_email:
            for prefs_name in ("Default/Preferences", "Default/Secure Preferences"):
                prefs_file = profile_path / prefs_name
                if not prefs_file.exists():
                    continue
                try:
                    with prefs_file.open("r", encoding="utf-8") as f:
                        prefs = json.load(f)
                    acct_info = prefs.get("account_info") or []
                    if acct_info:
                        detected_email = acct_info[0].get("email")
                    if not detected_email:
                        signin = prefs.get("signin") or {}
                        detected_email = signin.get("allowed_username") or signin.get("username")
                    if not detected_email:
                        profile_data = prefs.get("profile") or {}
                        name = profile_data.get("name") or ""
                        if "@" in name:
                            detected_email = name
                    if detected_email:
                        log.info(f"[TOKEN_EXTRACTED] [{datetime.now().isoformat()}] Email extracted from Preferences: {detected_email}")
                        break
                except Exception as e:
                    log.warning(f"[sync] Could not read {prefs_file}: {e}")
        
        # Method 2: Chrome Login Data (saved passwords — username is plain text)
        if not detected_email:
            login_data_path = profile_path / "Default" / "Login Data"
            if login_data_path.exists():
                try:
                    temp_ld = str(login_data_path) + ".sync_tmp"
                    shutil.copy2(str(login_data_path), temp_ld)
                    conn = sqlite3.connect(temp_ld)
                    if account_type == "grok":
                        rows = conn.execute(
                            "SELECT username_value FROM logins WHERE "
                            "(origin_url LIKE '%grok%' OR signon_realm LIKE '%grok%' OR "
                            "origin_url LIKE '%x.com%' OR signon_realm LIKE '%x.com%' OR "
                            "origin_url LIKE '%twitter%' OR signon_realm LIKE '%twitter%') "
                            "AND username_value != '' ORDER BY date_last_used DESC LIMIT 1"
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            "SELECT username_value FROM logins WHERE "
                            "(origin_url LIKE '%google%' OR signon_realm LIKE '%google%' OR "
                            "origin_url LIKE '%labs.google%') "
                            "AND username_value != '' ORDER BY date_last_used DESC LIMIT 1"
                        ).fetchall()
                    conn.close()
                    try: os.remove(temp_ld)
                    except: pass
                    if rows and rows[0][0]:
                        detected_email = rows[0][0]
                        log.info(f"[TOKEN_EXTRACTED] [{datetime.now().isoformat()}] Email extracted from Login Data: {detected_email}")
                except Exception as e:
                    log.warning(f"[sync] Could not read Login Data: {e}")
        
        # Method 3: Chrome History (last Google/Grok login URL)
        if not detected_email:
            history_path = profile_path / "Default" / "History"
            if history_path.exists():
                try:
                    temp_h = str(history_path) + ".sync_tmp"
                    shutil.copy2(str(history_path), temp_h)
                    conn = sqlite3.connect(temp_h)
                    if account_type == "grok":
                        rows = conn.execute(
                            "SELECT url FROM urls WHERE url LIKE '%accounts.google.com%' "
                            "AND url LIKE '%Email%' ORDER BY last_visit_time DESC LIMIT 5"
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            "SELECT url FROM urls WHERE url LIKE '%accounts.google.com%' "
                            "ORDER BY last_visit_time DESC LIMIT 5"
                        ).fetchall()
                    conn.close()
                    try: os.remove(temp_h)
                    except: pass
                    import re
                    for row in (rows or []):
                        url = row[0]
                        match = re.search(r'[Ee]mail=([^&]+)', url)
                        if match:
                            import urllib.parse
                            detected_email = urllib.parse.unquote(match.group(1))
                            log.info(f"[TOKEN_EXTRACTED] [{datetime.now().isoformat()}] Email extracted from History URL: {detected_email}")
                            break
                except Exception as e:
                    log.warning(f"[sync] Could not read History: {e}")
        
        # === Step 2: Verify login via Cookies DB ===
        if account_type == "grok":
            target_cookie = "sso"
            cookie_host = "%grok.com%"
        else:
            target_cookie = "__Secure-next-auth.session-token"
            cookie_host = "%google%"
        
        login_confirmed = False
        for cookies_rel in ("Default/Network/Cookies", "Default/Cookies"):
            cookies_file = profile_path / cookies_rel
            if cookies_file.exists():
                try:
                    temp_ck = str(cookies_file) + ".sync_tmp"
                    shutil.copy2(str(cookies_file), temp_ck)
                    conn = sqlite3.connect(temp_ck)
                    if account_type == "grok":
                        row = conn.execute(
                            "SELECT 1 FROM cookies WHERE name = ? AND host_key LIKE ?",
                            (target_cookie, cookie_host)
                        ).fetchone()
                    else:
                        row = conn.execute(
                            "SELECT 1 FROM cookies WHERE name IN ('__Secure-next-auth.session-token', 'next-auth.session-token') AND host_key LIKE ?",
                            (cookie_host,)
                        ).fetchone()
                    login_confirmed = row is not None
                    conn.close()
                    try: os.remove(temp_ck)
                    except: pass
                    if login_confirmed:
                        log.info(f"[COOKIE_SAVED] [{datetime.now().isoformat()}] Cookie verification passed for '{target_cookie}'.")
                        log.info(f"[SESSION_EXTRACT_DONE] [{datetime.now().isoformat()}] Session database check complete. status=CONFIRMED")
                        break
                except Exception as e:
                    log.warning(f"[sync] Could not check cookies: {e}")
        
        # === Step 3: Fallback — auto-generate email if not detected ===
        if login_confirmed and not detected_email:
            import time
            timestamp = int(time.time()) % 100000
            if account_type == "grok":
                detected_email = f"grok_user_{timestamp}@grok.com"
            else:
                detected_email = f"google_user_{timestamp}@gmail.com"
            log.info(f"[sync] Email not detected. Auto-generated fallback name: {detected_email}")
        
        # === Step 4: Report results ===
        from PySide6.QtCore import QMetaObject, Qt, Q_ARG
        
        if account_type == "grok":
            if login_confirmed and detected_email:
                detected_tier = getattr(self, "temp_detected_tier", "Grok") or "Grok"
                self.temp_detected_tier = None  # Clear after use
                log.info(f"[LOGIN_SUCCESS] [{datetime.now().isoformat()}] Grok login validation succeeded for {detected_email}, tier={detected_tier}")
                QMetaObject.invokeMethod(self, "_on_grok_login_success", Qt.QueuedConnection,
                    Q_ARG(str, detected_email), Q_ARG(str, str(profile_path)), Q_ARG(str, detected_tier))
            elif login_confirmed:
                log.warning("[sync] Grok login confirmed but no email")
                QMetaObject.invokeMethod(self, "_on_grok_login_failed", Qt.QueuedConnection,
                    Q_ARG(str, "Đã đăng nhập nhưng không thể phát hiện email. Vui lòng thử lại."))
            else:
                log.warning("[sync] Grok login NOT confirmed")
                QMetaObject.invokeMethod(self, "_on_grok_login_failed", Qt.QueuedConnection,
                    Q_ARG(str, "Không phát hiện đăng nhập Grok. Hãy đăng nhập và thử lại."))
                if not is_edit:
                    try: shutil.rmtree(profile_path, ignore_errors=True)
                    except: pass
            self.grok_login_status_changed.emit("Thêm tài khoản Grok", False)
        else:
            if detected_email and (login_confirmed or detected_email):
                detected_tier = getattr(self, "temp_detected_tier", "Thường") or "Thường"
                self.temp_detected_tier = None  # Clear after use
                log.info(f"[LOGIN_SUCCESS] [{datetime.now().isoformat()}] Google login validation succeeded for {detected_email}, tier={detected_tier}")
                QMetaObject.invokeMethod(self, "_on_login_success", Qt.QueuedConnection,
                    Q_ARG(str, detected_email), Q_ARG(str, str(profile_path)), Q_ARG(str, detected_tier))
            elif login_confirmed:
                log.warning("[sync] Google login confirmed but no email")
                QMetaObject.invokeMethod(self, "_on_login_failed", Qt.QueuedConnection,
                    Q_ARG(str, "Đã đăng nhập nhưng không thể phát hiện email. Vui lòng thử lại."))
            else:
                log.warning("[sync] Google login NOT confirmed")
                QMetaObject.invokeMethod(self, "_on_login_failed", Qt.QueuedConnection,
                    Q_ARG(str, "Không phát hiện đăng nhập Google. Hãy đăng nhập và thử lại."))
            self.login_status_changed.emit("Thêm tài khoản Google", False)

    @Slot(str)
    def _prompt_email_slot(self, account_type):
        """Fallback: ask user to enter their email when auto-detection fails.
        Loop until a valid email (containing '@') is entered, or the user clicks Cancel.
        """
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        label = "Nhập email tài khoản Grok:" if account_type == "grok" else "Nhập email tài khoản Google:"
        
        while True:
            email, ok = QInputDialog.getText(self, "Yêu cầu nhập Email", label)
            if not ok:
                # User clicked Cancel or closed the dialog
                self._pending_email_result = "__CANCELLED__"
                break
            
            email_val = email.strip()
            if "@" in email_val:
                self._pending_email_result = email_val
                break
            else:
                QMessageBox.warning(self, "Email không hợp lệ", "Email phải chứa ký tự '@'. Vui lòng nhập lại.")
                
        if hasattr(self, '_email_event') and self._email_event:
            self._email_event.set()

    async def _async_playwright_login(self, profile_path):
        import sys
        import tempfile
        import os
        from datetime import datetime
        
        # Phase 3 diagnostic variables
        meipass = getattr(sys, "_MEIPASS", "Not in Packaged Mode")
        cwd = os.getcwd()
        temp_dir = tempfile.gettempdir()
        
        log.info(f"[LOGIN_START] [{datetime.now().isoformat()}] Google Playwright Login init.")
        log.info(f"[LOGIN_START] MEIPASS: {meipass}")
        log.info(f"[LOGIN_START] CWD: {cwd}")
        log.info(f"[LOGIN_START] Temp Dir: {temp_dir}")
        log.info(f"[LOGIN_START] Target Profile Path: {profile_path}")
        
        from playwright.async_api import async_playwright
        chrome_exe = find_chrome()
        log.info(f"[LOGIN_START] Resolved Chrome Executable Path: {chrome_exe}")
        
        browser = None
        email = None
        tier = "Thường"
        
        try:
            self.login_status_changed.emit("Đang khởi động Chrome...", True)
            log.info(f"[LOGIN_START] [{datetime.now().isoformat()}] Launching Playwright persistent context...")
            
            async with async_playwright() as p:
                log.info(f"[LOGIN_START] Playwright context initialized. Launching chromium...")
                for attempt in range(5):
                    try:
                        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                        browser = await p.chromium.launch_persistent_context(
                            user_data_dir=str(profile_path),
                            headless=False,
                            executable_path=chrome_exe,
                            args=STEALTH_CHROME_ARGS,
                            ignore_default_args=["--enable-automation", "--no-sandbox"],
                            user_agent=user_agent,
                        )
                        log.info(f"[LOGIN_START] launch_persistent_context success on attempt {attempt+1}")
                        break
                    except Exception as launch_err:
                        log.warning(f"[LOGIN_START] Launch attempt {attempt+1} failed: {launch_err}")
                        if attempt == 4:
                            raise launch_err
                        await asyncio.sleep(1)
                
                log.info(f"[LOGIN_START] Applying stealth scripts to context...")
                await apply_stealth_to_context(browser)
                
                page = browser.pages[0] if browser.pages else await browser.new_page()
                self.login_status_changed.emit("Đang chờ đăng nhập...", True)
                
                log.info(f"[LOGIN_START] Navigating to Google Labs FX...")
                await page.goto("https://labs.google/fx/vi/tools/flow", wait_until="commit")
                
                log.info(f"[LOGIN_START] Page loaded. Starting credential monitoring loop (180 iterations)...")
                for i in range(180):
                    if page.is_closed():
                        log.info(f"[LOGIN_START] Page was closed by user.")
                        break
                    await asyncio.sleep(2)
                    url = page.url or ""
                    
                    if "labs.google" in url:
                        try:
                            result = await page.evaluate('''async () => {
                                try {
                                    const r = await fetch("https://labs.google/fx/api/auth/session", {credentials: "include"});
                                    if (!r.ok) return {};
                                    return await r.json();
                                } catch(e) { return {}; }
                            }''')
                            email = (result or {}).get("user", {}).get("email")
                        except Exception as eval_err:
                            log.warning(f"[LOGIN_START] Session eval failed: {eval_err}")
                            
                        if email:
                            log.info(f"[LOGIN_SUCCESS] [{datetime.now().isoformat()}] Detected email={email} at iteration {i}")
                            try:
                                api_res = await page.evaluate('''async () => {
                                    try {
                                        const r = await fetch("https://labs.google/fx/api/trpc/videoFx.getUser?input=%7B%7D");
                                        return r.ok ? await r.json() : {};
                                    } catch(e) { return {}; }
                                }''')
                                api_data = str(((api_res or {}).get("result", {}).get("data", {}).get("json")) or {}).lower()
                                if "ultra" in api_data:
                                    tier = "Ultra"
                                elif "tier_two" in api_data or "pro" in api_data or "paygate" in api_data:
                                    tier = "Pro"
                                else:
                                    await page.goto("https://labs.google/fx/vi/tools/flow", wait_until="commit")
                                    await asyncio.sleep(3)
                                    texts = await page.evaluate('() => document.body.innerText.toLowerCase()')
                                    if "ultra" in texts: tier = "Ultra"
                                    elif "pro" in texts or "tier 2" in texts: tier = "Pro"
                            except Exception as plan_err:
                                log.warning(f"[LOGIN_SUCCESS] Plan extraction error: {plan_err}")
                            break
                
                # Verify storage state save (H1)
                log.info(f"[SESSION_SAVE_START] [{datetime.now().isoformat()}] Explicitly saving storage state...")
                try:
                    storage_state_path = Path(profile_path) / "storage_state.json"
                    await browser.storage_state(path=str(storage_state_path))
                    log.info(f"[SESSION_SAVE_DONE] [{datetime.now().isoformat()}] storage_state.json saved to {storage_state_path}")
                except Exception as save_err:
                    log.error(f"[SESSION_SAVE_ERROR] [{datetime.now().isoformat()}] Failed to save storage state: {save_err}")
                
                log.info(f"[BROWSER_CLOSE_START] [{datetime.now().isoformat()}] Closing Playwright browser context...")
                await browser.close()
                log.info(f"[BROWSER_CLOSE_DONE] [{datetime.now().isoformat()}] Browser context closed.")
                browser = None
                
                log.info(f"[PLAYWRIGHT_STOP] [{datetime.now().isoformat()}] Playwright async block ending.")
                
                from PySide6.QtCore import QMetaObject, Qt, Q_ARG
                if email:
                    log.info(f"[ACCOUNT_UPDATE_START] [{datetime.now().isoformat()}] Invoking _on_login_success slot...")
                    QMetaObject.invokeMethod(self, "_on_login_success", Qt.QueuedConnection,
                        Q_ARG(str, email), Q_ARG(str, str(profile_path)), Q_ARG(str, tier))
                else:
                    log.warning(f"[LOGIN_FAILED] [{datetime.now().isoformat()}] Login timed out or no email.")
                    QMetaObject.invokeMethod(self, "_on_login_failed", Qt.QueuedConnection, 
                        Q_ARG(str, "Đăng nhập quá thời gian chờ hoặc không tìm thấy tài khoản."))
                        
        except Exception as e:
            log.error(f"[LOGIN_EXCEPTION] [{datetime.now().isoformat()}] Playwright loop exception: {e}", exc_info=True)
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(self, "_on_login_failed", Qt.QueuedConnection, Q_ARG(str, f"Lỗi trình duyệt: {e}"))
        finally:
            self.login_status_changed.emit("Thêm tài khoản Google", False)
            if browser:
                try:
                    log.info(f"[BROWSER_CLOSE_START] [{datetime.now().isoformat()}] Finally block closing browser context...")
                    await browser.close()
                    log.info(f"[BROWSER_CLOSE_DONE] [{datetime.now().isoformat()}] Finally block context closed.")
                except Exception as final_err:
                    log.error(f"[BROWSER_CLOSE_ERROR] Finally block context close exception: {final_err}")

    @Slot(str, str, str)
    def _on_login_success(self, email, cookie_path, tier):
        log.info(f"[ACCOUNT_SAVE_START] [{datetime.now().isoformat()}] Google DB Save started for email={email}")
        account = None
        for existing in self.db.get_accounts():
            if existing.email == email:
                account = existing
                break
        
        is_new = False
        if account is None:
            account = self.db.add_account(email)
            is_new = True
            
        account.cookie_path = cookie_path
        
        # Preserve Pro/Ultra tier if already set, unless the new tier is explicitly a higher tier
        if not is_new and account.tier in ("Pro", "Ultra") and tier == "Thường":
            log.info(f"[sync] Preserving existing tier '{account.tier}' for Google account {email} (new tier hint was 'Thường')")
        else:
            if tier:
                account.tier = tier
                
        self.db.update_account(account)
        log.info(f"[ACCOUNT_SAVE_DONE] [{datetime.now().isoformat()}] Google account successfully updated in Database. ID={account.id}, Email={account.email}")
        self._load_accounts()
        
        # Only trigger background tier sync if tier was not already detected by CDP monitor
        if tier == "Thường":
            log.info(f"[sync] Tier not yet detected, triggering background sync for Google account {email}")
            self._sync_account_tier(account, None)
        else:
            log.info(f"[sync] Tier already detected as '{tier}' via CDP, skipping background sync")
            
        log.info(f"[FINAL_STATE] [{datetime.now().isoformat()}] Google login UI update complete. Success.")
        QMetaObject.invokeMethod(self.parent(), "_refresh_account_headers", Qt.QueuedConnection)
        QMessageBox.information(self, "Đã lưu đăng nhập", f"Đã lưu tài khoản: {email}\nLoại tài khoản: {account.tier}")

    def _on_login_status(self, text):
        log.info(text)

    @Slot(str)
    def _on_login_failed(self, message):
        QMessageBox.warning(self, "Đăng nhập thất bại", str(message))

    @Slot()
    def _on_login_finished(self):
        self._login_thread = None

    def _renew_session(self, account):
        if not account:
            return
        thread = threading.Thread(target=lambda: self._run_renew(account.id, account.email, account.cookie_path, None), daemon=True)
        thread.start()
        self._renew_thread = thread

    def _run_renew(self, account_id, email, cookie_path, progress=None):
        try:
            asyncio.run(self._async_renew(account_id, email, cookie_path, progress))
        except Exception as e:
            self._on_renew_failed(account_id, str(e))

    def _cleanup_renew_chrome(self, profile_dir):
        return None

    async def _async_renew(self, account_id, email, cookie_path, progress=None):
        await asyncio.sleep(0.5)
        info = _read_chrome_cookies(Path(cookie_path or BROWSER_PROFILE_DIR))
        
        # Fetch actual tier from platform using real Chrome binary
        tier = "Thường"
        browser = None
        try:
            from services.flow_client import FlowClient
            from playwright.async_api import async_playwright
            chrome_exe = find_chrome()
            cp = cookie_path or str(BROWSER_PROFILE_DIR)
            async with async_playwright() as p:
                browser = await asyncio.wait_for(p.chromium.launch_persistent_context(
                      user_data_dir=cp,
                      headless=False,
                      executable_path=chrome_exe,
                      args=[
                          "--window-size=1,1",
                          "--window-position=-2000,-2000",
                          "--no-first-run",
                          "--disable-blink-features=AutomationControlled",
                          "--disable-infobars",
                          "--disable-extensions",
                          "--disable-features=TranslateUI,GlobalMediaControls",
                      ],
                ), timeout=15.0)
                page = await browser.new_page()
                client = FlowClient(page, cp, email)
                try:
                  await asyncio.wait_for(client.check_credits(), timeout=30.0)
                except Exception:
                  pass
                tier = await asyncio.wait_for(client.get_account_tier(), timeout=40.0)
        except Exception as e:
            log.warning(f"Failed to fetch real tier during renew: {e}")
        finally:
            if browser:
                try:
                      await browser.close()
                except Exception:
                  pass
            
        from PySide6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(self, "_on_renew_success", Qt.QueuedConnection,
            Q_ARG(int, account_id), Q_ARG(str, info.get("email") or email), Q_ARG(str, tier))

    @Slot(int, str, str)
    def _on_renew_success(self, account_id, email, tier):
        account = self.db.get_account(account_id)
        if account:
            account.email = email or account.email
            if tier:
                account.tier = tier
            self.db.update_account(account)
        self._load_accounts()

    @Slot(int, str)
    def _on_renew_failed(self, account_id, message):
        QMessageBox.warning(self, "Gia hạn thất bại", str(message))

    @Slot()
    def _on_renew_finished(self):
        self._renew_thread = None

    def _toggle_account(self, account, enabled):
        account.enabled = bool(enabled)
        self.db.update_account(account)

    def _edit_account(self, account):
        """Open Chrome to re-login / change this account."""
        if not account:
            return
        profile_path = account.cookie_path
        if not profile_path:
            QMessageBox.warning(self, "Lỗi", "Tài khoản này chưa có profile.")
            return
            
        if account.id in self.edit_procs:
            proc = self.edit_procs[account.id]
            del self.edit_procs[account.id]
            
            # Kill Chrome process tree to release the lock
            import subprocess
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            except:
                try: proc.terminate()
                except: pass
                
            self.login_status_changed.emit("Đang đồng bộ...", True)
            self._monitor_login_and_fetch(Path(profile_path))
            return
            
        chrome = find_chrome()
        if not chrome:
            QMessageBox.warning(self, "Không tìm thấy Chrome", "Đăng nhập cần Chrome.")
            return
            
        import subprocess
        try:
            self._delete_profile_session_cookie(profile_path, "__Secure-next-auth.session-token")
            proc = subprocess.Popen([
                chrome,
                f"--user-data-dir={profile_path}",
                "--no-first-run",
                "--disable-gpu",
                "--no-sandbox",
                "--no-default-browser-check",
                "--disable-sync",
                "--disable-signin-promo",
                "--disable-features=LockProfileCookieDatabase,BackgroundMode",
                "--password-store=basic",
                "https://labs.google/fx/vi/tools/flow"
            ])
            self.edit_procs[account.id] = proc
            
            # Start background monitor to close automatically if they succeed without clicking
            self._start_chrome_monitor(proc, profile_path, "__Secure-next-auth.session-token", 0)
            
            sender = self.sender()
            if sender and isinstance(sender, QPushButton):
                sender.setText("Đồng bộ")
                sender.setStyleSheet("QPushButton { padding: 4px 12px; font-size: 11px; font-weight: bold; background: #10b981; border: 1px solid #059669; color: white; border-radius: 4px; } QPushButton:hover { background: #059669; }")
            
            def wait_task():
                proc.wait()
                if account.id in self.edit_procs:
                    del self.edit_procs[account.id]
                    self.login_status_changed.emit("Đang đồng bộ...", True)
                    self._monitor_login_and_fetch(Path(profile_path))
                
            threading.Thread(target=wait_task, daemon=True).start()
            
        except Exception as e:
            if account.id in self.edit_procs:
                del self.edit_procs[account.id]
            self.login_status_changed.emit("Thêm tài khoản Google", False)
            QMessageBox.warning(self, "Lỗi", f"Không thể mở trình duyệt: {e}")

    def _delete_account(self, account):
        if not account:
            return
        if QMessageBox.question(self, "Xóa tài khoản", f"Xóa {account.email}?") == QMessageBox.Yes:
            self.db.delete_account(account.id)
            self._load_accounts()

    def _save_settings(self):
        if hasattr(self, "gemini_key_edit"):
            self.settings.set("gemini_api_key", self.gemini_key_edit.text().strip())
        if hasattr(self, "auto_retry"):
            self.settings.set("auto_retry", self.auto_retry.isChecked())
        self.accept()

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    def _run_health_check_ui(self, account):
        if not account:
            return
        dlg = HealthCheckDialog(self, account)
        dlg.show()
        
        # Start background check thread
        thread = threading.Thread(target=lambda: asyncio.run(self._async_health_check(account, dlg)), daemon=True)
        thread.start()

    async def _async_health_check(self, account, dlg):
        from PySide6.QtCore import QMetaObject, Qt, Q_ARG
        import os
        from playwright.async_api import async_playwright
        
        def emit(step, status):
            QMetaObject.invokeMethod(dlg, "add_step", Qt.QueuedConnection, Q_ARG(str, step), Q_ARG(str, status))
            
        emit("Đọc DB thành công", "PASS")
        
        if not account:
            emit("Tìm thấy account", "FAIL: Account rỗng")
            return
        emit("Tìm thấy account", f"PASS: {account.email}")
        
        cookie_path = account.cookie_path
        if not cookie_path:
            emit("Tìm thấy profile path", "FAIL: Profile path rỗng")
            return
        emit("Tìm thấy profile path", f"PASS: {cookie_path}")
        
        if not os.path.exists(cookie_path):
            emit("Profile tồn tại", "FAIL: Thư mục không tồn tại trên ổ đĩa")
            return
        emit("Profile tồn tại", "PASS")
        
        from utils.platform import find_chrome
        chrome_exe = find_chrome()
        browser = None
        try:
            async with async_playwright() as p:
                emit("Mở được profile", "WAITING...")
                for attempt in range(5):
                    try:
                        browser = await asyncio.wait_for(p.chromium.launch_persistent_context(
                            user_data_dir=cookie_path, headless=True, executable_path=chrome_exe,
                            args=["--no-first-run", "--disable-infobars"]
                        ), timeout=15.0)
                        break
                    except Exception as e:
                        if attempt == 4: raise e
                        await asyncio.sleep(1)
                emit("Mở được profile", "PASS")
                
                page = await browser.new_page()
                
                # TẦNG 1: GOOGLE SESSION
                emit("TẦNG 1: Google Session", "WAITING...")
                await page.goto("https://myaccount.google.com/", wait_until="domcontentloaded")
                await asyncio.sleep(2)
                is_signin = await page.evaluate("""!!document.querySelector('input[type="email"]') || document.body.innerText.includes("Đăng nhập") || document.body.innerText.includes("Sign in")""")
                google_logged_in = not is_signin
                emit("TẦNG 1: Google Session", "OK" if google_logged_in else "FAIL")
                
                # TẦNG 2: VIDEO FX ACCESS (API CHECK)
                emit("TẦNG 2: Video FX Access", "WAITING...")
                session = await page.evaluate('''async () => {
                      try {
                          const r = await fetch("https://labs.google/fx/api/auth/session");
                          return await r.json();
                      } catch(e) { return {}; }
                }''')
                token = (session or {}).get("accessToken") or (session or {}).get("access_token")
                video_fx_access = google_logged_in and bool(token)
                emit("TẦNG 2: Video FX Access", "OK" if video_fx_access else "FAIL (Mất token Video FX)")
                
                # CHÚT LOGIC:
                if google_logged_in and video_fx_access:
                      emit("Session tổng thể", "PASS (Không bị hết hạn)")
                else:
                      emit("Session tổng thể", "FAIL (Cần bấm 'Sửa' để cấp quyền lại)")
                      return
                
                # TẦNG 3: PLAN DETECTOR
                emit("TẦNG 3: Plan Detector", "WAITING...")
                tier = "Thường"
                await page.goto("https://labs.google/fx/vi/tools/flow", wait_until="networkidle")
                await asyncio.sleep(2)
                
                plan_found = False
                if token:
                      api_res = await page.evaluate('''async ({url, token}) => {
                          try {
                              const r = await fetch(url, { headers: {"Authorization": "Bearer " + token} });
                              return r.ok ? await r.json() : {};
                          } catch(e) { return {}; }
                      }''', {"url": "https://labs.google/fx/api/trpc/videoFx.getUser?input=%7B%7D", "token": token})
                      api_data = str(((api_res or {}).get("result", {}).get("data", {}).get("json")) or {}).lower()
                      if "ultra" in api_data:
                          tier = "Ultra"
                          plan_found = True
                      elif "tier_two" in api_data or "pro" in api_data or "paygate" in api_data:
                          tier = "Pro"
                          plan_found = True
                
                if not plan_found:
                      texts = await page.evaluate('() => document.body.innerText.toLowerCase()')
                      if "ultra" in texts: tier = "Ultra"
                      elif "pro" in texts or "tier 2" in texts: tier = "Pro"
                
                emit("TẦNG 3: Plan Detector", tier)
                
                # Lấy Screenshot
                proof_path = str(Path(os.getcwd()) / "proof_debug_ui.png")
                await page.screenshot(path=proof_path)
                emit("Lấy Bằng Chứng", "PASS (proof_debug_ui.png)")
                
                emit("Cập nhật UI & DB", "Đang xử lý...")
                account.tier = tier
                self.db.update_account(account)
                QMetaObject.invokeMethod(self, "_load_accounts", Qt.QueuedConnection)
                emit("Cập nhật UI & DB", "PASS")
                emit("HOÀN TẤT", "Thành công!")
                
        except asyncio.TimeoutError:
            emit("Lỗi", "Quá thời gian chờ trình duyệt")
        except Exception as e:
            emit("Lỗi", str(e))
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

    def _build_grok_accounts_tab(self, tabs):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        top = QHBoxLayout()
        self.grok_search_edit = QLineEdit()
        self.grok_search_edit.setPlaceholderText("Tìm email tài khoản Grok...")
        self.grok_search_edit.textChanged.connect(self._filter_grok_accounts)
        
        self.add_grok_btn = QPushButton("Thêm tài khoản Grok")
        self.add_grok_btn.setObjectName("grok_add_btn")
        self.add_grok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_grok_btn.clicked.connect(self._add_grok_account)
        
        top.addWidget(self.grok_search_edit)
        top.addWidget(self.add_grok_btn)
        layout.addLayout(top)

        self.grok_accounts_table = QTableWidget(0, 4)
        self.grok_accounts_table.setHorizontalHeaderLabels(["Email", "Tài khoản", "Bật", "Thao tác"])
        self.grok_accounts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.grok_accounts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.grok_accounts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.grok_accounts_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        
        self.grok_accounts_table.setColumnWidth(1, 200)
        self.grok_accounts_table.setColumnWidth(2, 60)
        self.grok_accounts_table.setColumnWidth(3, 140)
        
        self.grok_accounts_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.grok_accounts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.grok_accounts_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.grok_accounts_table.verticalHeader().setDefaultSectionSize(38)
        self.grok_accounts_table.verticalHeader().setVisible(False)
        self.grok_accounts_table.setStyleSheet("QTableWidget::item:selected { background-color: transparent; }")
        layout.addWidget(self.grok_accounts_table)
        tabs.addTab(tab, "🤖 Tài khoản Grok")

    def _load_grok_accounts(self):
        log.info(f"[UI_REFRESH_START] [{datetime.now().isoformat()}] Loading Grok accounts from DB to table widget...")
        try:
            self.grok_accounts = self.db.get_accounts(account_type="grok")
        except Exception as e:
            log.warning(f"Could not load grok accounts: {e}")
            self.grok_accounts = []
        self.grok_accounts_table.setRowCount(0)
        for row, account in enumerate(self.grok_accounts):
            self.grok_accounts_table.insertRow(row)
            self.refresh_grok_account_row(row, account)
        log.info(f"[UI_REFRESH_DONE] [{datetime.now().isoformat()}] Grok accounts successfully loaded. Count={len(self.grok_accounts)}")

    def refresh_grok_account_row(self, row, account):
        email_item = QTableWidgetItem(account.email)
        email_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grok_accounts_table.setItem(row, 0, email_item)
        
        self.grok_accounts_table.setCellWidget(row, 1, self._make_grok_tier_widget(account))
        
        enabled = PremiumCheckBox()
        enabled.setChecked(bool(account.enabled))
        enabled.toggled.connect(lambda checked, a=account: self._toggle_account(a, checked))
        self.grok_accounts_table.setCellWidget(row, 2, self._center(enabled))
        
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        edit = QPushButton("Sửa")
        edit.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        edit.setStyleSheet("QPushButton { padding: 4px 12px; font-size: 11px; font-weight: 600; background: #1f2937; border: 1px solid #374151; color: #9ca3af; border-radius: 4px; } QPushButton:hover { background: #374151; color: #f3f4f6; }")
        
        delete = QPushButton("Xóa")
        delete.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        delete.setStyleSheet("QPushButton { padding: 4px 12px; font-size: 11px; font-weight: 600; background: transparent; border: 1px solid #ef4444; color: #f87171; border-radius: 4px; } QPushButton:hover { background: #7f1d1d; color: white; }")
        
        edit.clicked.connect(lambda _, a=account: self._edit_grok_account(a))
        delete.clicked.connect(lambda _, a=account: self._delete_grok_account(a))
        
        layout.addWidget(edit)
        layout.addWidget(delete)
        self.grok_accounts_table.setCellWidget(row, 3, box)

    def _filter_grok_accounts(self, text):
        needle = str(text or "").lower()
        for row, account in enumerate(self.grok_accounts):
            self.grok_accounts_table.setRowHidden(row, needle not in account.email.lower())

    def _add_grok_account(self):
        log.info(f"[LOGIN_BUTTON_CLICK] [{datetime.now().isoformat()}] User clicked add_grok_btn (Grok account setup)")
        if self.grok_proc is not None:
            # User clicked "Đã đăng nhập xong"
            log.info(f"[LOGIN_VERIFIED] [{datetime.now().isoformat()}] User clicked 'Đăng nhập xong' (Grok) button manually.")
            proc = self.grok_proc
            self.grok_proc = None
            
            # Kill Chrome process tree to release the lock
            import subprocess
            try:
                log.info(f"[BROWSER_CLOSE_START] [{datetime.now().isoformat()}] Force killing Chrome process tree (PID={proc.pid}) to release sqlite database lock...")
                kill_res = subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, text=True)
                log.info(f"[BROWSER_CLOSE_DONE] [{datetime.now().isoformat()}] Taskkill result: stdout={kill_res.stdout.strip()}, stderr={kill_res.stderr.strip()}")
            except Exception as kill_err:
                log.warning(f"[BROWSER_CLOSE_ERROR] Failed taskkill, trying terminate: {kill_err}")
                try: proc.terminate()
                except: pass
                
            # Start sync
            self.add_grok_btn.setText("Đang đồng bộ...")
            self.add_grok_btn.setEnabled(False)
            self._monitor_grok_login(None, self.temp_grok_profile_path, is_edit=False)
            return

        chrome = find_chrome()
        if not chrome:
            QMessageBox.warning(self, "Không tìm thấy Chrome", "Đăng nhập Grok cần Chrome.")
            return
            
        import time
        profile_path = BROWSER_PROFILE_DIR / f"grok_temp_{int(time.time())}"
        profile_path.mkdir(parents=True, exist_ok=True)
        self.temp_grok_profile_path = profile_path
        
        import subprocess
        try:
            log.info(f"[LOGIN_START] [{datetime.now().isoformat()}] Grok Login: Launching Chrome native...")
            port = self._find_free_port()
            proc = subprocess.Popen([
                chrome,
                f"--user-data-dir={profile_path}",
                f"--remote-debugging-port={port}",
                "--no-first-run",
                "--disable-gpu",
                "--no-sandbox",
                "--no-default-browser-check",
                "--disable-features=LockProfileCookieDatabase",
                "https://grok.com/imagine"
            ])
            self.grok_proc = proc
            log.info(f"[LOGIN_WINDOW_OPEN] [{datetime.now().isoformat()}] Chrome browser opened successfully for Grok. PID={proc.pid}")
            
            # Start background monitor to close automatically if they succeed without clicking
            self._start_chrome_monitor(proc, profile_path, "sso", port)
            
            self.add_grok_btn.setText("Đăng nhập xong (Click vào đây)")
            self.add_grok_btn.setStyleSheet("QPushButton { padding: 6px 16px; font-weight: bold; background: #10b981; border: 1px solid #059669; color: white; border-radius: 6px; } QPushButton:hover { background: #059669; }")
            
            def wait_task():
                log.info(f"[wait_task] [{datetime.now().isoformat()}] Waiting for Grok Chrome process to exit...")
                proc.wait()
                log.info(f"[wait_task] [{datetime.now().isoformat()}] Grok Chrome process exited. ExitCode={proc.returncode}")
                if self.grok_proc == proc: # If not already handled by click
                    log.info(f"[LOGIN_VERIFIED] [{datetime.now().isoformat()}] Chrome browser closed by user. Triggering Grok sync process.")
                    self.grok_proc = None
                    self.grok_login_status_changed.emit("Đang đồng bộ...", True)
                    self._monitor_grok_login(None, profile_path, is_edit=False)
                
            threading.Thread(target=wait_task, daemon=True).start()
            
        except Exception as e:
            log.error(f"[LOGIN_FAILED] [{datetime.now().isoformat()}] Failed to launch Grok Chrome: {e}")
            self.grok_proc = None
            self.add_grok_btn.setText("Thêm tài khoản Grok")
            self.add_grok_btn.setEnabled(True)
            self.add_grok_btn.setStyleSheet("")
            QMessageBox.warning(self, "Lỗi", f"Không thể mở trình duyệt: {e}")

    def _edit_grok_account(self, account):
        chrome = find_chrome()
        if not chrome:
            QMessageBox.warning(self, "Không tìm thấy Chrome", "Đăng nhập Grok cần Chrome.")
            return
        profile_path = account.cookie_path
        if not profile_path:
            QMessageBox.warning(self, "Lỗi", "Tài khoản này chưa có profile.")
            return
            
        if account.id in self.edit_procs:
            proc = self.edit_procs[account.id]
            del self.edit_procs[account.id]
            
            # Kill Chrome process tree to release the lock
            import subprocess
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            except:
                try: proc.terminate()
                except: pass
                
            self.grok_login_status_changed.emit("Đang đồng bộ...", True)
            self._monitor_grok_login(account.email, Path(profile_path), is_edit=True)
            return
            
        import subprocess
        try:
            self._delete_profile_session_cookie(profile_path, "sso")
            port = self._find_free_port()
            proc = subprocess.Popen([
                chrome,
                f"--user-data-dir={profile_path}",
                f"--remote-debugging-port={port}",
                "--no-first-run",
                "--disable-gpu",
                "--no-sandbox",
                "--no-default-browser-check",
                "--disable-features=LockProfileCookieDatabase",
                "https://grok.com/imagine"
            ])
            self.edit_procs[account.id] = proc
            
            # Start background monitor to close automatically if they succeed without clicking
            self._start_chrome_monitor(proc, profile_path, "sso", port)
            
            sender = self.sender()
            if sender and isinstance(sender, QPushButton):
                sender.setText("Đồng bộ")
                sender.setStyleSheet("QPushButton { padding: 4px 12px; font-size: 11px; font-weight: bold; background: #10b981; border: 1px solid #059669; color: white; border-radius: 4px; } QPushButton:hover { background: #059669; }")
            
            def wait_task():
                proc.wait()
                if account.id in self.edit_procs:
                    del self.edit_procs[account.id]
                    self.grok_login_status_changed.emit("Đang đồng bộ...", True)
                    self._monitor_grok_login(account.email, Path(profile_path), is_edit=True)
                
            threading.Thread(target=wait_task, daemon=True).start()
            
        except Exception as e:
            if account.id in self.edit_procs:
                del self.edit_procs[account.id]
            self.grok_login_status_changed.emit("Thêm tài khoản Grok", False)
            QMessageBox.warning(self, "Lỗi", f"Không thể mở trình duyệt: {e}")

    def _delete_grok_account(self, account):
        reply = QMessageBox.question(self, "Xác nhận", f"Bạn có chắc muốn xóa tài khoản Grok {account.email}?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_account(account.id)
                if account.cookie_path and os.path.exists(account.cookie_path):
                    shutil.rmtree(account.cookie_path, ignore_errors=True)
            except Exception as e:
                log.error(f"Error deleting grok account: {e}")
            self._load_grok_accounts()

    def _monitor_grok_login(self, email, profile_path, is_edit=False):
        thread = threading.Thread(target=lambda: self._sync_account_from_profile(
            profile_path, "grok", email_hint=email, is_edit=is_edit), daemon=True)
        thread.start()

    async def _async_grok_login(self, email_input, profile_path, is_edit=False):
        import sys
        import tempfile
        import os
        from datetime import datetime
        
        # Diagnostic variables
        meipass = getattr(sys, "_MEIPASS", "Not in Packaged Mode")
        cwd = os.getcwd()
        temp_dir = tempfile.gettempdir()
        
        log.info(f"[LOGIN_START] [{datetime.now().isoformat()}] Grok Playwright Login init. is_edit={is_edit}")
        log.info(f"[LOGIN_START] MEIPASS: {meipass}")
        log.info(f"[LOGIN_START] CWD: {cwd}")
        log.info(f"[LOGIN_START] Temp Dir: {temp_dir}")
        log.info(f"[LOGIN_START] Target Profile Path: {profile_path}")
        
        from playwright.async_api import async_playwright
        chrome_exe = find_chrome()
        log.info(f"[LOGIN_START] Resolved Chrome Executable Path: {chrome_exe}")
        
        browser = None
        detected_email = email_input
        detected_tier = "Grok"
        
        try:
            self.grok_login_status_changed.emit("Đang khởi động Chrome...", True)
            log.info(f"[LOGIN_START] [{datetime.now().isoformat()}] Launching Playwright persistent context for Grok...")
            
            async with async_playwright() as p:
                log.info(f"[LOGIN_START] Playwright context initialized. Launching chromium...")
                for attempt in range(5):
                    try:
                        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                        browser = await p.chromium.launch_persistent_context(
                            user_data_dir=str(profile_path),
                            headless=False,
                            executable_path=chrome_exe,
                            args=STEALTH_CHROME_ARGS,
                            ignore_default_args=["--enable-automation", "--no-sandbox"],
                            user_agent=user_agent,
                        )
                        log.info(f"[LOGIN_START] launch_persistent_context success on attempt {attempt+1}")
                        break
                    except Exception as launch_err:
                        log.warning(f"[LOGIN_START] Launch attempt {attempt+1} failed: {launch_err}")
                        if attempt == 4: raise launch_err
                        await asyncio.sleep(1)
                
                log.info(f"[LOGIN_START] Applying stealth scripts to context...")
                await apply_stealth_to_context(browser)
                
                page = browser.pages[0] if browser.pages else await browser.new_page()
                self.grok_login_status_changed.emit("Đang chờ đăng nhập...", True)
                
                log.info(f"[LOGIN_START] Navigating to Grok Imagine...")
                await page.goto("https://grok.com/imagine", wait_until="commit")
                
                async def on_response(response):
                    nonlocal detected_email
                    if detected_email:
                        return
                    try:
                        if "application/json" in response.headers.get("content-type", ""):
                            data = await response.json()
                            found = find_email_in_obj(data)
                            if found:
                                detected_email = found
                                log.info(f"[LOGIN_SUCCESS] [{datetime.now().isoformat()}] Detected email={detected_email} via on_response event.")
                    except Exception as resp_err:
                        log.debug(f"Response evaluation debug: {resp_err}")
                
                page.on("response", on_response)
                
                log.info(f"[LOGIN_START] Page loaded. Starting credential monitoring loop (180 iterations)...")
                for i in range(180):
                    if page.is_closed():
                        log.info(f"[LOGIN_START] Page was closed by user.")
                        break
                    if not detected_email:
                        detected_email = await detect_email_from_page(page)
                        if detected_email:
                            log.info(f"[LOGIN_SUCCESS] [{datetime.now().isoformat()}] Detected email={detected_email} via detect_email_from_page at iteration {i}")
                    if detected_email:
                        break
                    await asyncio.sleep(2)
                
                if detected_email and not page.is_closed():
                    try:
                        log.info(f"[LOGIN_SUCCESS] Navigating to grok.com for tier detection...")
                        await page.goto("https://grok.com/", wait_until="commit")
                        await asyncio.sleep(4)
                        detected_tier = await detect_grok_tier_from_page(page)
                        log.info(f"[LOGIN_SUCCESS] Grok tier detected: {detected_tier}")
                    except Exception as tier_err:
                        log.warning(f"[LOGIN_SUCCESS] Could not check tier: {tier_err}")
                
                # Verify storage state save (H1)
                log.info(f"[SESSION_SAVE_START] [{datetime.now().isoformat()}] Explicitly saving storage state...")
                try:
                    storage_state_path = Path(profile_path) / "storage_state.json"
                    await browser.storage_state(path=str(storage_state_path))
                    log.info(f"[SESSION_SAVE_DONE] [{datetime.now().isoformat()}] storage_state.json saved to {storage_state_path}")
                except Exception as save_err:
                    log.error(f"[SESSION_SAVE_ERROR] [{datetime.now().isoformat()}] Failed to save storage state: {save_err}")
                
                log.info(f"[BROWSER_CLOSE_START] [{datetime.now().isoformat()}] Closing Playwright browser context...")
                await browser.close()
                log.info(f"[BROWSER_CLOSE_DONE] [{datetime.now().isoformat()}] Browser context closed.")
                browser = None
                
                log.info(f"[PLAYWRIGHT_STOP] [{datetime.now().isoformat()}] Playwright async block ending.")
                
                from PySide6.QtCore import QMetaObject, Qt, Q_ARG
                if detected_email:
                    log.info(f"[ACCOUNT_UPDATE_START] [{datetime.now().isoformat()}] Invoking _on_grok_login_success slot...")
                    QMetaObject.invokeMethod(self, "_on_grok_login_success", Qt.QueuedConnection,
                        Q_ARG(str, detected_email), Q_ARG(str, str(profile_path)), Q_ARG(str, detected_tier))
                else:
                    log.warning(f"[LOGIN_FAILED] [{datetime.now().isoformat()}] Login timed out or no email.")
                    QMetaObject.invokeMethod(self, "_on_grok_login_failed", Qt.QueuedConnection,
                        Q_ARG(str, "Không phát hiện thấy email tài khoản đăng nhập hoặc bạn đã đóng trình duyệt."))
                    if not is_edit:
                        try:
                            import shutil
                            shutil.rmtree(profile_path, ignore_errors=True)
                        except:
                            pass
        except Exception as e:
            log.error(f"[LOGIN_EXCEPTION] [{datetime.now().isoformat()}] Playwright loop exception: {e}", exc_info=True)
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(self, "_on_grok_login_failed", Qt.QueuedConnection, Q_ARG(str, f"Lỗi Grok login: {e}"))
        finally:
            self.grok_login_status_changed.emit("Thêm tài khoản Grok", False)
            if browser:
                try:
                    log.info(f"[BROWSER_CLOSE_START] [{datetime.now().isoformat()}] Finally block closing browser context...")
                    await browser.close()
                    log.info(f"[BROWSER_CLOSE_DONE] [{datetime.now().isoformat()}] Finally block context closed.")
                except Exception as final_err:
                    log.error(f"[BROWSER_CLOSE_ERROR] Finally block context close exception: {final_err}")

    def _make_grok_tier_widget(self, account):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        tier_str = str(account.tier)
        if "Super" in tier_str:
            display = "Super Grok"
            color = "#f59e0b"  # amber
        elif "Heavy" in tier_str:
            display = "Heavy Grok"
            color = "#a78bfa"  # purple
        else:
            display = "Grok"
            color = "#94a3b8"  # gray
            
        label = QLabel(display)
        label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")
        
        sync_btn = QPushButton("Đồng bộ")
        sync_btn.setToolTip("Đồng bộ loại tài khoản (Super Grok/Heavy Grok/Grok) từ grok.com")
        sync_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        sync_btn.setStyleSheet("QPushButton { color: #3b82f6; font-size: 11px; font-weight: bold; background: transparent; border: 1px solid #3b82f6; border-radius: 4px; padding: 3px 8px; } QPushButton:hover { background: #1e3a8a; color: white; }")
        
        def _on_sync_clicked():
            sync_btn.setEnabled(False)
            sync_btn.setStyleSheet("QPushButton { color: #f59e0b; font-size: 11px; font-weight: bold; background: transparent; border: 1px solid #f59e0b; border-radius: 4px; padding: 3px 8px; }")
            
            from PySide6.QtCore import QTimer
            timer = QTimer(sync_btn)
            frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            timer.frame = 0
            def animate():
                sync_btn.setText(f"{frames[timer.frame]} Đang đồng bộ...")
                timer.frame = (timer.frame + 1) % len(frames)
                
            timer.timeout.connect(animate)
            timer.start(100)
            sync_btn._anim_timer = timer
            
            self._sync_grok_account_tier(account, sync_btn)
            
        sync_btn.clicked.connect(_on_sync_clicked)
        
        layout.addStretch()
        layout.addWidget(label)
        layout.addWidget(sync_btn)
        layout.addStretch()
        return box

    def _sync_grok_account_tier(self, account, btn):
        if btn is not None:
            self._manual_sync_accounts.add(account.id)
        async def _run_sync():
            import subprocess
            import socket
            from playwright.async_api import async_playwright
            from utils.platform import find_chrome
            
            cookie_path = account.cookie_path
            chrome = find_chrome()
            if not chrome:
                return "Không tìm thấy Chrome"
                
            # Wait 1.5 seconds initially to allow previous browser to fully release profile locks
            await asyncio.sleep(1.5)
            
            # Find a free port
            s = socket.socket()
            s.bind(('', 0))
            port = s.getsockname()[1]
            s.close()
            
            # Launch native Chrome in headed mode offscreen to bypass Cloudflare Turnstile
            proc = subprocess.Popen([
                chrome,
                f"--user-data-dir={cookie_path}",
                f"--remote-debugging-port={port}",
                "--window-size=400,300",
                "--window-position=-3000,-3000",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-features=LockProfileCookieDatabase"
            ])
            
            browser = None
            try:
                async with async_playwright() as p:
                    # Connect over CDP
                    for attempt in range(15):
                        if proc.poll() is not None:
                            return "Chrome exited prematurely"
                        try:
                            browser = await p.chromium.connect_over_cdp(f"http://localhost:{port}")
                            break
                        except:
                            await asyncio.sleep(0.5)
                    
                    if not browser:
                        return "Failed to connect over CDP"
                        
                    contexts = browser.contexts
                    if contexts:
                        page = contexts[0].pages[0] if contexts[0].pages else await contexts[0].new_page()
                        await page.goto('https://grok.com/', wait_until='domcontentloaded')
                        await asyncio.sleep(5)
                        tier = await detect_grok_tier_from_page(page)
                        return tier
                    return "No browser contexts"
            except Exception as e:
                return str(e)
            finally:
                if browser:
                    try: await browser.close()
                    except: pass
                # Clean shutdown of Chrome process
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                except:
                    try: proc.terminate()
                    except Exception: pass
                    
        def worker():
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            try:
                tier = asyncio.run(_run_sync())
            except Exception as e:
                tier = str(e)
                
            if tier in ('Super Grok', 'Heavy Grok', 'Grok'):
                QMetaObject.invokeMethod(self, '_on_grok_sync_success', Qt.QueuedConnection, Q_ARG(int, account.id), Q_ARG(str, tier))
            else:
                QMetaObject.invokeMethod(self, '_on_grok_sync_failed', Qt.QueuedConnection, Q_ARG(int, account.id), Q_ARG(str, tier))
                
        threading.Thread(target=worker, daemon=True).start()

    @Slot(int, str)
    def _on_grok_sync_success(self, account_id: int, tier: str):
        try:
            account = self.db.get_account(account_id)
            if account:
                account.tier = tier
                self.db.update_account(account)
            self._load_grok_accounts()
            if account_id in self._manual_sync_accounts:
                self._manual_sync_accounts.discard(account_id)
                QMessageBox.information(self, "Thành công", f"Đã đồng bộ loại tài khoản Grok: {tier}")
        except Exception as e:
            log.error(f"Lỗi cập nhật tier Grok: {e}")

    @Slot(int, str)
    def _on_grok_sync_failed(self, account_id: int, error: str):
        self._load_grok_accounts()
        if account_id in self._manual_sync_accounts:
            self._manual_sync_accounts.discard(account_id)
            QMessageBox.warning(self, "Lỗi đồng bộ", f"Đồng bộ thất bại.\nChi tiết lỗi: {error}")

    @Slot(str, str, str)
    def _on_grok_login_success(self, email, cookie_path, tier="Grok"):
        log.info(f"[ACCOUNT_SAVE_START] [{datetime.now().isoformat()}] Grok DB Save started for email={email}")
        import shutil
        cookie_path = Path(cookie_path)
        final_path = cookie_path
        
        if "grok_temp" in cookie_path.name:
            safe_email = "".join([c if c.isalnum() else "_" for c in email])
            final_path = BROWSER_PROFILE_DIR / f"grok_{safe_email}"
            
            if final_path.exists():
                try:
                    shutil.rmtree(final_path, ignore_errors=True)
                except Exception as e:
                    log.warning(f"Could not remove existing profile: {e}")
            
            try:
                shutil.move(str(cookie_path), str(final_path))
            except Exception as e:
                log.error(f"Could not rename profile directory: {e}")
                final_path = cookie_path
                
        account = None
        for existing in self.db.get_accounts(account_type="grok"):
            if existing.email == email:
                account = existing
                break
        is_new = False
        if account is None:
            account = self.db.add_account(email, account_type="grok")
            is_new = True
            
        account.cookie_path = str(final_path)
        
        # Preserve Super/Heavy Grok tier if already set, unless the new tier is explicitly a higher tier
        if not is_new and account.tier in ("Super Grok", "Heavy Grok") and tier == "Grok":
            log.info(f"[sync] Preserving existing tier '{account.tier}' for Grok account {email} (new tier hint was 'Grok')")
        else:
            account.tier = tier
            
        self.db.update_account(account)
        log.info(f"[ACCOUNT_SAVE_DONE] [{datetime.now().isoformat()}] Grok account successfully updated in Database. ID={account.id}, Email={account.email}, Tier={account.tier}")
        self._load_grok_accounts()
        
        # Only trigger background tier sync if tier was not already detected by CDP monitor
        if tier == "Grok":
            log.info(f"[sync] Tier not yet detected, triggering background sync for Grok account {email}")
            self._sync_grok_account_tier(account, None)
        else:
            log.info(f"[sync] Tier already detected as '{tier}' via CDP, skipping background sync")
        
        log.info(f"[FINAL_STATE] [{datetime.now().isoformat()}] Grok login UI update complete. Success.")
        QMetaObject.invokeMethod(self.parent(), "_refresh_account_headers", Qt.QueuedConnection)
        QMessageBox.information(self, "Đã lưu đăng nhập", f"Đã lưu tài khoản Grok: {email}\nLoại tài khoản: {account.tier}")

    @Slot(str)
    def _on_grok_login_failed(self, message):
        QMessageBox.warning(self, "Lỗi đăng nhập Grok", str(message))



class HealthCheckDialog(QDialog):
    def __init__(self, parent=None, account=None):
        super().__init__(parent)
        self.setWindowTitle('Health Check: ' + (account.email if account else ''))
        self.resize(500, 400)
        self.layout = QVBoxLayout(self)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        
        self.layout.addWidget(self.log_view)
        
        btn_layout = QHBoxLayout()
        self.btn_fix = QPushButton("Mở trình duyệt để Đăng nhập / Cấp quyền Video FX")
        self.btn_fix.setStyleSheet("background-color: #3b82f6; color: white; padding: 5px 15px; font-weight: bold; border-radius: 4px;")
        self.btn_fix.clicked.connect(lambda: [self.accept(), parent._edit_account(account)] if parent and hasattr(parent, '_edit_account') else None)
        
        self.btn_close = QPushButton("Đóng")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_fix)
        btn_layout.addWidget(self.btn_close)
        self.layout.addLayout(btn_layout)
        
    @Slot(str, str)
    def add_step(self, step_name, status):
        color = '#10b981' if 'PASS' in status else ('#ef4444' if 'FAIL' in status else '#f59e0b')
        self.log_view.append(f'<span style="color: {color};">[{status}]</span> {step_name}')