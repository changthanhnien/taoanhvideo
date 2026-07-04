import asyncio
import os
import time
import tempfile
from utils.logger import log
from playwright.async_api import Page

class GrokClient:
    def __init__(self, page: Page, cookie_path=None, account_email: str | None = None):
        self._page = page
        self._cookie_path = cookie_path
        self._account_email = account_email or "?"

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
            
            # Keep only the session token cookies and clear all other cookies
            cookies = await self._page.context.cookies()
            keep_names = ["sso", "x-sso-jwt", "auth_token", "ct0", "twid", "personalization_id", "guest_id", "guest_id_marketing", "guest_id_ads"]
            to_delete = [c for c in cookies if c["name"] not in keep_names]
            if to_delete:
                await self._page.context.clear_cookies()
                # Restore only the session cookies
                to_restore = [c for c in cookies if c["name"] in keep_names]
                if to_restore:
                    await self._page.context.add_cookies(to_restore)
            log.info(f"GrokClient: Cleaned site data and non-essential cookies for {self._account_email}")
        except Exception as e:
            log.warning(f"GrokClient: Failed to clear non-essential state: {e}")

    async def _wait_for_imagine_ready(self) -> bool:
        """Wait up to 180 seconds for the Grok Imagine input box to become visible.
        This gives the user time to manually solve any login or captcha verification prompts.
        """
        log.info("GrokClient: Checking if Grok Imagine page is ready...")
        selectors = ["textarea[placeholder*='imagine']", "textarea[placeholder*='tưởng tượng']", "textarea", "div[contenteditable='true']"]
        
        for i in range(90):  # 90 iterations * 2 seconds = 180 seconds
            for sel in selectors:
                try:
                    loc = self._page.locator(sel).first
                    if await loc.is_visible() and await loc.is_enabled():
                        log.info("GrokClient: Imagine input ready. Continuing...")
                        return True
                except Exception:
                    pass
            
            current_url = self._page.url or ""
            is_blocked = "verify" in current_url or "login" in current_url or "challenge" in current_url or "x.com" in current_url
            
            if is_blocked:
                log.info(f"GrokClient: [Xác minh / Verify] Cửa sổ yêu cầu đăng nhập hoặc captcha đang hiện diện. URL hiện tại: {current_url}. Hãy hoàn thành thao tác trên trình duyệt. Đang đợi bạn giải xác minh ({i*2}s/180s)...")
            else:
                log.info(f"GrokClient: Đang đợi trang tải... ({i*2}s/180s)")
                
            await asyncio.sleep(2)
            
        return False

    async def generate_image(self, prompt: str, image_paths=None, aspect_ratio: str = "16:9", grok_mode: str = "Tốc độ", output_dir: str = "", count: int = 1, callback=None) -> list[str]:
        log.info(f"GrokClient: Navigating to https://grok.com/imagine for account {self._account_email}...")
        
        # 1. Navigate
        if "grok.com/imagine" not in (self._page.url or ""):
            await self._page.goto("https://grok.com/imagine", wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(4)

        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    log.info("GrokClient: Image generation failed, cleaning cookies/storage, reloading page (F5) and retrying...")
                    try:
                        await self._clear_non_essential_state()
                    except Exception as ce:
                        log.warning(f"GrokClient: Failed to clean state on retry: {ce}")
                    await self._page.reload(wait_until="domcontentloaded", timeout=45000)
                    await asyncio.sleep(4)

                # Wait for user to bypass login/captcha if present
                ready = await self._wait_for_imagine_ready()
                if not ready:
                    raise RuntimeError("Grok Imagine page failed to load or verification timed out after 180 seconds.")

                # Try to dismiss cookie consent banner if present
                try:
                    accept_btn = self._page.locator("#onetrust-accept-btn-handler, button:has-text('Accept All'), button:has-text('Accept All Cookies'), button:has-text('Đồng ý tất cả')").first
                    if await accept_btn.is_visible():
                        log.info("GrokClient: Dismissing cookie banner...")
                        await accept_btn.click()
                        await asyncio.sleep(1.5)
                except Exception:
                    pass
                    
                # Try to dismiss any popup promo modals
                try:
                    await self._page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)
                    dismiss_btn = self._page.locator("button:has-text('Dismiss'), button:has-text('Bỏ qua'), button:has-text('Đóng')").first
                    if await dismiss_btn.is_visible():
                        log.info("GrokClient: Dismissing popup modal...")
                        await dismiss_btn.click()
                        await asyncio.sleep(1)
                except Exception:
                    pass
                    
                # 2. Select "Image" mode if not already active
                try:
                    image_btn = None
                    for text in ["Image", "Hình ảnh", "Hình Ảnh"]:
                        btn = self._page.get_by_text(text, exact=False).first
                        if await btn.is_visible():
                            image_btn = btn
                            break
                    if image_btn:
                        await image_btn.click()
                        await asyncio.sleep(1)
                except Exception as e:
                    log.warning(f"Could not click Image mode button: {e}")

                # 3. Select grok_mode ("Speed" / "Tốc độ" or "Quality" / "Chất lượng")
                try:
                    if grok_mode in ("Tốc độ", "Speed"):
                        target_texts = ["Speed", "speed", "Tốc độ", "tốc độ"]
                    else:
                        target_texts = ["Quality", "quality", "Chất lượng", "chất lượng"]
                        
                    mode_btn = None
                    for text in target_texts:
                        loc = self._page.get_by_text(text, exact=True)
                        for idx in range(await loc.count()):
                            el = loc.nth(idx)
                            if await el.is_visible():
                                mode_btn = el
                                break
                        if mode_btn:
                            break
                    if mode_btn:
                        await mode_btn.click()
                        await asyncio.sleep(1)
                    else:
                        log.warning(f"Could not find button for grok_mode '{grok_mode}'")
                except Exception as e:
                    log.warning(f"Could not select grok_mode '{grok_mode}': {e}")

                # 4. Select aspect ratio
                try:
                    current_ratio = None
                    for r in ["2:3", "3:2", "1:1", "9:16", "16:9"]:
                        btn = self._page.get_by_text(r, exact=True).first
                        if await btn.is_visible():
                            current_ratio = r
                            break
                    
                    if current_ratio and current_ratio != aspect_ratio:
                        btn = self._page.get_by_text(current_ratio, exact=True).first
                        await btn.click()
                        await asyncio.sleep(1)
                        
                        target_option = None
                        for selector in [
                            f"button:has-text('{aspect_ratio}')",
                            f"li:has-text('{aspect_ratio}')",
                            f"div:has-text('{aspect_ratio}')",
                        ]:
                            loc = self._page.locator(selector)
                            count = await loc.count()
                            for i in range(count):
                                el = loc.nth(i)
                                text = await el.text_content() or ""
                                if aspect_ratio in text and any(w in text for w in ["Cao", "Rộng", "Vuông", "Dọc", "Màn hình rộng", "Tall", "Wide", "Square", "Vertical", "Widescreen"]):
                                    target_option = el
                                    break
                            if target_option:
                                break
                        
                        if not target_option:
                            target_option = self._page.get_by_text(aspect_ratio, exact=False).last
                        
                        if target_option and await target_option.is_visible():
                            await target_option.click()
                            await asyncio.sleep(1)
                            log.info(f"Successfully selected aspect ratio '{aspect_ratio}'")
                        else:
                            log.warning(f"Target aspect ratio option '{aspect_ratio}' is not visible")
                    elif current_ratio == aspect_ratio:
                        log.info(f"Aspect ratio '{aspect_ratio}' is already selected")
                except Exception as e:
                    log.warning(f"Could not select aspect ratio '{aspect_ratio}': {e}")

                # 5. Upload reference image (Image -> Image mode)
                if image_paths and len(image_paths) > 0:
                    try:
                        file_input = self._page.locator("input[type='file']")
                        if await file_input.count() > 0:
                            log.info(f"Uploading images: {image_paths}")
                            await file_input.set_input_files(image_paths)
                            wait_time = max(3.0, 3.0 * len(image_paths))
                            await asyncio.sleep(wait_time)
                    except Exception as e:
                        log.warning(f"Could not upload image: {e}")

                # 6. Record existing images on the page
                existing_srcs = set()
                image_elements = self._page.locator("img")
                for idx in range(await image_elements.count()):
                    src = await image_elements.nth(idx).get_attribute("src")
                    if src:
                        existing_srcs.add(src)

                # 7. Modify prompt tags if reference images are present
                modified_prompt = prompt
                if image_paths and len(image_paths) > 0:
                    for idx in range(len(image_paths)):
                        luma_tag = f"@{idx + 1}"
                        grok_tag = f"@Image {idx + 1}"
                        if luma_tag in modified_prompt:
                            modified_prompt = modified_prompt.replace(luma_tag, grok_tag)
                    if not any(f"@Image {i+1}" in modified_prompt for i in range(len(image_paths))):
                        modified_prompt += f" @Image 1"

                # 8. Focus and fill the prompt input textarea
                prompt_input = None
                for sel in ["textarea[placeholder*='imagine']", "textarea[placeholder*='tưởng tượng']", "textarea", "div[contenteditable='true']"]:
                    loc = self._page.locator(sel).first
                    if await loc.is_visible() and await loc.is_enabled():
                        prompt_input = loc
                        break

                if not prompt_input:
                    raise RuntimeError("Could not find Grok Imagine prompt input box.")

                await prompt_input.click()
                await prompt_input.fill("")
                await prompt_input.fill(modified_prompt)
                await asyncio.sleep(1)

                # 9. Submit
                submit_btn = None
                for sel in ["button[type='submit']", "button:has(svg)", "button:has-text('Tạo')"]:
                    btns = self._page.locator(sel)
                    for idx in range(await btns.count()):
                        btn = btns.nth(idx)
                        if await btn.is_visible() and await btn.is_enabled():
                            submit_btn = btn
                            break
                    if submit_btn:
                        break

                if submit_btn:
                    await submit_btn.click()
                else:
                    await prompt_input.press("Enter")
                log.info("Prompt submitted to Grok. Waiting for generation...")
                await asyncio.sleep(1)

                # 10. Wait for new generated images to be fully loaded
                start_time = time.time()
                new_image_srcs = []
                existing_srcs_list = list(existing_srcs)
                
                js_check = """
                (existing) => {
                    const hasBlur = (img) => {
                        let parent = img.parentElement;
                        for (let i = 0; i < 4; i++) {
                            if (!parent) break;
                            try {
                                const style = window.getComputedStyle(parent);
                                if (style.filter && style.filter.toLowerCase().includes('blur')) return true;
                            } catch (e) {}
                            const pClasses = (parent.className || "").toString().toLowerCase();
                            if (
                                pClasses.includes('blur') || 
                                pClasses.includes('loading') || 
                                pClasses.includes('generating') ||
                                pClasses.includes('pulse')
                            ) {
                                return true;
                            }
                            parent = parent.parentElement;
                        }
                        return false;
                    };

                    const imgs = Array.from(document.querySelectorAll('img'));
                    return imgs
                        .filter(img => {
                            const src = img.src || "";
                            if (existing.includes(src)) return false;
                            if (!src.startsWith('http') && !src.startsWith('data:image/')) return false;
                            if (src.includes('blob:') || src.includes('svg')) return false;
                            if (hasBlur(img)) return false;
                            return img.complete && img.naturalWidth > 500;
                        })
                        .map(img => img.src);
                }
                """
                
                while time.time() - start_time < 120:
                    if self._page.is_closed():
                        raise RuntimeError("Trình duyệt hoặc tab đã bị đóng bởi người dùng.")
                    try:
                        temp_new_srcs = await self._page.evaluate(js_check, existing_srcs_list)
                        if temp_new_srcs and len(temp_new_srcs) > 0:
                            await asyncio.sleep(0.5)
                            new_image_srcs = await self._page.evaluate(js_check, existing_srcs_list)
                            break
                    except Exception as e:
                        err_msg = str(e).lower()
                        if "closed" in err_msg or "target closed" in err_msg or "connection closed" in err_msg:
                            raise RuntimeError("Trình duyệt hoặc tab đã bị đóng bởi người dùng.")
                        log.warning(f"Error checking page images: {e}")
                    await asyncio.sleep(1)

                if not new_image_srcs:
                    raise RuntimeError("Timeout waiting for Grok to generate images.")

                log.info(f"Detected {len(new_image_srcs)} new images generated by Grok.")
                downloaded_paths = []
                
                # 11. Download image files
                download_count = max(4, count)
                for idx, src_url in enumerate(new_image_srcs[:download_count]):
                    try:
                        if src_url.startswith("data:image/"):
                            header, encoded = src_url.split(",", 1)
                            import base64
                            data = base64.b64decode(encoded)
                            ext = ".jpg"
                            if "webp" in header:
                                ext = ".webp"
                            temp_dir = tempfile.gettempdir()
                            filename = f"grok_image_{int(time.time())}_{idx}{ext}"
                            temp_path = os.path.join(temp_dir, filename)
                            with open(temp_path, "wb") as f:
                                f.write(data)
                            if callback:
                                await callback(temp_path)
                            downloaded_paths.append(temp_path)
                            log.info(f"Decoded base64 image to {temp_path}")
                        else:
                            response = await self._page.request.get(src_url)
                            if response.ok:
                                temp_dir = tempfile.gettempdir()
                                filename = f"grok_image_{int(time.time())}_{idx}.jpg"
                                temp_path = os.path.join(temp_dir, filename)
                                with open(temp_path, "wb") as f:
                                    f.write(await response.body())
                                if callback:
                                    await callback(temp_path)
                                downloaded_paths.append(temp_path)
                                log.info(f"Downloaded image to {temp_path}")
                            else:
                                log.warning(f"Failed to download image: HTTP {response.status}")
                    except Exception as e:
                        log.error(f"Error downloading image: {e}")
                        
                return downloaded_paths
            except Exception as e:
                err_msg = str(e).lower()
                if "closed" in err_msg or "target closed" in err_msg or "connection closed" in err_msg:
                    raise e
                if attempt < max_attempts - 1:
                    log.warning(f"Image generation failed on attempt {attempt+1}: {e}. Retrying after F5...")
                    continue
                else:
                    raise e

    async def generate_video(self, prompt: str, image_paths=None, aspect_ratio: str = "16:9", quality: str = "720p", duration: str = "6s", output_dir: str = "", callback=None) -> list[str]:
        log.info(f"GrokClient: Navigating to https://grok.com/imagine for account {self._account_email}...")
        
        # 1. Navigate
        if "grok.com/imagine" not in (self._page.url or ""):
            await self._page.goto("https://grok.com/imagine", wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(4)

        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    log.info("GrokClient: Video generation failed, cleaning cookies/storage, reloading page (F5) and retrying...")
                    try:
                        await self._clear_non_essential_state()
                    except Exception as ce:
                        log.warning(f"GrokClient: Failed to clean state on retry: {ce}")
                    await self._page.reload(wait_until="domcontentloaded", timeout=45000)
                    await asyncio.sleep(4)

                # Wait for user to bypass login/captcha if present
                ready = await self._wait_for_imagine_ready()
                if not ready:
                    raise RuntimeError("Grok Imagine page failed to load or verification timed out after 180 seconds.")

                # Try to dismiss cookie consent banner if present
                try:
                    accept_btn = self._page.locator("#onetrust-accept-btn-handler, button:has-text('Accept All'), button:has-text('Accept All Cookies'), button:has-text('Đồng ý tất cả')").first
                    if await accept_btn.is_visible():
                        log.info("GrokClient: Dismissing cookie banner...")
                        await accept_btn.click()
                        await asyncio.sleep(1.5)
                except Exception:
                    pass
                    
                # Try to dismiss any popup promo modals
                try:
                    await self._page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)
                    dismiss_btn = self._page.locator("button:has-text('Dismiss'), button:has-text('Bỏ qua'), button:has-text('Đóng')").first
                    if await dismiss_btn.is_visible():
                        log.info("GrokClient: Dismissing popup modal...")
                        await dismiss_btn.click()
                        await asyncio.sleep(1)
                except Exception:
                    pass
                    
                # 2. Select "Video" mode if not already active
                try:
                    video_btn = None
                    for text in ["Video", "video"]:
                        btn = self._page.get_by_text(text, exact=True).first
                        if await btn.is_visible():
                            video_btn = btn
                            break
                    if video_btn:
                        await video_btn.click()
                        await asyncio.sleep(1)
                except Exception as e:
                    log.warning(f"Could not click Video mode button: {e}")

                # 3. Choose duration (6s or 10s)
                try:
                    target_btn = None
                    for text in [duration, f"{duration}s", duration.replace("s", "")]:
                        btn = self._page.get_by_text(text, exact=True).first
                        if await btn.is_visible():
                            target_btn = btn
                            break
                    if target_btn:
                        await target_btn.click()
                        await asyncio.sleep(1)
                    else:
                        log.warning(f"Could not find duration button for {duration}")
                except Exception as e:
                    log.warning(f"Could not select duration: {e}")

                # 4. Choose Quality/Resolution (480p or 720p)
                try:
                    target_btn = None
                    for text in [quality, f"Grok ({quality})"]:
                        btn = self._page.get_by_text(text, exact=True).first
                        if await btn.is_visible():
                            target_btn = btn
                            break
                    if target_btn:
                        await target_btn.click()
                        await asyncio.sleep(1)
                    else:
                        log.warning(f"Could not find quality button for {quality}")
                except Exception as e:
                    log.warning(f"Could not select quality: {e}")

                # 5. Select aspect ratio
                try:
                    current_ratio = None
                    for r in ["2:3", "3:2", "1:1", "9:16", "16:9"]:
                        btn = self._page.get_by_text(r, exact=True).first
                        if await btn.is_visible():
                            current_ratio = r
                            break
                    
                    if current_ratio and current_ratio != aspect_ratio:
                        btn = self._page.get_by_text(current_ratio, exact=True).first
                        await btn.click()
                        await asyncio.sleep(1)
                        
                        # Locate the option in the dropdown
                        target_option = None
                        for selector in [
                            f"button:has-text('{aspect_ratio}')",
                            f"li:has-text('{aspect_ratio}')",
                            f"div:has-text('{aspect_ratio}')",
                        ]:
                            loc = self._page.locator(selector)
                            count = await loc.count()
                            for i in range(count):
                                el = loc.nth(i)
                                text = await el.text_content() or ""
                                if aspect_ratio in text and any(w in text for w in ["Cao", "Rộng", "Vuông", "Dọc", "Màn hình rộng", "Tall", "Wide", "Square", "Vertical", "Widescreen"]):
                                    target_option = el
                                    break
                            if target_option:
                                break
                        
                        if not target_option:
                            target_option = self._page.get_by_text(aspect_ratio, exact=False).last
                        
                        if target_option and await target_option.is_visible():
                            await target_option.click()
                            await asyncio.sleep(1)
                            log.info(f"Successfully selected aspect ratio '{aspect_ratio}'")
                        else:
                            log.warning(f"Target aspect ratio option '{aspect_ratio}' is not visible")
                except Exception as e:
                    log.warning(f"Could not select aspect ratio '{aspect_ratio}': {e}")

                # 6. Upload reference image (Image -> Video mode)
                if image_paths and len(image_paths) > 0:
                    try:
                        file_input = self._page.locator("input[type='file']")
                        if await file_input.count() > 0:
                            log.info(f"Uploading images: {image_paths}")
                            await file_input.set_input_files(image_paths)
                            wait_time = max(3.0, 3.0 * len(image_paths))
                            await asyncio.sleep(wait_time)
                    except Exception as e:
                        log.warning(f"Could not upload image: {e}")

                # 7. Record existing videos on the page to distinguish new ones
                existing_srcs = set()
                video_elements = self._page.locator("video")
                for idx in range(await video_elements.count()):
                    src = await video_elements.nth(idx).get_attribute("src")
                    if src:
                        existing_srcs.add(src)

                # Translate Luma-style tags (@1, @2) to Grok-style tags (@Image 1, @Image 2)
                modified_prompt = prompt
                if image_paths and len(image_paths) > 0:
                    for idx in range(len(image_paths)):
                        luma_tag = f"@{idx + 1}"
                        grok_tag = f"@Image {idx + 1}"
                        if luma_tag in modified_prompt:
                            modified_prompt = modified_prompt.replace(luma_tag, grok_tag)
                    
                    if not any(f"@Image {i+1}" in modified_prompt for i in range(len(image_paths))):
                        modified_prompt += f" @Image 1"

                # 8. Focus and fill the prompt input textarea
                prompt_input = None
                for sel in ["textarea[placeholder*='imagine']", "textarea[placeholder*='tưởng tượng']", "textarea", "div[contenteditable='true']"]:
                    loc = self._page.locator(sel).first
                    if await loc.is_visible() and await loc.is_enabled():
                        prompt_input = loc
                        break

                if not prompt_input:
                    raise RuntimeError("Could not find Grok Imagine prompt input box.")

                await prompt_input.click()
                await prompt_input.fill("")
                await prompt_input.fill(modified_prompt)
                await asyncio.sleep(1)

                # 9. Submit
                submit_btn = None
                for sel in ["button[type='submit']", "button:has(svg)", "button:has-text('Tạo')"]:
                    btns = self._page.locator(sel)
                    for idx in range(await btns.count()):
                        btn = btns.nth(idx)
                        if await btn.is_visible() and await btn.is_enabled():
                            submit_btn = btn
                            break
                    if submit_btn:
                        break
                        
                if submit_btn:
                    await submit_btn.click()
                else:
                    await prompt_input.press("Enter")
                log.info("Prompt submitted to Grok (Video). Waiting for generation...")
                await asyncio.sleep(1)

                # 10. Wait for new generated videos to be fully loaded
                start_time = time.time()
                new_video_srcs = []
                existing_srcs_list = list(existing_srcs)
                
                js_check = """
                (existing) => {
                    const hasBlur = (vid) => {
                        let parent = vid.parentElement;
                        for (let i = 0; i < 4; i++) {
                            if (!parent) break;
                            try {
                                const style = window.getComputedStyle(parent);
                                if (style.filter && style.filter.toLowerCase().includes('blur')) return true;
                            } catch (e) {}
                            const pClasses = (parent.className || "").toString().toLowerCase();
                            if (pClasses.includes('blur') || pClasses.includes('loading') || pClasses.includes('generating')) return true;
                            parent = parent.parentElement;
                        }
                        return false;
                    };

                    const vids = Array.from(document.querySelectorAll('video'));
                    return vids
                        .filter(vid => {
                            const src = vid.src || "";
                            if (existing.includes(src)) return false;
                            if (!src.startsWith('http') && !src.startsWith('blob:')) return false;
                            if (hasBlur(vid)) return false;
                            return vid.readyState >= 2;
                        })
                        .map(vid => vid.src);
                }
                """
                
                while time.time() - start_time < 180:
                    if self._page.is_closed():
                        raise RuntimeError("Trình duyệt hoặc tab đã bị đóng bởi người dùng.")
                    try:
                        temp_new_srcs = await self._page.evaluate(js_check, existing_srcs_list)
                        if temp_new_srcs and len(temp_new_srcs) > 0:
                            await asyncio.sleep(0.5)
                            new_video_srcs = await self._page.evaluate(js_check, existing_srcs_list)
                            break
                    except Exception as e:
                        err_msg = str(e).lower()
                        if "closed" in err_msg or "target closed" in err_msg or "connection closed" in err_msg:
                            raise RuntimeError("Trình duyệt hoặc tab đã bị đóng bởi người dùng.")
                        log.warning(f"Error checking page videos: {e}")
                    await asyncio.sleep(1)

                if not new_video_srcs:
                    raise RuntimeError("Timeout waiting for Grok to generate videos.")

                log.info(f"Detected {len(new_video_srcs)} new videos generated by Grok.")
                downloaded_paths = []
                
                # 11. Download video files
                for idx, src_url in enumerate(new_video_srcs):
                    try:
                        log.info(f"GrokClient: Downloading video {idx} from {src_url}...")
                        if src_url.startswith("blob:"):
                            # Use browser fetch for blob URLs (local to browser context)
                            try:
                                js_download = """
                                async (url) => {
                                    const response = await fetch(url);
                                    const blob = await response.blob();
                                    return new Promise((resolve) => {
                                        const reader = new FileReader();
                                        reader.onloadend = () => resolve(reader.result);
                                        reader.readAsDataURL(blob);
                                    });
                                }
                                """
                                data_url = await self._page.evaluate(js_download, src_url)
                                header, encoded = data_url.split(",", 1)
                                import base64
                                data = base64.b64decode(encoded)
                                
                                temp_dir = tempfile.gettempdir()
                                filename = f"grok_video_{int(time.time())}_{idx}.mp4"
                                temp_path = os.path.join(temp_dir, filename)
                                with open(temp_path, "wb") as f:
                                    f.write(data)
                                
                                if callback:
                                    await callback(temp_path)
                                downloaded_paths.append(temp_path)
                                log.info(f"Downloaded blob video to {temp_path}")
                            except Exception as js_ex:
                                log.error(f"Failed to download blob video: {js_ex}")
                        else:
                            # Use backend client request for http/https URLs to bypass CORS completely
                            response = await self._page.request.get(src_url)
                            if response.ok:
                                temp_dir = tempfile.gettempdir()
                                filename = f"grok_video_{int(time.time())}_{idx}.mp4"
                                temp_path = os.path.join(temp_dir, filename)
                                with open(temp_path, "wb") as f:
                                    f.write(await response.body())
                                
                                if callback:
                                    await callback(temp_path)
                                    
                                downloaded_paths.append(temp_path)
                                log.info(f"Downloaded http video to {temp_path}")
                            else:
                                log.warning(f"Failed to download video via request: HTTP {response.status}")
                    except Exception as e:
                        log.error(f"Error downloading video: {e}")
                        
                return downloaded_paths
            except Exception as e:
                err_msg = str(e).lower()
                if "closed" in err_msg or "target closed" in err_msg or "connection closed" in err_msg:
                    raise e
                if attempt < max_attempts - 1:
                    log.warning(f"Video generation failed on attempt {attempt+1}: {e}. Retrying after F5...")
                    continue
                else:
                    raise e
