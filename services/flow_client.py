"""VidGen AI — Google Flow AI Sandbox API client.

Auth: Playwright headless → /fx/api/auth/session → ya29.* access_token
API:
  - Upload:   POST aisandbox-pa.googleapis.com/v1/flow/uploadImage
  - Generate: POST aisandbox-pa.googleapis.com/v1/video:batchAsyncGenerateVideo*
  - Poll:     POST aisandbox-pa.googleapis.com/v1/video:batchCheckAsyncVideoGenerationStatus
  - Download: tRPC media.getMediaUrlRedirect
  - Image:    POST aisandbox-pa.googleapis.com/v1:runImageFx
Flow: get_token → upload_images → generate → poll → download
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from config.constants import MAX_RETRY_COUNT, POLL_INTERVAL_SECONDS, DATA_DIR
from utils.logger import log

if TYPE_CHECKING:
    from playwright.async_api import Page


_BUNDLED_PW_DIR = Path(__file__).parent / "playwright"
AISANDBOX_BASE = "https://aisandbox-pa.googleapis.com/v1"
X_CLIENT_DATA = "CIa2yQEIprbJAQipncoBCLb9ygEIlqHLAQiFoM0BCNmqzwEY/qXPARikqM8BGMOrzwE="
X_BROWSER_VALIDATION = "AKIAtsVHZoiKbPixy+qSK1BgKWo="
_RECAPTCHA_LOCKS: dict[str, asyncio.Lock] = {}


def _get_recaptcha_lock(account_email):
    try:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
    except RuntimeError:
        loop_id = 0
    key = f"{loop_id}:{account_email or '?'}"
    lock = _RECAPTCHA_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _RECAPTCHA_LOCKS[key] = lock
    return lock


class FlowClient:
    TRPC = "https://labs.google/fx/api/trpc"
    SESSION_URL = "https://labs.google/fx/api/auth/session"
    _caption_cache: dict[str, str] = {}
    _IMAGE_MODEL_FALLBACK = {
        "Nano Banana 2": "IMAGEN_3_5",
        "Imagen 3.5": "IMAGEN_3_5",
        "Imagen 4": "IMAGEN_4",
        "Imagen 4 Ultra": "IMAGEN_4_ULTRA",
    }

    def __init__(self, page: "Page", cookie_path=None, account_email: str | None = None):
        self._page = page
        self._token = None
        self._session_id = str(uuid.uuid4())
        self._cookie_path = cookie_path
        self._account_email = account_email or "?"
        self._last_remaining_credits = None
        self._last_credit_cost = 0
        self._last_model_key = None
        self._recaptcha_provider = None
        self._recaptcha_fail_count = 0

    async def _clear_non_essential_state(self):
        try:
            # Clear localStorage, sessionStorage, and IndexedDB
            await self._page.evaluate("""() => {
                try {
                    localStorage.clear();
                    sessionStorage.clear();
                    if (window.indexedDB && window.indexedDB.databases) {
                        window.indexedDB.databases().then(dbs => {
                            dbs.forEach(db => {
                                try { window.indexedDB.deleteDatabase(db.name); } catch(e) {}
                            });
                        });
                    }
                } catch(e) {}
            }""")
            
            # Clear cookies only for labs.google domains to preserve Google auth session
            await self._page.context.clear_cookies(domain="labs.google")
            await self._page.context.clear_cookies(domain=".labs.google")
            log.info(f"[FlowClient] Cleaned site data and labs.google cookies for {self._account_email}")
        except Exception as e:
            log.warning(f"[FlowClient] Failed to pre-clean site data: {e}")

    async def ensure_token(self):
        """Get ya29.* access token from NextAuth session."""
        if self._token:
            return self._token

        log.info("Getting session token...")
        
        if "labs.google" not in (self._page.url or ""):
            await self._page.goto("https://labs.google/fx/vi/tools/flow", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

        # Auto-bypass Google Labs Welcome/Terms Modals
        try:
            for attempt in range(5):
                btn = await self._page.query_selector(
                    'button:has-text("Tiếp theo"), button:has-text("Next"), '
                    'button:has-text("Tiếp tục"), button:has-text("Continue"), '
                    'button:has-text("Đồng ý"), button:has-text("Agree"), '
                    'button:has-text("Tôi đồng ý"), button:has-text("I agree"), '
                    'button:has-text("Bắt đầu"), button:has-text("Get started"), '
                    'button:has-text("Đã hiểu"), button:has-text("Got it"), '
                    'button:has-text("Let\'s go")'
                )
                if btn and await btn.is_visible():
                    log.info(f"FlowClient: Bypassing welcome dialog step {attempt + 1}. Clicking button...")
                    await btn.click()
                    await asyncio.sleep(2)
                else:
                    break
        except Exception as e:
            log.warning(f"FlowClient: Welcome dialog bypass error: {e}")

        # Check for Google Flow application crash
        try:
            body_text = await self._page.inner_text("body")
            if "Oops, something went wrong!" in body_text or "something went wrong" in body_text.lower():
                log.warning("Detected Google Flow crash page. Clearing cookies and reloading...")
                await self._clear_non_essential_state()
                await self._page.goto("https://labs.google/fx/vi/tools/flow", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
        except Exception as e:
            log.warning(f"Error checking page crash: {e}")

        if "accounts.google.com" in (self._page.url or ""):
            raise RuntimeError("Phiên đăng nhập Google của tài khoản này đã hết hạn (exhausted). Vui lòng vào Cài đặt -> Quản lý tài khoản để Đăng nhập lại.")

        # CHECK TOKEN FIRST BEFORE CLICKING ANYTHING!
        result = await self._page.evaluate(
            """async (url) => {
                const r = await fetch(url, {credentials: "include"});
                if (!r.ok) return {error: r.status};
                return await r.json();
            }""",
            self.SESSION_URL,
        )
        token = (result or {}).get("accessToken") or (result or {}).get("access_token")
        
        # IF NO TOKEN, TRY CLICKING SIGN IN
        if not token:
            try:
                # Use a very short timeout, if it's not there we just fail
                btn = await self._page.query_selector(
                    'a[href*="accounts.google.com"], button:has-text("Sign in"), a:has-text("Sign in")'
                )
                if btn and await btn.is_visible(timeout=5000):
                    log.info("Clicking Sign in...")
                    async with self._page.context.expect_page() as pi:
                        await btn.click()
                    popup = await pi.value
                    await popup.wait_for_event("close", timeout=20000)
            except Exception:
                pass
                
            # TRY FETCHING AGAIN
            result = await self._page.evaluate(
                """async (url) => {
                    const r = await fetch(url, {credentials: "include"});
                    if (!r.ok) return {error: r.status};
                    return await r.json();
                }""",
                self.SESSION_URL,
            )
            token = (result or {}).get("accessToken") or (result or {}).get("access_token")

        if not token:
            err = json.dumps(result, ensure_ascii=False)[:500]
            log.error(f"Session token missing: {err}")
            raise RuntimeError("Could not get Google session access token (exhausted). Please check login state.")
            
        self._token = token
        return token

    def set_recaptcha_provider(self, provider):
        """Set external reCAPTCHA token provider (SubprocessTokenProvider)."""
        self._recaptcha_provider = provider

    async def renew_token(self):
        """Force refresh of the session token."""
        log.info("Renewing session token...")
        self._token = None
        token = await self.ensure_token()
        provider = self._recaptcha_provider
        if provider and getattr(provider, "is_running", lambda: False)():
            try:
                cookies = await self._page.context.cookies()
                provider.refresh_cookies(cookies)
            except Exception as e:
                log.warning(f"Failed to refresh provider cookies: {e}")
        return token

    async def get_recaptcha_token(self, action: str):
        lock = _get_recaptcha_lock(self._account_email)
        async with lock:
            provider = self._recaptcha_provider
            if provider:
                try:
                    token = await provider.get_token(action)
                    if token:
                        self._recaptcha_fail_count = 0
                        return token
                except Exception as e:
                    self._recaptcha_fail_count += 1
                    log.warning(f"reCAPTCHA provider failed: {e}")

            # Simulate human telemetry before executing reCAPTCHA
            try:
                log.info("Simulating human telemetry on page for reCAPTCHA...")
                await self._page.bring_to_front()
                await self._page.mouse.move(200, 200)
                await asyncio.sleep(0.1)
                await self._page.mouse.click(200, 200)
                await asyncio.sleep(0.2)
                for x, y in [(250, 220), (320, 280), (410, 230), (500, 350)]:
                    await self._page.mouse.move(x, y)
                    await asyncio.sleep(0.1)
                await self._page.evaluate("window.scrollBy(0, 50)")
                await asyncio.sleep(0.2)
                await self._page.evaluate("window.scrollBy(0, -50)")
                await asyncio.sleep(0.8)
            except Exception as sim_err:
                log.warning(f"Failed to simulate human telemetry: {sim_err}")

            result = await self._page.evaluate(
                """async (action) => {
                    if (typeof grecaptcha === 'undefined') return {error: "grecaptcha missing"};
                    
                    let siteKey = null;
                    const scripts = document.querySelectorAll('script[src*="recaptcha"]');
                    for (const s of scripts) {
                        const m = s.src.match(/[?&]render=([^&]+)/);
                        if (m) { siteKey = m[1]; break; }
                    }
                    if (!siteKey) {
                        const el = document.querySelector('.g-recaptcha');
                        if (el) siteKey = el.getAttribute('data-sitekey');
                    }
                    
                    let token = null;
                    if (grecaptcha.enterprise && typeof grecaptcha.enterprise.execute === 'function') {
                        token = await grecaptcha.enterprise.execute(siteKey || undefined, {action});
                    } else if (typeof grecaptcha.execute === 'function') {
                        token = await grecaptcha.execute(siteKey || undefined, {action});
                    } else {
                        return {error: "execute_function_missing"};
                    }
                    return {token};
                }""",
                action,
            )
            if isinstance(result, dict) and result.get("token"):
                self._recaptcha_fail_count = 0
                return result["token"]
            self._recaptcha_fail_count += 1
            raise RuntimeError(f"Could not get reCAPTCHA token for {action}: {result}")

    async def _api(self, procedure: str, payload=None, method: str = "POST"):
        # await self.ensure_token() # Not needed for UI automation
        import urllib.parse

        payload = payload or {}
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "x-client-data": X_CLIENT_DATA,
            "x-browser-validation": X_BROWSER_VALIDATION,
        }
        if method.upper() == "GET":
            url = f"{self.TRPC}/{procedure}?input={urllib.parse.quote(json.dumps(payload))}"
            resp = await self._page.request.get(url, headers=headers)
        else:
            resp = await self._page.request.post(f"{self.TRPC}/{procedure}", headers=headers, data=json.dumps(payload))
        if not resp.ok:
            text = await resp.text()
            raise RuntimeError(f"tRPC {procedure} failed HTTP {resp.status}: {text[:500]}")
        return await resp.json()

    def _extract(self, result):
        """Extract result.data.json.result from tRPC response."""
        return (((result or {}).get("result") or {}).get("data") or {}).get("json")

    async def _browser_sandbox_request(self, endpoint: str, payload: dict):
        await self.ensure_token()
        if endpoint.startswith(":"):
            url = f"{AISANDBOX_BASE}{endpoint}"
        else:
            url = f"{AISANDBOX_BASE}/{endpoint.lstrip('/')}"
        body_json = json.dumps(payload)
        for attempt in range(MAX_RETRY_COUNT):
            result = await self._page.evaluate(
                """async ({url, token, body}) => {
                    const r = await fetch(url, {
                        method: "POST",
                        headers: {"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                        body
                    });
                    const text = await r.text();
                    try { return {status: r.status, ok: r.ok, json: JSON.parse(text)}; }
                    catch(e) { return {status: r.status, ok: r.ok, text}; }
                }""",
                {"url": url, "token": self._token, "body": body_json},
            )
            if result.get("ok"):
                return result.get("json")
            if result.get("status") in (401, 403):
                await self.renew_token()
            await asyncio.sleep(1 + attempt)
        raise RuntimeError(f"Sandbox request failed: {result}")

    async def _sandbox_request(self, endpoint: str, payload=None, method: str = "POST", raw_body=None, content_type="application/json"):
        import httpx

        await self.ensure_token()
        url = f"{AISANDBOX_BASE}/{endpoint.lstrip('/')}"
        body = raw_body if raw_body is not None else json.dumps(payload or {}).encode()
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": content_type,
            "Origin": "https://labs.google",
            "Referer": "https://labs.google/",
            "x-client-data": X_CLIENT_DATA,
            "x-browser-validation": X_BROWSER_VALIDATION,
        }
        for attempt in range(MAX_RETRY_COUNT):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(url, content=body, headers=headers)
                if resp.status_code in (401, 403):
                    log.warning(f"Sandbox auth failed HTTP {resp.status_code}, renewing token")
                    await self.renew_token()
                    headers["Authorization"] = f"Bearer {self._token}"
                    await asyncio.sleep(1 + attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                log.error(f"Sandbox request error: {e}")
                if attempt == MAX_RETRY_COUNT - 1:
                    raise
                await asyncio.sleep(1 + attempt)

    async def _get_cookies_for_httpx(self):
        """Extract cookies from CDP browser for use with httpx requests."""
        try:
            all_cookies = await self._page.context.cookies()
            return {c.get("name"): c.get("value") for c in all_cookies if "google" in c.get("domain", "")}
        except Exception as e:
            log.warning(f"Failed to extract cookies: {e}")
            return {}

    async def _video_gen_httpx(self, url: str, payload: dict):
        import httpx

        token = self._token
        cookie_dict = await self._get_cookies_for_httpx()
        ua = await self._page.evaluate("() => navigator.userAgent")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Origin": "https://labs.google",
            "Referer": "https://labs.google/",
            "User-Agent": ua,
            "x-client-data": X_CLIENT_DATA,
            "x-browser-validation": X_BROWSER_VALIDATION,
        }
        async with httpx.AsyncClient(timeout=120, cookies=cookie_dict) as client:
            resp = await client.post(url, content=json.dumps(payload).encode(), headers=headers)
        if resp.status_code >= 400:
            log.error(f"Video gen HTTP {resp.status_code}: {resp.text[:500]}")
            raise RuntimeError(resp.text[:500])
        return resp.json()

    async def check_credits(self):
        """Check remaining video credits via aisandbox API."""
        await self.ensure_token()
        try:
            result = await self._page.evaluate(
                """async (token) => {
                    try {
                        const r = await fetch("https://aisandbox-pa.googleapis.com/v1/whisk:getVideoCreditStatus", {
                            method: "GET",
                            headers: {"Authorization": "Bearer " + token, "Origin": "https://labs.google", "Referer": "https://labs.google/"}
                        });
                        if (r.ok) return await r.json();
                        return {error: r.status};
                    } catch(e) { return {error: e.message}; }
                }""",
                self._token,
            )
            if result.get("error"):
                log.warning(f"Credit check failed: {json.dumps(result)[:300]}")
            else:
                log.info(f"Credits: {json.dumps(result, ensure_ascii=False)[:300]}")
            return result
        except Exception as e:
            log.error(f"Credit check error: {e}")
            return None

    async def get_video_models(self):
        """Fetch available video models from tRPC API."""
        result = await self._api("videoFx.getVideoModelConfig", {}, "GET")
        data = self._extract(result) or {}
        models = data.get("videoModelConfigs", [])
        log.info(f"VideoModelRegistry: {len(models)}")
        return models

    async def get_image_models(self):
        """Fetch available image models from tRPC API."""
        try:
            result = await self._api("imageFx.getImageModelConfig", {}, "GET")
            data = self._extract(result) or {}
            models = data.get("imageModelConfigs", [])
            log.info(f"ImageModelRegistry: {len(models)}")
            return models
        except Exception as e:
            log.warning(f"Failed to fetch image models from API: {e}")
            fallback = [{"displayName": "Nano Banana 2", "modelNameType": "IMAGEN_3_5"}]
            log.info(f"ImageModelRegistry: using {len(fallback)} fallback")
            return fallback

    def _map_image_model(self, display_name: str):
        """Map UI display name → API modelNameType enum value."""
        clean_name = display_name.replace("🍌", "").strip()
        dynamic = getattr(self, "_image_model_mapping", {})
        res = dynamic.get(display_name) or dynamic.get(clean_name) or self._IMAGE_MODEL_FALLBACK.get(clean_name) or self._IMAGE_MODEL_FALLBACK.get(display_name)
        return res or "IMAGEN_3_5"

    def _map_image_aspect_ratio(self, ratio: str) -> str:
        ratio_map = {
            "1:1": "IMAGE_ASPECT_RATIO_SQUARE",
            "9:16": "IMAGE_ASPECT_RATIO_PORTRAIT",
            "16:9": "IMAGE_ASPECT_RATIO_LANDSCAPE",
            "3:4": "IMAGE_ASPECT_RATIO_PORTRAIT_THREE_FOUR",
            "4:3": "IMAGE_ASPECT_RATIO_LANDSCAPE_FOUR_THREE"
        }
        import re
        m = re.search(r"(\d+:\d+)", ratio)
        clean_ratio = m.group(1) if m else ratio.strip()
        return ratio_map.get(clean_ratio, "IMAGE_ASPECT_RATIO_SQUARE")

    async def load_image_model_mapping(self):
        """Fetch image models from API and cache mapping."""
        models = await self.get_image_models()
        self._image_model_mapping = {}
        display_names = []
        for m in models:
            display = m.get("displayName")
            model_type = m.get("modelNameType")
            if display and model_type:
                self._image_model_mapping[display] = model_type
                display_names.append(display)
        log.info(f"Image model mapping loaded: {display_names}")
        return display_names

    async def upload_image(self, image_path, name: Optional[str] = None):
        await self.ensure_token()
        from PIL import Image
        import io

        image_path = Path(image_path)
        name = name or image_path.name
        with open(image_path, "rb") as f:
            raw = f.read()
        try:
            img = Image.open(io.BytesIO(raw))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((1536, 1536), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=92)
            raw = buf.getvalue()
        except Exception:
            pass
        image_b64 = base64.b64encode(raw).decode("ascii")
        payload = {"image": {"bytesBase64Encoded": image_b64, "mimeType": "image/jpeg"}, "name": name}
        log.info(f"Uploading image {name}: {len(raw)} bytes")
        result = await self._sandbox_request("flow/uploadImage", payload)
        self._last_upload_response = result
        return result.get("media") or result.get("name") or result

    async def _generate_video_whisk(self, prompt, image_paths=None, model="veo-3.1-fast", aspect_ratio="16:9", duration=8, project_name="", count=1, callback=None):
        import asyncio, base64, json
        from pathlib import Path
        import time as _time
        blob_info = None
        # await self.ensure_token()
        max_nav_retries = 3
        for nav_attempt in range(max_nav_retries):
            log.info(f"UI Auto: Navigating to Flow (attempt {nav_attempt + 1}/{max_nav_retries})...")
            try:
                await self._page.goto("https://labs.google/fx/vi/tools/flow", wait_until="load", timeout=60000)
                await asyncio.sleep(2)
            except Exception as e:
                log.warning(f"UI Auto: Navigation failed: {e}")
            try:
                if "about:blank" in self._page.url:
                    await self._page.goto(f"{AISANDBOX_BASE}/create", wait_until="load", timeout=60000)
            except Exception:
                pass
            
            try:
                for attempt in range(5):
                    btn = await self._page.query_selector(
                        'button:has-text("Tiếp theo"), button:has-text("Next"), '
                        'button:has-text("Tiếp tục"), button:has-text("Continue"), '
                        'button:has-text("Đồng ý"), button:has-text("Agree"), '
                        'button:has-text("Tôi đồng ý"), button:has-text("I agree"), '
                        'button:has-text("Bắt đầu"), button:has-text("Get started"), '
                        'button:has-text("Đã hiểu"), button:has-text("Got it"), '
                        'button:has-text("Let\'s go")'
                    )
                    if btn and await btn.is_visible():
                        log.info(f"UI Auto: Bypassing welcome dialog step {attempt + 1}. Clicking button...")
                        await btn.click()
                        await asyncio.sleep(2)
                    else:
                        break
            except Exception as e:
                log.warning(f"UI Auto: Welcome dialog bypass error: {e}")
            
            log.info("UI Auto: Looking for New Project button...")
            for _ in range(20):
                try:
                    new_btn = await self._page.query_selector('button:has-text("Dự án mới"), button:has-text("New project")')
                    if new_btn and await new_btn.is_visible():
                        await asyncio.sleep(2.0)
                        await new_btn.click()
                        try:
                            await self._page.wait_for_url("**/project/**", timeout=10000)
                            log.info("UI Auto: Successfully entered new project canvas.")
                            await asyncio.sleep(3.0)
                        except Exception:
                            log.warning("UI Auto: Did not detect /project/ URL")
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            
            current_url = self._page.url or ""
            if "about:blank" in current_url or self._page.is_closed():
                log.warning(f"UI Auto: Page crashed after clicking Dự án mới (url={current_url}), retrying...")
                if nav_attempt < max_nav_retries - 1:
                    await asyncio.sleep(2)
                    continue
                else:
                    raise RuntimeError("Trình duyệt bị crash liên tục khi truy cập Google Flow.")
            break
            
        try:

            # --- POPUP DISMISSAL ---
            # The UI might show a "Maps Imagery Grounding" or other onboarding popup for new accounts
            try:
                log.info("UI Auto: Checking for any onboarding popups...")
                
                # 1. Try to click specific dismiss buttons
                dismiss_btns = await self._page.query_selector_all('button:has-text("Bắt đầu"), button:has-text("Get started"), button:has-text("Got it"), button:has-text("Đã hiểu"), button:has-text("Tiếp tục"), button:has-text("Continue")')
                for btn in dismiss_btns:
                    if await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(0.5)
                        
                # 2. Press Escape a couple of times to close modals
                await self._page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                await self._page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                
                # 3. Click outside the modal in the dark overlay area (left edge, middle vertically)
                # This guarantees the modal closes if it requires clicking outside
                await self._page.mouse.click(10, 300)
                await asyncio.sleep(0.5)
                await self._page.mouse.click(10, 400)
                await asyncio.sleep(0.5)
                
            except Exception as e:
                log.warning(f"UI Auto: Error dismissing popups: {e}")
            # -----------------------

            if project_name:
                log.info(f"UI Auto: Renaming project to {project_name}...")
                try:
                    title_input = await self._page.query_selector('input[aria-label*="Rename"], input[aria-label*="Đổi tên"], input[aria-label*="Title"], input[aria-label*="Tiêu đề"], input[aria-label*="Project"], input[aria-label*="Dự án"]')
                    if not title_input:
                        buttons = await self._page.query_selector_all('[role="button"]')
                        for b in buttons:
                            if await b.is_visible():
                                text = await b.inner_text()
                                if text and ("202" in text or " AM" in text or " PM" in text or " SA" in text or " CH" in text or "Không có tiêu đề" in text or "Untitled" in text):
                                    await b.click()
                                    await asyncio.sleep(0.5)
                                    title_input = await self._page.query_selector('input')
                                    break
                    if title_input:
                        await title_input.click()
                        await self._page.keyboard.press("Control+a")
                        await self._page.keyboard.press("Backspace")
                        await self._page.keyboard.type(project_name, delay=20)
                        await self._page.keyboard.press("Enter")
                        await asyncio.sleep(1)
                except Exception as e:
                    log.warning(f"Failed to rename project: {e}")


            if image_paths and any(isinstance(p, str) and p.strip() for p in image_paths):
                log.info(f"UI Auto: Uploading reference image {image_paths[0]}...")
                try:
                    # Best method: use hidden file input directly
                    file_inputs = await self._page.query_selector_all('input[type="file"]')
                    if file_inputs:
                        await file_inputs[0].set_files(image_paths[0])
                        log.info("UI Auto: Uploaded image via hidden input.")
                        await asyncio.sleep(16.0)
                    else:
                        log.warning("UI Auto: No input[type='file'] found, trying UI click...")
                        # Fallback: Click the attachment button (usually a paperclip or image icon)
                        file_chooser_promise = self._page.expect_file_chooser(timeout=10000)
                        upload_btn = None
                        buttons = await self._page.query_selector_all('button, [role="button"]')
                        for b in buttons:
                            if await b.is_visible():
                                try:
                                    icon = await b.query_selector('md-icon')
                                    if icon:
                                        txt = await icon.inner_text()
                                        if txt and ('add_photo_alternate' in txt or 'image' in txt or 'attach_file' in txt):
                                            upload_btn = b
                                            break
                                except Exception:
                                    continue
                        if upload_btn:
                            await upload_btn.click()
                            file_chooser = await file_chooser_promise
                            await file_chooser.set_files(image_paths[0])
                            await asyncio.sleep(16.0)
                except Exception as e:
                    log.warning(f"UI Auto: Image upload failed: {e}")



            async def click_dropdown_option(options):
                def clean_text(text):
                    import re
                    return re.sub(r'[^a-z0-9]', '', str(text).lower())
                
                # options is a list of strings
                listboxes = await self._page.query_selector_all('[role="listbox"], [role="menu"], md-menu, .mdc-menu')
                for lb in listboxes:
                    if await lb.is_visible():
                        items = await lb.query_selector_all('[role="option"], [role="menuitem"], md-menu-item, li')
                        for item in items:
                            if await item.is_visible():
                                text = await item.inner_text()
                                c_text = clean_text(text)
                                for opt in options:
                                    if clean_text(opt) in c_text and len(c_text) > 0:
                                        await item.click(force=True)
                                        return True
                return False

            log.info("UI Auto: Configuring settings for Video...")
            
            # --- 1. OPEN SETTINGS POPUP ---
            popup_opened = False
            import re
            try:
                # Direct Native Playwright Click on the pill
                pill = self._page.locator('button, [role="button"]').filter(has_text=re.compile(r"veo|imagen|nano|video|image|16:9|1x", re.IGNORECASE)).first
                try:
                    await pill.wait_for(state="visible", timeout=3000)
                    await pill.click()
                    popup_opened = True
                except:
                    slider = self._page.locator('button:has(svg)').filter(has_text=re.compile(r"settings|cài đặt", re.IGNORECASE)).first
                    await slider.wait_for(state="visible", timeout=3000)
                    await slider.click()
                    popup_opened = True
            except Exception as e:
                log.warning(f"UI Auto: Native pill click FAILED: {e}")
            
            if not popup_opened:
                try:
                    pill = self._page.locator('button, [role="button"]').filter(has_text=re.compile(r"veo|imagen|nano|video|image|16:9|1x", re.IGNORECASE)).first
                    await pill.wait_for(state="visible", timeout=1500)
                    await pill.click()
                    popup_opened = True
                except: pass
            
            log.info(f"UI Auto: Popup open triggered: {popup_opened}")
            import asyncio
            await asyncio.sleep(1.5) # Wait for animation
            
            # --- 2. CONFIGURE SETTINGS INSIDE POPUP ---
            # Aspect Ratio mapping
            ratio_kws = ["16:9"]
            if "9:16" in aspect_ratio: ratio_kws = ["9:16", "dọc", "vertical"]
            elif "1:1" in aspect_ratio: ratio_kws = ["1:1", "vuông", "square"]
            elif "4:3" in aspect_ratio: ratio_kws = ["4:3"]
            elif "3:4" in aspect_ratio: ratio_kws = ["3:4"]
            
            # Duration mapping
            if "8" in str(duration) or "6" in str(duration):
                dur_kws = ["6s", "6 giây", "6 seconds", "8s", "8 giây", "8 seconds"]
            else:
                dur_kws = ["4s", "4 giây", "4 seconds", "5s", "5 giây", "5 seconds"]
            
            # Count mapping
            count_kw = f"x{count}" if int(count) > 1 else "1x"
            if count_kw == "x1": count_kw = "1x"
            
            logs = []
            try:
                import re
                # Find the popup using playwright locator
                popup = self._page.locator('md-menu[open], [role="menu"], [role="dialog"], .cdk-overlay-pane').filter(has_text=re.compile(r"aspect ratio|mode|tỷ lệ|16:9|nano|veo|video", re.IGNORECASE)).first
                await popup.wait_for(state="visible", timeout=3000)
                
                async def pw_click(keywords):
                    for kw in keywords:
                        try:
                            # Try role tab/radio/button first
                            btn = popup.get_by_role("tab", name=re.compile(kw, re.IGNORECASE)).first
                            if await btn.is_visible(timeout=200):
                                await btn.click(timeout=1000)
                                logs.append(f"Clicked tab: {kw}")
                                return True
                        except: pass
                        try:
                            btn = popup.get_by_text(kw, exact=True).first
                            if await btn.is_visible(timeout=200):
                                await btn.click(timeout=1000)
                                logs.append(f"Clicked exact: {kw}")
                                return True
                        except: pass
                        try:
                            btn = popup.locator(f"text=/{kw}/i").first
                            if await btn.is_visible(timeout=200):
                                await btn.click(timeout=1000)
                                logs.append(f"Clicked regex: {kw}")
                                return True
                        except: pass
                    logs.append(f"Not found: {keywords[0]}")
                    return False

                # 1. Click Video Mode
                await pw_click(["Video", "Veo", "Ảnh -> Video"])
                await asyncio.sleep(0.5)
                
                # 2. Click Aspect Ratio
                await pw_click(ratio_kws)
                await asyncio.sleep(0.5)
                
                # 3. Click Duration
                await pw_click(dur_kws)
                await asyncio.sleep(0.5)
                
                # 4. Click Count
                await pw_click([count_kw])
                
            except Exception as e:
                logs.append(f"Popup manipulation error: {e}")
            
            log.info(f"UI Auto: Configuration result: {logs}")
            await asyncio.sleep(0.5)

            # Close settings popup by safely clicking the main canvas background
            # Do NOT use Escape, as Escape will clear the prompt box if it has focus!
            await self._page.mouse.click(10, 10)
            await asyncio.sleep(0.5)
            log.info("UI Auto: Entering prompt...")
            existing = await self._page.query_selector_all('video, img[src*="blob:"], img[src*="googleusercontent.com"]')
            existing_srcs = []
            for img in existing:
                src = await img.evaluate('el => el.currentSrc || el.src || ""')
                if src:
                    existing_srcs.append(src)

            log.info(f"UI Auto: Entering prompt ({len(prompt)} chars)...")
            if not prompt:
                raise ValueError("Prompt is empty! Cannot generate video.")
                
            safe_prompt = prompt.replace("\n", " ")
            
            # 1. Find the prompt input by scanning all text editors and picking the one inside the prompt bar
            # Google Flow uses placeholder "What do you want to create?" or similar.
            prompt_input = None
            max_y = -1
            inputs = await self._page.query_selector_all('[data-slate-editor="true"], [role="textbox"], [contenteditable="true"], textarea, input')
            for inp in inputs:
                if await inp.is_visible():
                    label = (await inp.get_attribute('aria-label') or "").lower()
                    placeholder = (await inp.get_attribute('placeholder') or "").lower()
                    aria_placeholder = (await inp.get_attribute('aria-placeholder') or "").lower()
                    combined_attr = label + " " + placeholder + " " + aria_placeholder
                    
                    if 'tiêu đề' not in label and 'title' not in label and 'search' not in label and 'tìm kiếm' not in label:
                        # Prefer the one with placeholder "create" or "tạo"
                        if 'create' in combined_attr or 'tạo' in combined_attr:
                            prompt_input = inp
                            log.info(f"UI Auto: Found prompt input via placeholder/label: {combined_attr}")
                            break
                        
                        box = await inp.bounding_box()
                        if box and box['y'] > max_y:
                            max_y = box['y']
                            prompt_input = inp
                            
            if prompt_input:
                log.info("UI Auto: Found prompt input! Clicking it to focus...")
                await prompt_input.scroll_into_view_if_needed()
                await prompt_input.click(force=True)
                await asyncio.sleep(0.5)
                
                # The user explicitly requested to REMOVE Ctrl+A to avoid highlighting the whole screen.
                # We will just type the prompt directly.
                log.info("UI Auto: Typing prompt directly (skipping Ctrl+A as requested)...")
                
                # Paste the text directly (using clipboard or fast typing)
                try:
                    await prompt_input.fill(safe_prompt)
                    await prompt_input.evaluate("el => el.dispatchEvent(new Event('input', {bubbles: true}))")
                except Exception:
                    await self._page.keyboard.type(safe_prompt, delay=10)
                    
                await asyncio.sleep(0.5)
                await self._page.keyboard.press("Space")
                await self._page.keyboard.press("Backspace")
                await asyncio.sleep(0.5)
            else:
                log.warning("UI Auto: Could not find prompt input field using DOM!")
                # Fallback to absolute click just in case
                viewport = self._page.viewport_size
                if viewport:
                    cx = viewport['width'] / 2
                    cy = viewport['height'] - 120 # Much safer distance from bottom
                    await self._page.mouse.click(cx, cy)
                    await asyncio.sleep(0.5)
                    await self._page.keyboard.type(safe_prompt, delay=0)
            
            log.info("UI Auto: Clicking Generate button next to Settings Pill...")
            await asyncio.sleep(0.5)
            try:
                # Add "Create", "Send", "Submit" to the query selector
                selectors = [
                    'button[aria-label*="Generate"]', 'button[title*="Generate"]', 'button:has-text("Generate")',
                    'button[aria-label*="Tạo"]', 'button[title*="Tạo"]', 'button:has-text("Tạo")',
                    'button[aria-label*="Create"]', 'button[title*="Create"]', 'button:has-text("Create")',
                    'button[aria-label*="Send"]', 'button[title*="Send"]'
                ]
                gen_btns = await self._page.query_selector_all(', '.join(selectors))
                gen_btn = None
                for btn in gen_btns:
                    if await btn.is_visible():
                        label = (await btn.get_attribute('aria-label') or "").lower()
                        title = (await btn.get_attribute('title') or "").lower()
                        text = (await btn.inner_text() or "").lower()
                        # Exclude plus, upload, and setting pills
                        if any(x in label or x in title or x in text for x in ["add", "plus", "upload", "tải", "thêm", "+", "agent", "setting", "cài đặt", "video", "image", "ảnh"]):
                            continue
                        gen_btn = btn
                        break
                
                if gen_btn:
                    log.info("UI Auto: Found Generate button via aria-label/title, clicking it...")
                    await gen_btn.click(force=True)
                else:
                    log.info("UI Auto: Finding submit button near prompt input...")
                    clicked = False
                    if prompt_input:
                        parent = await prompt_input.evaluate_handle('el => el.closest("div")?.parentElement?.parentElement || el.parentElement.parentElement')
                        if parent:
                            btns = await parent.query_selector_all('button, [role="button"]')
                            for b in reversed(btns): # Usually the send button is the last button
                                if await b.is_visible():
                                    label = (await b.get_attribute('aria-label') or "").lower()
                                    title = (await b.get_attribute('title') or "").lower()
                                    text = (await b.inner_text() or "").lower()
                                    
                                    # Skip plus, upload, agent, and setting/mode pills
                                    if any(x in label or x in title or x in text for x in ["add", "plus", "upload", "tải", "thêm", "+", "agent", "setting", "cài đặt", "video", "image", "ảnh"]):
                                        continue
                                        
                                    await b.click(force=True)
                                    log.info(f"UI Auto: Clicked button near prompt input: label={label}, title={title}")
                                    clicked = True
                                    break
                    if not clicked:
                        log.info("UI Auto: Pressing Enter to submit...")
                        await self._page.keyboard.press("Enter")
                        await asyncio.sleep(0.5)
                        await self._page.keyboard.press("Control+Enter")
                        await asyncio.sleep(0.5)
                        await self._page.keyboard.press("Meta+Enter") # For Mac
            except Exception as e:
                log.warning(f"UI Auto: Failed to click submit, fallback to enter: {e}")
                await self._page.keyboard.press("Enter")
                await asyncio.sleep(0.5)
                await self._page.keyboard.press("Control+Enter")
                
            log.info("UI Auto: Waiting for Generation to complete...")
            start_time = _time.time()
            media_list = []
            max_wait = 600
            
            # ---------------------------------------------------------
            # INSTRUMENTATION INJECTION
            # ---------------------------------------------------------
            import time as perf_time
            perf_timestamps = {
                "submit_time": perf_time.perf_counter(),
                "render_start_time": perf_time.perf_counter(), # Approximate since we just hit Enter
                "poll_iterations": []
            }
            
            # 1. Listen for Network Responses
            async def on_response(response):
                try:
                    url = response.url
                    # batchCheckAsyncVideoGenerationStatus is the endpoint Google uses
                    if "batchCheckAsyncVideoGenerationStatus" in url or "video" in response.request.resource_type:
                        if "network" not in perf_timestamps:
                            perf_timestamps["network"] = perf_time.perf_counter()
                except: pass
            self._page.on("response", on_response)
            
            # 2. Listen for WebSocket
            async def on_websocket(ws):
                try:
                    if "websocket" not in perf_timestamps:
                        perf_timestamps["websocket"] = perf_time.perf_counter()
                except: pass
            self._page.on("websocket", on_websocket)
            
            # 3. Setup Mutation Observer for DOM and Download button
            async def notify_dom():
                if "dom" not in perf_timestamps:
                    perf_timestamps["dom"] = perf_time.perf_counter()
            async def notify_btn():
                if "download_btn" not in perf_timestamps:
                    perf_timestamps["download_btn"] = perf_time.perf_counter()
                    
            try:
                await self._page.expose_function("_notify_dom", notify_dom)
                await self._page.expose_function("_notify_btn", notify_btn)
            except Exception:
                pass # Already exposed if running multiple times
                
            await self._page.evaluate('''() => {
                window._inst_video_found = false;
                window._inst_btn_found = false;
                const observer = new MutationObserver((mutations) => {
                    const video = document.querySelector('video');
                    if (video && !window._inst_video_found) {
                        window._inst_video_found = true;
                        window._notify_dom();
                    }
                        const dbtn = document.querySelector('button[aria-label*="ownload"], button[title*="ownload"], [aria-label*="ownload"], button[aria-label*="ải"], button[title*="ải"], [aria-label*="ải"]');
                    if (dbtn && !window._inst_btn_found) {
                        window._inst_btn_found = true;
                        window._notify_btn();
                    }
                });
                observer.observe(document.body, {childList: true, subtree: true});
            }''')
            # ---------------------------------------------------------
            
            last_progress = ""
            src_attempts = {}
            while time.time() - start_time < max_wait:
                # Close any pesky popups
                try:
                    await self._page.evaluate('''() => {
                        const btn = document.querySelector('button[aria-label="Got it"], button:has-text("Got it"), button:has-text("Đã hiểu")');
                        if (btn) btn.click();
                    }''')
                except: pass
                
                # Check for platform errors to update status immediately
                try:
                    error_msg = await self._page.evaluate('''() => {
                        const errEls = Array.from(document.querySelectorAll('snack-bar-container, md-toast, .error-message, .error, [role="alert"]'));
                        for (const el of errEls) {
                            if (el.offsetParent) {
                                const text = el.innerText || "";
                                if (text.length > 5 && (text.toLowerCase().includes("error") || text.toLowerCase().includes("lỗi") || text.includes("must be provided") || text.includes("failed") || text.includes("could not"))) {
                                    // Try to close it so it doesn't block future runs
                                    const dismiss = el.querySelector('button');
                                    if(dismiss) dismiss.click();
                                    return text;
                                }
                            }
                        }
                        return null;
                    }''')
                    if error_msg:
                        log.error(f"UI Auto: Platform threw an error during generation: {error_msg}")
                        return {"success": False, "error": f"Nền tảng báo lỗi: {error_msg.strip()}"}
                except Exception:
                    pass

                poll_start_perf = perf_time.perf_counter()
                
                if self._page.is_closed():
                    raise RuntimeError("Browser was closed by user")
                    
                try:
                    progress_text = await self._page.evaluate('''() => {
                        const el = Array.from(document.querySelectorAll('div, span')).find(e => e.textContent && e.textContent.trim().match(/^[0-9]+%$/));
                        return el ? el.textContent.trim() : "";
                    }''')
                    if progress_text and progress_text != last_progress:
                        log.info(f"UI Auto: Real-time generation progress: {progress_text} ...")
                        last_progress = progress_text
                except:
                    pass
                    
                if "navtools_first_detect" not in perf_timestamps:
                    # Not found yet, we will mark it if result_imgs is found
                    pass
                    
                result_imgs = await self._page.query_selector_all('video, img[src*="blob:"], img[src*="googleusercontent.com"]')
                # ------------------- EVIDENCE LOGGING -------------------
                if result_imgs and "navtools_first_detect" not in perf_timestamps:
                    perf_timestamps["navtools_first_detect"] = perf_time.perf_counter()
                    
                if result_imgs:
                    dump_info = await self._page.evaluate(
                        '''(els) => els.map(v => {
                            const actualSrc = v.currentSrc || v.src || "";
                            const isVideo = v.tagName === 'VIDEO';
                            if (isVideo && actualSrc) {
                                return { src: actualSrc, visible: true };
                            }
                            const rect = v.getBoundingClientRect();
                            const isLarge = rect.width >= 100 && rect.height >= 100;
                            
                            // Ignore small UI avatars from googleusercontent or UI icons
                            if (!actualSrc.includes('blob:') && !isLarge) {
                                return { src: actualSrc, visible: false };
                            }
                            
                            return {
                                src: actualSrc, 
                                visible: (isLarge || v.readyState > 0 || actualSrc.includes('blob:'))
                            };
                        })''', result_imgs
                    )
                    v_data = dump_info
                    
                    new_srcs = []
                    blob_info = None
                    for item in v_data:
                        src = item.get("src")
                        if item.get("visible") and src and src not in existing_srcs:
                            new_srcs.append(src)
                            
                    for src in new_srcs:
                        src_attempts[src] = src_attempts.get(src, 0) + 1
                        if src_attempts[src] > 3:
                            continue # We already tried too many times
                            
                        log.info(f"UI Auto: Processing new video src...")
                        
                        # Log performance
                        if "download_started" not in perf_timestamps: perf_timestamps["download_started"] = perf_time.perf_counter()
                        
                        # NATIVE DOWNLOAD - Bypassed to avoid 15s timeout. We go straight to HTTP fetch.
                        downloaded = False
                        blob_info = {"data": None, "error": "Bypassed", "size": 0}
                        
                        if not downloaded:
                            log.warning(f"UI Auto: Falling back to HTTP memory fetch...")
                            blob_info = await self._page.evaluate(
                                '''async (url) => {
                                    try {
                                        const controller = new AbortController();
                                        const timeoutId = setTimeout(() => controller.abort(), 10000);
                                        const r = await fetch(url, { signal: controller.signal });
                                        clearTimeout(timeoutId);
                                        const b = await r.blob();
                                        if (b.size > 50000) {
                                            return new Promise((resolve) => {
                                                const reader = new FileReader();
                                                reader.onloadend = () => resolve({size: b.size, data: reader.result});
                                                reader.readAsDataURL(b);
                                            });
                                        }
                                        return {size: b.size, data: null, error: "Too small"};
                                    } catch(e) { 
                                        if (url.startsWith('https://')) {
                                            return {size: 100000, data: url, error: "CORS fallback"};
                                        }
                                        return {size: 0, data: null, error: e.message || "Fetch aborted or unknown error"}; 
                                    }
                                }''', src
                            )
                        if blob_info and blob_info.get("data"):
                            log.info(f"UI Auto: Found REAL generated video of size {blob_info['size']} bytes!")
                            existing_srcs.append(src)
                            media_list.append({
                                "image": {
                                    "generatedImage": {
                                        "url": blob_info["data"],
                                        "name": f"flow_video_{int(_time.time())}_{len(media_list)}",
                                    }
                                }
                            })
                            if callback:
                                try:
                                    await callback(blob_info["data"])
                                except Exception:
                                    pass
                            downloaded = True
                        if not downloaded:
                            # Absolute final fallback: just return the URL and let the frontend try its luck
                            if not src.startswith('blob:'):
                                log.info(f"UI Auto: Falling back to HTTP URL: {src[:100]}")
                                existing_srcs.append(src)
                                media_list.append({
                                    "image": {
                                        "generatedImage": {
                                            "url": src,
                                            "name": f"flow_video_{int(_time.time())}_{len(media_list)}",
                                        }
                                    }
                                })
                                if callback:
                                    try:
                                        await callback(src)
                                    except Exception:
                                        pass
                            else:
                                # Absolute final fallback if both blob fetch and download button failed: return the blob URL anyway
                                log.info(f"UI Auto: Falling back to Blob URL after failed fetch/download: {src[:100]}")
                                existing_srcs.append(src)
                                media_list.append({
                                    "image": {
                                        "generatedImage": {
                                            "url": src,
                                            "name": f"flow_video_{int(_time.time())}_{len(media_list)}",
                                        }
                                    }
                                })
                                if callback:
                                    try:
                                        await callback(src)
                                    except Exception:
                                        pass
                                downloaded = True
                    
                    poll_end_perf = perf_time.perf_counter()
                    
                    perf_timestamps["poll_iterations"].append({
                        "iteration": len(perf_timestamps["poll_iterations"]) + 1,
                        "time": poll_start_perf,
                        "duration": poll_end_perf - poll_start_perf
                    })
                    
                if len(media_list) >= count:
                    break
                
                # The sleep is part of the existing logic
                await asyncio.sleep(0.5)
            
            if not media_list:
                raise RuntimeError(f"No result video found after {max_wait}s")
            
            perf_timestamps["ui_updated"] = perf_time.perf_counter()
            try:
                with open(DATA_DIR / "timeline_raw.json", "a") as tf:
                    tf.write(json.dumps(perf_timestamps) + "\n")
            except Exception:
                pass
            
            return {"media": media_list}
            
        except Exception as e:
            log.error(f"UI Auto failed: {e}")
            raise RuntimeError(f"UI Auto failed: {e}")



    async def generate_video(self, prompt, image_paths=None, model="veo-3.1-fast", aspect_ratio="16:9", duration=8, quality="720p", seed=None, project_name="", count=1, callback=None):
        try:
            return await self._generate_video_whisk(prompt, image_paths, model, aspect_ratio, duration, project_name, count, callback)
        except Exception as e:
            import traceback
            try:
                with open(DATA_DIR / "crash_log.txt", "w", encoding="utf-8") as f:
                    f.write(traceback.format_exc())
            except:
                pass
            raise

    async def flow_concat(self, media_ids, output_path=None, timeout=300):
        if not media_ids:
            log.error("flow_concat called without media_ids")
            return None
        await self.ensure_token()
        input_videos = [{"mediaId": mid, "startOffsetMs": i * 8000} for i, mid in enumerate(media_ids)]
        payload = {"inputVideos": input_videos}
        result = await self._aisandbox_post_absolute(f"{AISANDBOX_BASE}/video:concat", payload)
        media_id = self._extract_generation_id(result, 0) or result.get("mediaId") or result.get("name")
        if output_path and media_id:
            await self.download_video(media_id, output_path)
        return media_id

    async def _aisandbox_post_absolute(self, url: str, payload: dict):
        await self.ensure_token()
        body_json = json.dumps(payload)
        for attempt in range(MAX_RETRY_COUNT):
            try:
                if self._page.is_closed():
                    raise RuntimeError("Browser page is closed")
                result = await asyncio.wait_for(
                    self._page.evaluate(
                        """async ({url, token, body}) => {
                            const r = await fetch(url, {method: "POST", headers: {"Authorization": "Bearer " + token, "Content-Type": "application/json"}, body});
                            const text = await r.text();
                            try { return {ok: r.ok, status: r.status, json: JSON.parse(text)}; }
                            catch(e) { return {ok: r.ok, status: r.status, text}; }
                        }""",
                        {"url": url, "token": self._token, "body": body_json},
                    ),
                    timeout=120,
                )
                if result.get("ok"):
                    return result.get("json")
                if result.get("status") in (401, 403):
                    await self.renew_token()
                await asyncio.sleep(1 + attempt)
            except Exception as e:
                log.warning(f"aisandbox post failed: {e}")
                if attempt == MAX_RETRY_COUNT - 1:
                    raise
        raise RuntimeError("aisandbox post failed")

    async def extend_video(self, media_id, prompt, quality="720p", aspect_ratio="16:9"):
        await self.ensure_token()
        workflow_id = str(uuid.uuid4())
        recaptcha_token = await self.get_recaptcha_token("video_extend")
        payload = {
            "clientContext": {"sessionId": self._session_id, "workflowId": workflow_id},
            "mediaId": media_id,
            "prompt": prompt,
            "quality": quality,
            "aspectRatio": aspect_ratio,
            "recaptchaToken": recaptcha_token,
        }
        result = await self._browser_sandbox_request("video:extend", payload)
        return self._extract_generation_id(result, 0) or result

    def _extract_generation_id(self, result, _depth=0):
        if _depth > 6:
            return None
        if isinstance(result, dict):
            media_arr = result.get("media")
            if isinstance(media_arr, list) and media_arr:
                media_name = media_arr[0].get("name") or media_arr[0].get("mediaId")
                if media_name:
                    return media_name
            for key in ("name", "mediaId", "generationId", "operationName"):
                val = result.get(key)
                if isinstance(val, str):
                    return val
            for val in result.values():
                nested = self._extract_generation_id(val, _depth + 1)
                if nested:
                    return nested
        elif isinstance(result, list):
            for item in result:
                nested = self._extract_generation_id(item, _depth + 1)
                if nested:
                    return nested
        return None

    def _image_to_base64(self, image_path):
        from PIL import Image
        import io

        try:
            with open(os.path.abspath(image_path), "rb") as f:
                raw = f.read()
            img = Image.open(io.BytesIO(raw))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((1536, 1536), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=92)
            data = base64.b64encode(buf.getvalue()).decode("ascii")
            log.info(f"Image base64 {Path(image_path).name}: {buf.getbuffer().nbytes} bytes")
            return "data:image/jpeg;base64," + data
        except Exception as e:
            log.error(f"Image encode failed: {e}")
            raise

    async def _backbone_generate_caption(self, image_b64: str, category: str):
        """Call backbone.generateCaption tRPC to get a text description of an image."""
        img_hash = hashlib.md5(image_b64[:8192].encode()).hexdigest()
        cached = FlowClient._caption_cache.get(img_hash)
        if cached:
            log.info(f"Backbone caption (cached): {cached[:80]}...")
            return cached
        payload = {"category": category, "image": image_b64, "sessionId": self._session_id}
        try:
            result = await self._api("backbone.generateCaption", payload)
            data = self._extract(result) or result
            caption = data if isinstance(data, str) else data.get("caption") or data.get("prompt") or ""
            FlowClient._caption_cache[img_hash] = caption
            return caption
        except Exception as e:
            log.warning(f"Backbone caption failed: {e}")
            return ""

    async def _backbone_generate_storyboard_prompt(self, characters, additional_input: str):
        """Call backbone.generateStoryBoardPrompt to build an enhanced prompt."""
        payload = {
            "characters": characters,
            "additionalInput": additional_input,
            "sessionId": self._session_id,
        }
        try:
            result = await self._api("backbone.generateStoryBoardPrompt", payload)
            data = self._extract(result) or result
            if isinstance(data, str):
                return data
            if isinstance(data, dict):
                enhanced = data.get("prompt") or data.get("enhancedPrompt")
                if enhanced:
                    return enhanced
                prompts = data.get("prompts")
                if isinstance(prompts, list) and prompts:
                    return prompts[0]
        except Exception as e:
            log.warning(f"Storyboard prompt failed: {e}")
        return additional_input

    def _get_project_id_from_url(self) -> str | None:
        url = self._page.url or ""
        import re
        m = re.search(r"/project/([a-f0-9\-]+)", url)
        if m:
            return m.group(1)
        return None

    async def _ensure_project_id(self) -> str:
        project_id = self._get_project_id_from_url()
        if project_id:
            return project_id
            
        url = self._page.url or ""
        if "tools/flow" not in url:
            log.info("FlowClient: Navigating to Flow to ensure project ID...")
            await self._page.goto("https://labs.google/fx/vi/tools/flow", wait_until="load", timeout=30000)
            await asyncio.sleep(2)
            
        # Dismiss any modals
        try:
            await self._page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
        except Exception:
            pass
            
        # Click Dự án mới (wait up to 15s for the button to render)
        selector = 'button:has-text("Dự án mới"), button:has-text("New project"), button:has-text("dự án mới")'
        try:
            new_btn = await self._page.wait_for_selector(selector, timeout=15000)
            if new_btn:
                await new_btn.click()
                await self._page.wait_for_url("**/project/**", timeout=20000)
        except Exception as click_err:
            log.warning(f"Failed to find or click New Project button: {click_err}")
                
        project_id = self._get_project_id_from_url()
        if not project_id:
            # Fallback to generating a uuid if still not found
            project_id = str(uuid.uuid4())
            
        return project_id

    async def _generate_image_whisk(self, prompt, image_paths=None, model="Nano Banana 2", aspect_ratio="1:1", count=1):
        await self.ensure_token()
        
        project_id = await self._ensure_project_id()
        
        inputs = []
        for p in image_paths or []:
            if os.path.isfile(p):
                inputs.append(await self.upload_image(p))
            else:
                log.warning(f"Reference image not found: {p}")
        
        # Get reCAPTCHA token
        try:
            recaptcha_token = await self.get_recaptcha_token("flow_generate_image")
        except Exception as re_err:
            log.warning(f"Failed to get reCAPTCHA token via execute, trying fallback: {re_err}")
            recaptcha_token = ""
            
        session_id = f";{int(time.time() * 1000)}"
        
        # Model mapping
        clean_model = model.replace("🍌", "").strip().lower()
        if "banana" in clean_model or "narwhal" in clean_model:
            model_name = "NARWHAL"
        elif "imagen 3.5" in clean_model:
            model_name = "IMAGEN_3_5"
        elif "imagen 4" in clean_model:
            model_name = "IMAGEN_4"
        elif "ultra" in clean_model:
            model_name = "IMAGEN_4_ULTRA"
        else:
            model_name = "NARWHAL"
            
        # Aspect ratio mapping
        aspect_ratio_enum = "IMAGE_ASPECT_RATIO_SQUARE"
        clean_ratio = aspect_ratio.strip()
        if "16:9" in clean_ratio:
            aspect_ratio_enum = "IMAGE_ASPECT_RATIO_LANDSCAPE"
        elif "9:16" in clean_ratio:
            aspect_ratio_enum = "IMAGE_ASPECT_RATIO_PORTRAIT"
        elif "3:4" in clean_ratio:
            aspect_ratio_enum = "IMAGE_ASPECT_RATIO_PORTRAIT_THREE_FOUR"
        elif "4:3" in clean_ratio:
            aspect_ratio_enum = "IMAGE_ASPECT_RATIO_LANDSCAPE_FOUR_THREE"
            
        client_context = {
            "recaptchaContext": {
                "token": recaptcha_token,
                "applicationType": "RECAPTCHA_APPLICATION_TYPE_WEB"
            },
            "projectId": project_id,
            "tool": "PINHOLE",
            "sessionId": session_id
        }
        
        requests = []
        for i in range(count):
            requests.append({
                "clientContext": client_context,
                "imageModelName": model_name,
                "imageAspectRatio": aspect_ratio_enum,
                "structuredPrompt": {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                },
                "seed": (int(time.time()) + i * 12345) % 1000000,
                "imageInputs": inputs
            })
            
        payload = {
            "clientContext": client_context,
            "mediaGenerationContext": {
                "batchId": str(uuid.uuid4())
            },
            "useNewMedia": True,
            "requests": requests
        }
        
        endpoint = f"projects/{project_id}/flowMedia:batchGenerateImages"
        return await self._browser_sandbox_request(endpoint, payload)

    async def generate_image(self, prompt, image_paths=None, model="Nano Banana 2", aspect_ratio="1:1", project_name="", count=1, callback=None, **kwargs):
        await self.ensure_token()
        if image_paths:
            characters = []
            for i, p in enumerate(image_paths):
                image_b64 = self._image_to_base64(p)
                caption = await self._backbone_generate_caption(image_b64, "CHARACTER")
                characters.append({
                    "imageId": str(uuid.uuid4()),
                    "category": "CHARACTER",
                    "base64Image": image_b64,
                    "isPlaceholder": False,
                    "index": i,
                    "isSelected": True,
                    "prompt": caption,
                })
            prompt = await self._backbone_generate_storyboard_prompt(characters, prompt)

        result = await self._generate_image_whisk(prompt, image_paths, model, aspect_ratio, count=count)

        def _extract_all_images(d):
            images = []
            if not isinstance(d, dict):
                return images
            media = d.get("media")
            if isinstance(media, list):
                for m in media:
                    if isinstance(m, dict):
                        img_wrap = m.get("image")
                        gen = (img_wrap or {}).get("generatedImage")
                        if gen:
                            gen.setdefault("name", m.get("name"))
                            images.append(gen)
            generated = d.get("generatedImages")
            if isinstance(generated, list):
                for g in generated:
                    if isinstance(g, dict):
                        images.append(g)
            for key in ("imagePanels", "responses"):
                arr = d.get(key)
                if isinstance(arr, list):
                    for entry in arr:
                        images.extend(_extract_all_images(entry))
            return images

        images = _extract_all_images(result)
        if not images:
            self._last_error = result
            raise RuntimeError(f"Image gen failed: {json.dumps(result, ensure_ascii=False)[:500]}")
        return images if count > 1 else images[0]

    async def upsample_image(self, media_id, resolution="2K"):
        await self.ensure_token()
        res_key = resolution.upper().replace(" ", "")
        target_enum = {"2K": "UPSCALE_2K", "4K": "UPSCALE_4K"}.get(res_key, "UPSCALE_2K")
        recaptcha_token = await self.get_recaptcha_token("image_upsample")
        payload = {"mediaId": media_id, "targetResolution": target_enum, "recaptchaToken": recaptcha_token}
        return await self._browser_sandbox_request("image:upscale", payload)

    async def upsample_video(self, media_id, output_path=None, resolution="1080p"):
        await self.ensure_token()
        recaptcha_token = await self.get_recaptcha_token("video_upsample")
        payload = {
            "mediaId": media_id,
            "targetResolution": resolution.upper().replace("P", "p"),
            "sessionId": self._session_id,
            "recaptchaToken": recaptcha_token,
        }
        result = await self._browser_sandbox_request("video:upscale", payload)
        out_id = self._extract_generation_id(result, 0) or media_id
        if output_path:
            await self.download_video(out_id, output_path)
        return out_id

    async def poll_status(self, generation_id):
        await self.ensure_token()
        payload = {"generationIds": [generation_id]}
        raw = await self._browser_sandbox_request("video:batchCheckAsyncVideoGenerationStatus", payload)
        media_arr = raw.get("media") if isinstance(raw, dict) else None
        if isinstance(media_arr, list) and media_arr:
            item = media_arr[0]
            status = str(item.get("status") or item.get("state") or "").upper()
            if status in ("SUCCEEDED", "SUCCESS", "COMPLETED", "DONE"):
                return {"status": "COMPLETED", "result": item, "media": item}
            if status in ("FAILED", "ERROR", "CANCELLED"):
                return {"status": "FAILED", "error": item}
            return {"status": "RUNNING", "raw": item}
        return raw if isinstance(raw, dict) else {"status": "UNKNOWN", "raw": raw}

    async def wait_for_completion(self, generation_id, timeout=600, callback=None, cancel_check=None):
        """Poll until video generation completes or times out."""
        start = time.time()
        polls = 0
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 6
        while time.time() - start < timeout:
            if cancel_check and cancel_check():
                log.info("wait_for_completion: cancelled by caller")
                return {"status": "FAILED", "error": "CANCELLED"}
            polls += 1
            try:
                s = await self.poll_status(generation_id)
                consecutive_errors = 0
                if callback:
                    callback(s)
                status = str(s.get("status", "")).upper()
                if status in ("COMPLETED", "FAILED", "FATAL"):
                    return s
                log.info(f"Poll #{polls}: {json.dumps(s, ensure_ascii=False)[:300]}")
            except Exception as e:
                consecutive_errors += 1
                log.error(f"Poll error {consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}: {e}")
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    return {"status": "FAILED", "error": str(e)}
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        return {"status": "FAILED", "error": "TIMEOUT"}

    async def _fetch_mp4_via_browser_fetch(self, media_name):
        result = await self._page.evaluate(
            """async (mediaName) => {
                try {
                    const r = await fetch("https://aisandbox-pa.googleapis.com/v1/media/" + encodeURIComponent(mediaName));
                    if (!r.ok) return {ok:false, error:r.status};
                    const buf = await r.arrayBuffer();
                    let binary = "";
                    const bytes = new Uint8Array(buf);
                    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
                    return {ok:true, b64:btoa(binary), ct:r.headers.get("content-type") || ""};
                } catch(e) { return {ok:false, error:e.message || "unknown"}; }
            }""",
            media_name,
        )
        if not result.get("ok"):
            log.warning(f"Browser-fetch MP4 failed for {media_name}: {result.get('error', 'unknown')}")
            return None
        data = base64.b64decode(result.get("b64", ""))
        log.info(f"Browser-fetch MP4 ok: {len(data)} bytes {result.get('ct')}")
        return data

    async def get_download_url(self, media_id):
        """Get video download URL via labs.google redirect endpoint."""
        if not media_id: return None
        if "getMediaUrlRedirect" in media_id:
            redirect_url = media_id if media_id.startswith("http") else f"https://labs.google{media_id}"
        else:
            redirect_url = f"https://labs.google/fx/api/trpc/media.getMediaUrlRedirect?name={media_id}"
        try:
            result = await self._page.evaluate(
                """async (url) => {
                    try {
                        const r = await fetch(url, {method: "GET", credentials: "include", redirect: "follow"});
                        if (r.ok) {
                            const ct = r.headers.get("content-type") || "";
                            if (ct.includes("json")) return {type: "json", data: await r.json()};
                            return {type: "redirect", url: r.url, size: r.headers.get("content-length")};
                        }
                        return {error: r.status, text: (await r.text()).substring(0, 500)};
                    } catch(e) { return {error: e.message}; }
                }""",
                redirect_url,
            )
            if result.get("type") == "redirect":
                return result.get("url")
            data = result.get("data")
            if isinstance(data, dict):
                extracted = self._extract(data)
                if isinstance(extracted, str):
                    return extracted
                if isinstance(extracted, dict):
                    return extracted.get("url")
            log.warning(f"Download URL failed: {json.dumps(result, ensure_ascii=False)[:500]}")
        except Exception as e:
            log.error(f"Download URL error: {e}")
        return None

    async def download_result(self, download_url, output_path):
        """Download video/image from URL to local file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        log.info(f"Downloading to {output_path}...")
        try:
            r = await self._page.request.get(download_url)
            if not r.ok:
                log.error(f"Download failed HTTP {r.status}")
                return False
            content = await r.body()
            with open(output_path, "wb") as f:
                f.write(content)
            size_mb = len(content) / 1048576
            log.info(f"Downloaded: {output_path} ({size_mb:.1f} MB)")
            return True
        except Exception as e:
            log.error(f"Download error: {e}")
            return False

    async def download_video(self, generation_id, output_path):
        """Full download flow: get URL via tRPC then download file."""
        url = await self.get_download_url(generation_id)
        if url:
            return await self.download_result(url, output_path)
        log.info("tRPC URL failed, trying direct media fetch...")
        direct_url = f"https://aisandbox-pa.googleapis.com/v1/media/{generation_id}"
        return await self.download_result(direct_url, output_path)

    async def _get_or_create_project(self):
        """Get existing project or create new one (tRPC)."""
        result = await self._api("project.searchUserProjects", {}, "GET")
        data = self._extract(result) or {}
        projects = data.get("projects", [])
        if isinstance(projects, list) and projects:
            pid = projects[0].get("id") or projects[0].get("projectId")
            log.info(f"Using existing project: {pid}")
            return pid
        log.info("No existing project found")
        return str(uuid.uuid4())
