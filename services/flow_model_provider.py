"""Dynamic Model Provider for Google Flow.

Uses videoFx.getModels tRPC endpoint to fetch REAL models from the user's account.
Runs headless (no visible browser), fast (~5s).
"""

import asyncio
import json
import logging
import re
from pathlib import Path

from config.constants import DATA_DIR

log = logging.getLogger("VidGen")

CACHE_FILE = DATA_DIR / "models_cache.json"

# tRPC endpoint that returns both image + video + audio models
MODELS_ENDPOINT = "videoFx.getModels"
MODELS_INPUT = '{"json":null,"meta":{"values":["undefined"]}}'


class FlowModelProvider:
    """Provides dynamic model configurations from Google Flow."""

    def __init__(self):
        self.models = self.load_cache()

    def load_cache(self) -> dict:
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log.warning(f"Failed to load models cache: {e}")
        return {}

    def save_cache(self, data: dict):
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.models = data
        except Exception as e:
            log.error(f"Failed to save models cache: {e}")

    async def sync_models(self, user_data_dir: str):
        """Fast headless sync: ~5s, no visible browser, uses tRPC API."""
        log.info("Starting Flow model sync (headless)...")
        from utils.platform import find_chrome
        from playwright.async_api import async_playwright
        import urllib.parse
        import shutil
        import tempfile

        chrome_exe = find_chrome()

        # Copy cookies to a temp profile to avoid ProcessSingleton lock
        # when Chrome/BrowserManager is already using the same profile
        temp_profile = tempfile.mkdtemp(prefix="navtools_sync_")
        try:
            src_cookies = Path(user_data_dir) / "Default" / "Cookies"
            src_local_state = Path(user_data_dir) / "Local State"
            dst_default = Path(temp_profile) / "Default"
            dst_default.mkdir(parents=True, exist_ok=True)

            if src_cookies.exists():
                shutil.copy2(str(src_cookies), str(dst_default / "Cookies"))
            if src_local_state.exists():
                shutil.copy2(str(src_local_state), str(Path(temp_profile) / "Local State"))
        except Exception as e:
            log.warning(f"Could not copy cookies to temp profile: {e}")

        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch_persistent_context(
                user_data_dir=temp_profile,
                headless=True,
                executable_path=chrome_exe,
                args=[
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )
            page = await browser.new_page()

            # Step 1: Get session token (~1s)
            await page.goto(
                "https://labs.google/fx/api/auth/session",
                wait_until="domcontentloaded",
                timeout=10000,
            )
            body = await page.inner_text("body")
            try:
                session = json.loads(body)
                token = session.get("accessToken") or session.get("access_token", "")
            except Exception:
                token = ""

            if not token:
                log.error("No session token - account may not be logged in")
                return self.models

            # Step 2: Navigate to Flow for cookie context
            await page.goto(
                "https://labs.google/fx/vi/tools/flow",
                wait_until="domcontentloaded",
                timeout=10000,
            )

            # Step 3: Call tRPC to get all models (~1s)
            url = f"https://labs.google/fx/api/trpc/{MODELS_ENDPOINT}?input={urllib.parse.quote(MODELS_INPUT)}"

            result = await page.evaluate(
                """async ({url, token}) => {
                    try {
                        const r = await fetch(url, {
                            headers: {'Authorization': 'Bearer ' + token},
                            credentials: 'include'
                        });
                        if (!r.ok) return {error: r.status};
                        return await r.json();
                    } catch(e) { return {error: e.message}; }
                }""",
                {"url": url, "token": token},
            )

            if isinstance(result, dict) and "error" in result:
                log.error(f"tRPC getModels failed: {result['error']}")
                return self.models

            # Parse response
            raw = result
            for key in ("result", "data", "json", "result"):
                if isinstance(raw, dict):
                    raw = raw.get(key, raw)

            model_config = raw.get("modelConfig", {}) if isinstance(raw, dict) else {}

            # Extract image models (filter out upsample-only)
            image_models = []
            for m in model_config.get("imageModels", []):
                name = m.get("displayName", "")
                key = m.get("key", "")
                if not name:
                    continue
                if "upsample" in key.lower():
                    continue
                image_models.append({
                    "name": name,
                    "type": "image",
                    "key": key,
                    "usages": m.get("usages", []),
                })

            # Extract video models (include all) from getModels
            video_models_dict = {}
            for m in model_config.get("videoModels", []):
                name = m.get("displayName", "")
                key = m.get("key", "")
                if not name:
                    continue
                
                raw_usages = m.get("usages", [])
                parsed_usages = []
                for ru in raw_usages:
                    length = ru.get("videoLengthSeconds")
                    cmap = ru.get("creditMapping", {})
                    cost = None
                    for tier, val in cmap.items():
                        c = val.get("creditInfo", {}).get("cost")
                        if c is not None:
                            cost = c
                            break
                    if length is not None:
                        parsed_usages.append({
                            "duration": length,
                            "cost": cost if cost is not None else 10
                        })
                
                video_models_dict[key] = {
                    "name": name,
                    "type": "video",
                    "key": key,
                    "usages": parsed_usages,
                }

            video_models = list(video_models_dict.values())

            # Extract audio models
            audio_models = []
            for m in model_config.get("audioModels", []):
                name = m.get("displayName", "")
                key = m.get("key", "")
                if not name:
                    continue
                audio_models.append({
                    "name": name,
                    "type": "audio",
                    "key": key,
                })

            # Extract tier defaults
            tier_defaults = model_config.get("tierDefaults", {})

            data = {
                "image_models": image_models,
                "video_models": video_models,
                "audio_models": audio_models,
                "tier_defaults": tier_defaults,
            }

            self.save_cache(data)
            log.info(
                f"Sync OK: {len(image_models)} image, "
                f"{len(video_models)} video, {len(audio_models)} audio models"
            )
            return data

        except Exception as e:
            log.error(f"Sync failed: {e}")
            return self.models
        finally:
            if "browser" in locals():
                await browser.close()
            await pw.stop()
            # Clean up temp profile
            try:
                shutil.rmtree(temp_profile, ignore_errors=True)
            except Exception:
                pass


model_provider = FlowModelProvider()
