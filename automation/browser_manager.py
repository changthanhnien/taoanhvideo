"""VidGen AI — Browser manager using real Chrome headless + CDP.

Strategy:
  - Login: Chrome subprocess (visible) → user logs in → closes Chrome
  - Generate/Renew: Chrome subprocess (headless) + Playwright connects via CDP
  - Same Chrome binary + same profile = cookies work
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from config.constants import BROWSER_PROFILE_DIR
from utils.logger import log
from utils.platform import (
    find_chrome,
    get_subprocess_flags,
    hide_chromium_taskbar_icons,
    hide_window,
    kill_process_on_port,
    kill_process_tree,
)


class BrowserManager:
    """Manages Chrome headless processes + Playwright CDP connections."""

    GOOGLE_FLOW_URL = "https://labs.google/fx/tools/video-fx"
    GOOGLE_IMAGE_URL = "https://labs.google/fx/tools/image-fx"

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(BrowserManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._playwright = None
        self._playwrights = {}
        self._browsers = {}
        self._chrome_procs = {}
        self._pages = {}
        self._ref_counts = {}
        self._ports = {}
        self._profiles = {}
        self._next_port = 9222
        self._loop_locks = {}

    def _get_loop_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
        if loop_id not in self._loop_locks:
            self._loop_locks[loop_id] = asyncio.Lock()
        return self._loop_locks[loop_id]

    async def _ensure_playwright(self):
        if not self._playwright:
            log.info("Starting Playwright (CDP mode)...")
            self._playwright = await async_playwright().start()

    async def stop(self):
        """Close all browser connections and Chrome processes."""
        for account_id in list(self._browsers.keys()):
            self._ref_counts[account_id] = 1
            await self.close_context(account_id)
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        log.info("Browser manager stopped")

    def _get_port(self, account_id: int) -> int:
        """Get a unique debugging port for an account."""
        if account_id not in self._ports:
            self._ports[account_id] = self._next_port
            self._next_port += 1
        return self._ports[account_id]

    async def get_or_create_context(
        self,
        account_id: int,
        email: str,
        proxy: Optional[str] = None,
        cookie_path: Optional[str] = None,
    ) -> BrowserContext:
        """Launch Playwright Chromium with cookies from Chrome login profile."""
        async with self._get_loop_lock():
            self._ref_counts[account_id] = self._ref_counts.get(account_id, 0) + 1
            self._ensure_taskbar_sweeper()

            if account_id in self._browsers:
                b = self._browsers[account_id]
                if hasattr(b, "contexts"): # It's a Browser
                    contexts = b.contexts
                    if contexts:
                        return contexts[0]
                else:
                    return b # It's already a BrowserContext

            if account_id not in self._playwrights:
                log.info(f"Starting Playwright for account {account_id}...")
                self._playwrights[account_id] = await async_playwright().start()

            import json as _json

            has_persistent_profile = False
            if cookie_path and Path(cookie_path).exists():
                if (Path(cookie_path) / "Default").exists() or (Path(cookie_path) / "Local State").exists():
                    has_persistent_profile = True
                    
            cookies = []
            if not has_persistent_profile and cookie_path and Path(cookie_path).exists():
                cookies_file = Path(cookie_path) / "cookies_export.json"
                if cookies_file.exists():
                    try:
                        with open(cookies_file, "r", encoding="utf-8") as f:
                            cookies = _json.load(f)
                        log.info(f"Loaded {len(cookies)} cookies from {cookies_file}")
                    except Exception as e:
                        log.warning(f"Failed to load cookies: {e}")

            if not has_persistent_profile and not cookies:
                raise RuntimeError(f"No cookies for {email}. Please login/renew account first.")

            self._profiles[account_id] = cookie_path or ""
            
            # Prevent 'Opening in existing browser session' issue by force killing any orphan Chrome processes using this profile
            if cookie_path:
                try:
                    import psutil
                    abs_profile = os.path.abspath(cookie_path).lower()
                    for proc in psutil.process_iter(attrs=['pid', 'name', 'cmdline']):
                        try:
                            if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                                cmdline = proc.info['cmdline']
                                if cmdline and any(abs_profile in str(arg).lower() for arg in cmdline):
                                    log.info(f"BrowserManager: Killing orphan Chrome process {proc.info['pid']} using profile: {cookie_path}")
                                    proc.kill()
                        except Exception:
                            pass
                except Exception as pe:
                    log.warning(f"BrowserManager: Failed to check/kill orphan processes: {pe}")
                
                # Delete SingletonLock to avoid Chrome profile lock errors
                lock_file = os.path.join(cookie_path, "SingletonLock")
                if os.path.exists(lock_file):
                    try:
                        os.remove(lock_file)
                        log.info(f"BrowserManager: Removed SingletonLock file for {cookie_path}")
                    except Exception as le:
                        log.warning(f"BrowserManager: Failed to remove SingletonLock: {le}")

            pw = self._playwrights[account_id]

            log.info(f"Launching Chromium for {email}...")
            chrome_exe = find_chrome()
            if chrome_exe:
                log.info(f"Using system Chrome: {chrome_exe}")
            else:
                log.info("System Chrome not found, fallback to bundled chromium")

            args = [
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
                "--no-first-run",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-field-trial-config",
                "--password-store=basic",
                "--use-mock-keychain",
            ]

            # Stealth script: hide CDP/automation artifacts that Cloudflare Turnstile detects.
            # Comprehensive approach targeting Turnstile 2025+ detection vectors.
            _STEALTH_JS = """
            // === 1. navigator.webdriver ===
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
                configurable: true
            });
            // Also delete it from Navigator.prototype
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
                // Continuously clean (Playwright may re-inject)
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
                                        get: () => undefined,
                                        configurable: true
                                    });
                                } catch(e) {}
                            }
                            return win;
                        }
                    });
                }
            } catch(e) {}

            // === 6. navigator.plugins (CDP returns empty) ===
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

            // === 8. Mask Error.stack sourceURL (Playwright uses __playwright_evaluation_script__) ===
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

            // === 9. Prevent detection via toString() on patched functions ===
            const origToString = Function.prototype.toString;
            const nativeToString = function() {
                if (this === navigator.permissions.query) return 'function query() { [native code] }';
                return origToString.call(this);
            };
            Function.prototype.toString = nativeToString;
            // Self-protect toString
            try {
                Object.defineProperty(Function.prototype, 'toString', {
                    value: nativeToString, writable: false, configurable: false
                });
            } catch(e) {}
            """

            if has_persistent_profile:
                log.info(f"Using persistent profile at {cookie_path}")
                port = self._get_port(account_id)
                import subprocess
                chrome_args = [
                    chrome_exe,
                    f"--user-data-dir={cookie_path}",
                    f"--remote-debugging-port={port}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-sync",
                    "--disable-signin-promo",
                    "--disable-features=BackgroundMode",
                    "--password-store=basic",
                    "--window-size=1024,768",
                    "--disable-blink-features=AutomationControlled",
                ]
                proc = subprocess.Popen(chrome_args)
                self._chrome_procs[account_id] = proc
                
                await asyncio.sleep(2.0)
                browser = await pw.chromium.connect_over_cdp(f"http://localhost:{port}")
                self._browsers[account_id] = browser
                context = browser.contexts[0]
            else:
                browser = await pw.chromium.launch(
                    headless=False,
                    executable_path=chrome_exe,
                    args=args,
                    ignore_default_args=["--enable-automation", "--no-sandbox"],
                )
                self._browsers[account_id] = browser
                context = await browser.new_context()
                if cookies:
                    await context.add_cookies(cookies)
                    log.info(f"Chromium ready for {email} ({len(cookies)} cookies injected)")

            # Inject stealth patches into every page (current + future)
            await context.add_init_script(_STEALTH_JS)

            # Abort local network requests to prevent Cloudflare Turnstile debugging port scan
            async def _handle_route(route):
                url = route.request.url
                if any(h in url for h in ["127.0.0.1", "localhost", "::1"]):
                    await route.abort()
                else:
                    await route.continue_()
            await context.route("**/*", _handle_route)

        self._ensure_taskbar_sweeper()
        return context

    def _ensure_taskbar_sweeper(self):
        """Start the background taskbar sweeper if it's not running.

        Each worker QThread has its OWN asyncio event loop. A sweeper
        task created in worker 1's loop dies when that loop shuts down
        — the next worker must therefore start a fresh sweeper in its
        own loop. We key sweepers by event-loop id so multiple workers
        can have their own sweeper concurrently without stomping each
        other.
        """
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            log.debug("_ensure_taskbar_sweeper called outside event loop")
            return None

        if not hasattr(self, "_taskbar_sweepers"):
            self._taskbar_sweepers = {}

        loop_id = id(current_loop)
        existing = self._taskbar_sweepers.get(loop_id)
        if existing is not None and not existing.done():
            return None

        try:
            task = current_loop.create_task(self._taskbar_sweep_loop())
            self._taskbar_sweepers[loop_id] = task
            log.debug(f"Taskbar sweeper started for loop {loop_id}")
        except Exception as e:
            log.warning(f"Could not start taskbar sweeper: {e}")
        return None

    async def _taskbar_sweep_loop(self):
        """Continuously strip taskbar buttons from our Chromium windows.

        Fast cadence for the first 10 seconds after the first browser
        comes up (catches delayed window creation + renderer/profile
        popups), then slows to 2s intervals. Exits cleanly once every
        browser we tracked is gone.
        """
        loop = asyncio.get_running_loop()
        fast_sweeps_left = 20
        idle_sweeps = 0

        while True:
            try:
                await loop.run_in_executor(None, hide_chromium_taskbar_icons)
            except RuntimeError as e:
                if "after shutdown" in str(e):
                    log.debug("Taskbar sweeper: event loop shutting down, exit")
                    return None
                log.debug(f"Taskbar sweep failed: {e}")
            except Exception as e:
                log.debug(f"Taskbar sweep failed: {e}")

            if not self._browsers:
                idle_sweeps += 1
                if idle_sweeps >= 3:
                    log.debug("Taskbar sweeper: no more browsers, stopping")
                    return None
            else:
                idle_sweeps = 0

            if fast_sweeps_left > 0:
                fast_sweeps_left -= 1
                await asyncio.sleep(0.5)
            else:
                await asyncio.sleep(2)

    async def get_page(
        self,
        account_id: int,
        email: str,
        proxy: Optional[str] = None,
        url: str = None,
        cookie_path: Optional[str] = None,
    ) -> Page:
        """Get or create a page for an account, navigate to URL."""
        context = await self.get_or_create_context(account_id, email, proxy, cookie_path)
        need_new_page = False

        if account_id not in self._pages or self._pages[account_id].is_closed():
            need_new_page = True
        else:
            try:
                await self._pages[account_id].evaluate("1+1")
            except Exception:
                log.warning(f"Page stale for account_id={account_id}, reconnecting...")
                need_new_page = True
                if account_id in self._browsers:
                    try:
                        await self._browsers[account_id].close()
                    except Exception:
                        pass
                    del self._browsers[account_id]
                    del self._pages[account_id]
                    self._kill_chrome(account_id)
                    context = await self.get_or_create_context(account_id, email, proxy, cookie_path)

        if need_new_page:
            pages = context.pages
            if pages:
                page = pages[0]
            else:
                page = await context.new_page()
            self._pages[account_id] = page

        page = self._pages[account_id]
        if url:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return page

    async def close_context(self, account_id: int):
        """Close CDP connection and kill Chrome process.

        Uses ref counting: only actually closes when no more tasks
        are using this browser (ref count reaches 0).
        """
        self._ref_counts[account_id] = self._ref_counts.get(account_id, 1) - 1
        if self._ref_counts[account_id] > 0:
            log.info(
                f"Browser for account_id={account_id} still in use "
                f"({self._ref_counts[account_id]} tasks remaining), keeping alive"
            )
            return None

        self._ref_counts.pop(account_id, None)

        if account_id in self._pages:
            try:
                if not self._pages[account_id].is_closed():
                    await self._pages[account_id].close()
            except Exception:
                pass
            del self._pages[account_id]

        if account_id in self._browsers:
            try:
                await self._browsers[account_id].close()
            except Exception:
                pass
            del self._browsers[account_id]

        self._kill_chrome(account_id)

        # Force terminate any remaining chrome.exe process for this specific profile asynchronously in the background
        if account_id in self._profiles:
            cookie_path = self._profiles[account_id]
            if cookie_path:
                profile_basename = os.path.basename(cookie_path)
                async def run_killer():
                    try:
                        # 1. Try legacy wmic command
                        cmd_wmic = f'wmic process where "name=\'chrome.exe\' and CommandLine like \'%{profile_basename}%\'" call terminate'
                        proc = await asyncio.create_subprocess_shell(
                            cmd_wmic,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        await proc.communicate()
                    except Exception:
                        pass
                    try:
                        # 2. Try modern PowerShell fallback
                        cmd_ps = f'powershell -Command "Get-CimInstance Win32_Process -Filter \'Name = \\"chrome.exe\\"\' | Where-Object {{ $_.CommandLine -like \'*{profile_basename}*\' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"'
                        proc = await asyncio.create_subprocess_shell(
                            cmd_ps,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        await proc.communicate()
                    except Exception:
                        pass
                
                asyncio.create_task(run_killer())

        if account_id in self._profiles:
            prof = Path(self._profiles[account_id])
            for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
                lock_file = prof / lock_name
                if not lock_file.exists():
                    continue
                try:
                    lock_file.unlink()
                except Exception:
                    pass

        if account_id in self._playwrights:
            try:
                await self._playwrights[account_id].stop()
            except Exception:
                pass
            del self._playwrights[account_id]

        log.info(f"Closed browser for account_id={account_id}")
        return None

    def _kill_chrome(self, account_id: int):
        """Kill the Chrome process and free its port."""
        if account_id in self._chrome_procs:
            proc = self._chrome_procs.pop(account_id)
            if not kill_process_tree(proc.pid):
                try:
                    proc.kill()
                except Exception:
                    pass

        if account_id in self._ports:
            kill_process_on_port(self._ports[account_id])
        return None

    def is_context_open(self, account_id: int) -> bool:
        return account_id in self._browsers

    @property
    def active_count(self) -> int:
        return len(self._browsers)
