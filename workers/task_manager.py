"""Background task manager."""

from __future__ import annotations

import time
import asyncio
import os
import httpx
from pathlib import Path
from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, Signal

from services.flow_client import FlowClient
from config.constants import TaskMode, ItemStatus, DEFAULT_IMAGE_OUTPUT, DEFAULT_VIDEO_OUTPUT
from utils.logger import log


class WorkerSignals(QObject):
    task_started = Signal(int)
    task_completed = Signal(int)
    task_error = Signal(int, str)
    task_progress = Signal(int, int, int)
    item_status_changed = Signal(int, str)
    item_completed = Signal(int, str)
    item_error = Signal(int, str)
    credit_updated = Signal(int, int)
    account_disabled = Signal(int, str, str)


class AccountPool:
    _counts = {}
    _exhausted = set()

    def __init__(self, db, account_type="google"):
        self.db = db
        self.account_type = account_type

    def acquire(self, max_per_account: int = 1):
        import os
        accounts = self.db.get_accounts(enabled_only=True, account_type=self.account_type) if self.db else []
        for account in accounts:
            if account.id in AccountPool._exhausted:
                continue
            # Validate that the browser profile directory actually exists
            if not account.cookie_path or not os.path.exists(account.cookie_path):
                log.warning("AccountPool: Skipping account {} because its profile directory does not exist: {}".format(account.email, account.cookie_path))
                continue
            count = AccountPool._counts.get(account.id, 0)
            if count < max_per_account:
                AccountPool._counts[account.id] = count + 1
                return account
        return None

    def release(self, account):
        if account:
            count = AccountPool._counts.get(account.id, 0)
            if count > 0:
                AccountPool._counts[account.id] = count - 1

    def mark_exhausted(self, account):
        if account:
            AccountPool._exhausted.add(account.id)
            self.release(account)

    def available_count(self):
        try:
            accounts = self.db.get_accounts(enabled_only=True, account_type=self.account_type)
            return len([a for a in accounts if a.id not in self._exhausted])
        except Exception:
            return 0


class TaskWorker(QThread):
    def __init__(self, task, db=None, browser_manager=None, account_pool=None, parent=None):
        super().__init__(parent)
        self.task = task
        self.db = db
        self.browser_manager = browser_manager
        self.account_pool = account_pool
        self.signals = WorkerSignals()
        self._cancelled = False
        self._paused = False

    def _cancellable_sleep(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            if self._cancelled:
                return False
            time.sleep(0.1)
        return True

    def cancel(self):
        self._cancelled = True

    def _schedule_close(self):
        return None

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def run(self):
        try:
            asyncio.run(self._async_execute())
        except Exception as e:
            self.signals.task_error.emit(getattr(self.task, "id", 0), str(e))

    async def _async_execute(self):
        from automation.browser_manager import BrowserManager
        import logging
        log = logging.getLogger("navtools")
        local_browser_manager = BrowserManager()
        
        task_id = getattr(self.task, "id", 0)
        self.signals.task_started.emit(task_id)
        items = getattr(self.task, "items", []) or []
        total = len(items)
        
        delay = getattr(self.task, "delay", 0) or 0
        if delay == 0 and hasattr(self.task, "config") and self.task.config:
            import json
            try:
                cfg = json.loads(self.task.config)
                delay = cfg.get("delay", 0)
            except Exception:
                pass
        
        try:
            # Group items into batches
            batches = []
            current_batch = []
            mode = getattr(self.task, "mode", TaskMode.IMAGE)
            max_batch_size = 1 if mode in (TaskMode.GROK_IMAGE, TaskMode.GROK_VIDEO) else 4
            
            def get_group_key(item):
                p = getattr(item, "prompt", "")
                r = getattr(item, "reference_image", "")
                s = getattr(item, "start_frame", "")
                e = getattr(item, "end_frame", "")
                return (p, r, s, e)

            for item in items:
                if not current_batch:
                    current_batch.append(item)
                else:
                    if len(current_batch) < max_batch_size and get_group_key(item) == get_group_key(current_batch[0]):
                        current_batch.append(item)
                    else:
                        batches.append(current_batch)
                        current_batch = [item]
            if current_batch:
                batches.append(current_batch)

            # NEW ARCHITECTURE
            browser_concurrency = getattr(self.task, "concurrent", 1) or 1
            if browser_concurrency <= 0: browser_concurrency = 1
            
            account_concurrency = 1
            
            self._task_account_lock = asyncio.Lock()
            self._current_account = None
            
            max_per_acc = 1 if mode in (TaskMode.GROK_IMAGE, TaskMode.GROK_VIDEO) else (getattr(self.task, "parallel_per_account", 1) or 1)
            
            async def get_account():
                async with self._task_account_lock:
                    if self._current_account is None:
                        acc = self.account_pool.acquire(max_per_acc)
                        wait_time = 0
                        while not acc and not self._cancelled:
                            if wait_time % 10 == 0:
                                log.warning("Task {}: Waiting for available {} account... (waited {}s)".format(task_id, self.account_pool.account_type, wait_time))
                            if wait_time >= 30:
                                raise RuntimeError("Không có tài khoản {} nào khả dụng hoặc hồ sơ trình duyệt đã bị xóa.".format(self.account_pool.account_type))
                            await asyncio.sleep(2)
                            wait_time += 2
                            acc = self.account_pool.acquire(max_per_acc)
                        self._current_account = acc
                    return self._current_account
                    
            async def rotate_account(old_acc):
                async with self._task_account_lock:
                    if self._current_account and self._current_account.email == old_acc.email:
                        log.info("Task {}: Account {} exhausted, rotating...".format(task_id, old_acc.email))
                        self.account_pool.mark_exhausted(self._current_account)
                        self.account_pool.release(self._current_account)
                        self._current_account = None
                        acc = self.account_pool.acquire(max_per_acc)
                        wait_time = 0
                        while not acc and not self._cancelled:
                            if wait_time % 10 == 0:
                                log.warning("Task {}: Waiting for available {} account during rotation... (waited {}s)".format(task_id, self.account_pool.account_type, wait_time))
                            if wait_time >= 20:
                                raise RuntimeError("Hết tài khoản {} khả dụng để luân phiên.".format(self.account_pool.account_type))
                            await asyncio.sleep(2)
                            wait_time += 2
                            acc = self.account_pool.acquire(max_per_acc)
                        self._current_account = acc
                    return self._current_account

            sem = asyncio.Semaphore(browser_concurrency)
            self._browser_ctx_lock = asyncio.Lock()
            
            async def worker(index, batch):
                async with sem:
                    if self._cancelled:
                        return
                    while self._paused and not self._cancelled:
                        await asyncio.sleep(0.2)
                    
                    item_ids = [getattr(it, "id", 0) for it in batch]
                    
                    actual_delay = (index // max_batch_size) * delay
                    if actual_delay > 0 and not self._cancelled:
                        log.info("Delay {}s before starting batch {}...".format(actual_delay, item_ids))
                        await asyncio.sleep(actual_delay)
                    max_retries = 3
                    fatal_keywords = [
                        "quota", "permission", "denied", "blocked",
                        "policy", "unsafe", "không an toàn", "bị chặn",
                        "cancelled", "video gen failed", "exhausted", "limit"
                    ]
                    
                    retry_count = 0
                    while retry_count < max_retries:
                        if self._cancelled:
                            return
                            
                        account = await get_account()
                        if not account:
                            return
                            
                        try:
                            await self._async_process_batch(batch, local_browser_manager, account)
                            break  # Success
                        except Exception as e:
                            err_str = str(e)
                            log.error("Error processing batch {} (attempt {}/{}): {}".format(item_ids, retry_count+1, max_retries, err_str))
                            
                            all_exist = True
                            for it in batch:
                                out_path = getattr(it, "output_path", None)
                                if out_path and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                                    it_id = getattr(it, "id", 0)
                                    log.info("Item {}: output exists despite error, marking completed".format(it_id))
                                    self.signals.item_completed.emit(it_id, out_path)
                                else:
                                    all_exist = False
                            if all_exist:
                                break
                            
                            is_fatal = any(kw.lower() in err_str.lower() for kw in fatal_keywords)
                            
                            if is_fatal and any(k in err_str.lower() for k in ["quota", "exhausted", "limit", "failed", "invalid"]):
                                log.info("Batch {}: Requesting account rotation for {}...".format(item_ids, account.email))
                                for it_id in item_ids:
                                    self.signals.item_status_changed.emit(it_id, "GENERATING")
                                await rotate_account(account)
                                await asyncio.sleep(2)
                                continue 
                            
                            retry_count += 1
                            if is_fatal or retry_count >= max_retries:
                                if self.db:
                                    for it_id in item_ids:
                                        self.db.update_item_status(it_id, ItemStatus.ERROR, error_message=err_str)
                                for it_id in item_ids:
                                    self.signals.item_error.emit(it_id, err_str)
                                break
                            else:
                                log.info("Batch {}: retrying in 5s...".format(item_ids))
                                for it_id in item_ids:
                                    self.signals.item_status_changed.emit(it_id, "GENERATING")
                                await asyncio.sleep(5)
                    
                    self.signals.task_progress.emit(task_id, index + len(batch), total)

            tasks = []
            processed = 0
            for batch in batches:
                tasks.append(asyncio.create_task(worker(processed, batch)))
                processed += len(batch)
                
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, r in enumerate(results):
                    if isinstance(r, Exception):
                        err_msg = str(r)
                        log.error("Worker {} threw unhandled exception: {}".format(i+1, err_msg))
                        err_batch = batches[i]
                        for it in err_batch:
                            item_id = getattr(it, "id", 0)
                            if self.db:
                                self.db.update_item_status(item_id, ItemStatus.ERROR, error_message=err_msg)
                            self.signals.item_error.emit(item_id, err_msg)
        finally:
            if getattr(self, "_current_account", None):
                self.account_pool.release(self._current_account)
        self.signals.task_completed.emit(task_id)

    def _execute(self):
        pass

    def _run_one(self, item):
        pass

    async def _download_file(self, url: str, output_path: str):
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)

    async def _async_process_batch(self, batch, local_browser_manager, account):
        import logging
        log = logging.getLogger("navtools")
        if not batch: return
        item_ids = [getattr(it, "id", 0) for it in batch]
        for it_id in item_ids:
            self.signals.item_status_changed.emit(it_id, "GENERATING")
            
        generation_quantity = len(batch)
        browser_concurrency = getattr(self.task, "concurrent", 1) or 1
        account_concurrency = 1
        
        try:
            async with self._browser_ctx_lock:
                context = await local_browser_manager.get_or_create_context(
                    account.id, account.email, account.proxy, account.cookie_path
                )
            # Reuse the first page if available to avoid leaving about:blank open!
            pages = context.pages
            if pages:
                page = pages[0]
            else:
                page = await context.new_page()
            
            try:
                client = FlowClient(page, account.cookie_path, account.email)
                
                mode = getattr(self.task, "mode", TaskMode.IMAGE)
                first_item = batch[0]
                prompt = getattr(first_item, "prompt", "")
                
                image_paths = []
                ref_img = getattr(first_item, "reference_image", None)
                if ref_img and os.path.exists(ref_img):
                    image_paths.append(ref_img)
                    
                start_frame = getattr(first_item, "start_frame", None)
                end_frame = getattr(first_item, "end_frame", None)
                
                quality = getattr(self.task, "quality", "Veo 3.1 - Fast")
                aspect_ratio = getattr(self.task, "aspect_ratio", "16:9")
                image_model = getattr(self.task, "image_model", "") or "Nano Banana 2"
                
                import json
                try:
                    cfg_dict = json.loads(self.task.config) if getattr(self.task, "config", None) else {}
                    dur_str = cfg_dict.get("duration", "8s")
                    duration = int(dur_str.replace("s", ""))
                    creation_mode = cfg_dict.get("creation_mode", "Text -> Video")
                    uploaded_images = cfg_dict.get("uploaded_images", [])
                except Exception:
                    duration = 8
                    creation_mode = "Text -> Video"
                    uploaded_images = []
                    
                if "Text ->" in creation_mode or "Text to" in creation_mode:
                    image_paths = [] 
                elif "Frame" in creation_mode:
                    image_paths = [] 
                    if start_frame and os.path.exists(start_frame):
                        image_paths.append(start_frame)
                    if end_frame and os.path.exists(end_frame):
                        image_paths.append(end_frame)
                elif "Ảnh" in creation_mode or "Anh" in creation_mode:
                    image_paths = [p for p in uploaded_images if os.path.exists(p)]
                    if ref_img and os.path.exists(ref_img) and ref_img not in image_paths:
                        image_paths.insert(0, ref_img)
                    
                project_name = getattr(self.task, "name", "")
                count = len(batch)
                result_urls = []
                
                if mode == TaskMode.GROK_VIDEO:
                    from services.grok_client import GrokClient
                    grok_client = GrokClient(page, account.cookie_path, account.email)
                    
                    reported_count = [0]
                    async def on_grok_video_downloaded(local_path):
                        idx = reported_count[0]
                        it = None
                        if idx < len(batch):
                            it = batch[idx]
                        else:
                            it = batch[-1] if len(batch) > 0 else None
                            
                        if it:
                            it_id = getattr(it, "id", 0)
                            output_dir = getattr(self.task, "output_path", "")
                            if not output_dir or not os.path.exists(output_dir):
                                output_dir = str(DEFAULT_VIDEO_OUTPUT)
                                os.makedirs(output_dir, exist_ok=True)
                                
                            safe_prompt = getattr(it, "prompt", "video")[:20]
                            safe_prompt = "".join(c for c in safe_prompt if c.isalnum() or c in (' ', '-', '_')).strip()
                            if not safe_prompt: safe_prompt = "video"
                            
                            import time
                            suffix = f"_var{idx}" if idx >= len(batch) else ""
                            out_path = os.path.join(output_dir, "{}_{}_{}{}.mp4".format(safe_prompt, it_id, int(time.time()), suffix))
                            
                            try:
                                import shutil
                                shutil.copy2(local_path, out_path)
                                if idx < len(batch):
                                    it.output_path = out_path
                                    if self.db:
                                        self.db.update_item_status(it_id, ItemStatus.COMPLETED, output_path=out_path)
                                    self.signals.item_completed.emit(it_id, out_path)
                                log.info("Saved Grok video to: {}".format(out_path))
                            except Exception as e:
                                log.error("Failed to copy Grok video: {}".format(e))
                                if idx < len(batch) and self.db:
                                    self.db.update_item_status(it_id, ItemStatus.FAILED, error_message=str(e))
                        reported_count[0] += 1

                    try:
                        dur_str = cfg_dict.get("duration", "6s")
                        quality = cfg_dict.get("quality", "720p")
                        
                        await grok_client.generate_video(
                            prompt=prompt,
                            image_paths=image_paths if image_paths else None,
                            aspect_ratio=aspect_ratio,
                            quality=quality,
                            duration=dur_str,
                            output_dir=getattr(self.task, "output_path", ""),
                            callback=on_grok_video_downloaded
                        )
                    except Exception as e:
                        log.error("Grok video generation failed: {}".format(e))
                        for it in batch:
                            it_id = getattr(it, "id", 0)
                            if self.db:
                                self.db.update_item_status(it_id, ItemStatus.FAILED, error_message=str(e))
                    finally:
                        try:
                            await page.close()
                        except Exception:
                            pass
                        try:
                            await local_browser_manager.close_context(account.id)
                        except Exception as ex:
                            log.error(f"Error releasing browser context in grok video finally: {ex}")
                    return

                if mode in (TaskMode.IMAGE, TaskMode.CHAR_IMAGE, TaskMode.GROK_IMAGE):
                    if mode == TaskMode.GROK_IMAGE:
                        from services.grok_client import GrokClient
                        grok_client = GrokClient(page, account.cookie_path, account.email)
                        grok_mode = cfg_dict.get("grok_mode", "Tốc độ")
                        
                        reported_count = [0]
                        async def on_grok_image_downloaded(local_path):
                            idx = reported_count[0]
                            it = None
                            if idx < len(batch):
                                it = batch[idx]
                            else:
                                it = batch[-1] if len(batch) > 0 else None
                                
                            if it:
                                it_id = getattr(it, "id", 0)
                                output_dir = getattr(self.task, "output_path", "")
                                if not output_dir or not os.path.exists(output_dir):
                                    output_dir = str(DEFAULT_IMAGE_OUTPUT)
                                    os.makedirs(output_dir, exist_ok=True)
                                    
                                safe_prompt = getattr(it, "prompt", "image")[:20]
                                safe_prompt = "".join(c for c in safe_prompt if c.isalnum() or c in (' ', '-', '_')).strip()
                                if not safe_prompt: safe_prompt = "image"
                                
                                import time
                                suffix = f"_var{idx}" if idx >= len(batch) else ""
                                out_path = os.path.join(output_dir, "{}_{}_{}{}.jpg".format(safe_prompt, it_id, int(time.time()), suffix))
                                
                                try:
                                    import shutil
                                    shutil.copy2(local_path, out_path)
                                    if idx < len(batch):
                                        it.output_path = out_path
                                        if self.db:
                                            self.db.update_item_status(it_id, ItemStatus.COMPLETED, output_path=out_path)
                                        self.signals.item_completed.emit(it_id, out_path)
                                    log.info("Saved Grok image to: {}".format(out_path))
                                except Exception as e:
                                    log.error("Failed to copy Grok image: {}".format(e))
                                    if idx < len(batch) and self.db:
                                        self.db.update_item_status(it_id, ItemStatus.FAILED, error_message=str(e))
                            reported_count[0] += 1

                        try:
                            await grok_client.generate_image(
                                prompt=prompt,
                                image_paths=image_paths if image_paths else None,
                                aspect_ratio=aspect_ratio,
                                grok_mode=grok_mode,
                                output_dir=getattr(self.task, "output_path", ""),
                                count=count,
                                callback=on_grok_image_downloaded
                            )
                        except Exception as e:
                            log.error("Grok image generation failed: {}".format(e))
                            for it in batch:
                                it_id = getattr(it, "id", 0)
                                if self.db:
                                    self.db.update_item_status(it_id, ItemStatus.FAILED, error_message=str(e))
                        finally:
                            try:
                                await page.close()
                            except Exception:
                                pass
                            try:
                                await local_browser_manager.close_context(account.id)
                            except Exception as ex:
                                log.error(f"Error releasing browser context in grok image finally: {ex}")
                        return

                    reported_count = [0]
                    async def on_new_image(url):
                        idx = reported_count[0]
                        if idx < len(batch):
                            it = batch[idx]
                            it_id = getattr(it, "id", 0)
                            log.info("UI Auto: Streaming image for item {}: {}".format(it_id, url))
                            self.signals.item_status_changed.emit(it_id, "DOWNLOADING")
                            
                            output_dir = getattr(self.task, "output_path", "")
                            if not output_dir or not os.path.exists(output_dir):
                                output_dir = str(DEFAULT_IMAGE_OUTPUT)
                                os.makedirs(output_dir, exist_ok=True)
                                
                            safe_prompt = getattr(it, "prompt", "image")[:20]
                            safe_prompt = "".join(c for c in safe_prompt if c.isalnum() or c in (' ', '-', '_')).strip()
                            if not safe_prompt: safe_prompt = "image"
                            
                            import time
                            out_path = os.path.join(output_dir, "{}_{}_{}.jpg".format(safe_prompt, it_id, int(time.time())))
                            
                            it.output_path = out_path
                            if self.db:
                                self.db.update_item_status(it_id, ItemStatus.GENERATING, output_path=out_path)
                        reported_count[0] += 1
                        
                    result = await client.generate_image(
                        prompt=prompt,
                        image_paths=image_paths if image_paths else None,
                        model=image_model,
                        aspect_ratio=aspect_ratio,
                        project_name=project_name,
                        count=count,
                        callback=on_new_image
                    )
                    if result:
                        if isinstance(result, list):
                            result_urls.extend([r.get("mediaId") or r.get("url") for r in result if isinstance(r, dict)])
                        elif isinstance(result, dict):
                            if "media" in result:
                                for m in result["media"]:
                                    url = m.get("image", {}).get("generatedImage", {}).get("url")
                                    if url:
                                        result_urls.append(url)
                            elif "url" in result:
                                result_urls.append(result["url"])
                            elif "mediaId" in result:
                                result_urls.append(result["mediaId"])
                            elif "name" in result:
                                result_urls.append(result["name"])
                            elif "encodedImage" in result:
                                img_data = result["encodedImage"]
                                if img_data and not img_data.startswith("data:"):
                                    img_data = f"data:image/jpeg;base64,{img_data}"
                                result_urls.append(img_data)
                        
                else: 
                    reported_count = [0]
                    async def on_new_video(url):
                        idx = reported_count[0]
                        if idx < len(batch):
                            it = batch[idx]
                            it_id = getattr(it, "id", 0)
                            log.info("UI Auto: Streaming video for item {}: {}".format(it_id, url))
                            self.signals.item_status_changed.emit(it_id, "DOWNLOADING")
                            
                            output_dir = getattr(self.task, "output_path", "")
                            if not output_dir or not os.path.exists(output_dir):
                                output_dir = str(DEFAULT_VIDEO_OUTPUT)
                                os.makedirs(output_dir, exist_ok=True)
                                
                            safe_prompt = getattr(it, "prompt", "video")[:20]
                            safe_prompt = "".join(c for c in safe_prompt if c.isalnum() or c in (' ', '-', '_')).strip()
                            if not safe_prompt: safe_prompt = "video"
                            
                            import time
                            out_path = os.path.join(output_dir, "{}_{}_{}.mp4".format(safe_prompt, it_id, int(time.time())))
                            
                            if url and url.startswith("data:"):
                                import base64
                                try:
                                    header, encoded = url.split(",", 1)
                                    b64 = base64.b64decode(encoded)
                                    with open(out_path, "wb") as f:
                                        f.write(b64)
                                    log.info(f"UI Auto: Realtime saved video to {out_path} for item {it_id}")
                                    it.output_path = out_path
                                    if self.db:
                                        self.db.update_item_status(it_id, ItemStatus.COMPLETED, output_path=out_path)
                                    self.signals.item_completed.emit(it_id, out_path)
                                except Exception as e:
                                    log.error(f"UI Auto: Failed to save realtime video: {e}")
                                    it.output_path = out_path
                                    if self.db:
                                        self.db.update_item_status(it_id, ItemStatus.GENERATING, output_path=out_path)
                            else:
                                it.output_path = out_path
                                if self.db:
                                    self.db.update_item_status(it_id, ItemStatus.GENERATING, output_path=out_path)
                        reported_count[0] += 1
                    
                    result = await client.generate_video(
                        prompt=prompt,
                        image_paths=image_paths if image_paths else None,
                        model=quality,
                        aspect_ratio=aspect_ratio,
                        project_name=project_name,
                        duration=duration,
                        count=count,
                        callback=on_new_video
                    )
                    
                    if result:
                        if isinstance(result, list):
                            for r in result:
                                result_urls.append(r.get("mediaId") or r.get("name"))
                        else:
                            # result is usually {"media": [...]}
                            media_arr = result.get("media", [])
                            if not media_arr and "result" in result:
                                media_arr = result.get("result", {}).get("media", [])
                                
                            for m in media_arr:
                                img = m.get("image", {}).get("generatedImage", {})
                                url = img.get("url")
                                if url:
                                    result_urls.append(url)
                            
                            # Fallback if result_urls is still empty
                            if not result_urls:
                                for i in range(count):
                                    result_urls.append(result.get("name") or result.get("mediaId"))

                opened_profiles = len(local_browser_manager._browsers) if hasattr(local_browser_manager, '_browsers') else 1
                
                log.info(
                    "\n--- EXECUTION LOG ---\n"
                    "generation_quantity={}\n"
                    "browser_concurrency={}\n"
                    "account_concurrency={}\n"
                    "selected_account={}\n"
                    "opened_profiles={}\n"
                    "flow_batch={}\n"
                    "received={}\n"
                    "---------------------\n".format(
                        generation_quantity,
                        browser_concurrency,
                        account_concurrency,
                        account.email,
                        opened_profiles,
                        count,
                        len(result_urls)
                    )
                )

                if not result_urls:
                    raise RuntimeError("No media/URL received after generation.")
                    
                if self._cancelled:
                    return

                for i, it in enumerate(batch):
                    it_id = getattr(it, "id", 0)
                    
                    if self.db:
                        current_item = self.db.get_item(it_id)
                        if current_item and current_item.status == ItemStatus.COMPLETED and current_item.output_path and os.path.exists(current_item.output_path):
                            continue
                            
                    out_path = getattr(it, "output_path", "")
                    if not out_path:
                        import time
                        ext = ".mp4" if mode == TaskMode.VIDEO else ".jpg"
                        out_dir = DEFAULT_IMAGE_OUTPUT if mode in (TaskMode.IMAGE, TaskMode.CHAR_IMAGE) else DEFAULT_VIDEO_OUTPUT
                        os.makedirs(out_dir, exist_ok=True)
                        out_path = str(out_dir / "result_{}_{}{}".format(it_id, int(time.time()), ext))
                    else:
                        out_path = str(out_path)
                            
                    r_url = result_urls[i] if i < len(result_urls) else result_urls[0]
                    
                    try:
                        os.makedirs(os.path.dirname(out_path), exist_ok=True)
                        if r_url and r_url.startswith("data:"):
                            import base64
                            header, encoded = r_url.split(",", 1)
                            b64 = base64.b64decode(encoded)
                            with open(out_path, "wb") as f:
                                f.write(b64)
                            log.info(f"Saved base64 data URL to {out_path} for item {it_id}")
                            if mode not in (TaskMode.IMAGE, TaskMode.CHAR_IMAGE):
                                self.signals.item_completed.emit(it_id, out_path)
                        elif mode in (TaskMode.IMAGE, TaskMode.CHAR_IMAGE):
                            await self._download_file(r_url, out_path)
                            self.signals.item_status_changed.emit(it_id, "UPSCALE") 
                            log.info("Downloaded image for item {}".format(it_id))
                        else:
                            if r_url.startswith("/fx/api"):
                                full_url = f"https://labs.google{r_url}"
                            elif not r_url.startswith("http"):
                                full_url = f"https://labs.google/fx/api/trpc/media.getMediaUrlRedirect?name={r_url}"
                            else:
                                full_url = r_url

                            log.info(f"Downloading video directly via Playwright: {full_url}")
                            r = await client._page.request.get(full_url, max_redirects=5)
                            if not r.ok:
                                raise RuntimeError(f"HTTP {r.status} khi tải video")
                            
                            content = await r.body()
                            with open(out_path, "wb") as f:
                                f.write(content)
                                
                            size_mb = len(content) / 1048576
                            log.info(f"Downloaded video for item {it_id} ({size_mb:.1f} MB)")
                            
                        if self.db:
                            self.db.update_item_status(it_id, ItemStatus.COMPLETED, output_path=out_path)
                        self.signals.item_completed.emit(it_id, out_path)
                        
                    except Exception as e:
                        log.error("Failed to download/save for item {}: {}".format(it_id, e))
                        if self.db:
                            self.db.update_item_status(it_id, ItemStatus.ERROR, error_message=str(e))
                        self.signals.item_error.emit(it_id, str(e))
                    
            except Exception as inner_e:
                err_str = str(inner_e).lower()
                if any(kw in err_str for kw in ["quota", "limit", "exhausted", "failed", "invalid"]):
                    log.warning("Account {} exhausted, marking it offline.".format(account.email))
                raise inner_e
            finally:
                try:
                    await page.close()
                except Exception:
                    pass
                try:
                    await local_browser_manager.close_context(account.id)
                except Exception as ex:
                    log.error(f"Error releasing browser context in batch finally: {ex}")
                
        except Exception as e:
            raise e


class UpscaleSignals(QObject):
    done = Signal(str)
    error = Signal(str)


class UpscaleRunnable(QRunnable):
    def __init__(self, image_path, output_path=None):
        super().__init__()
        self.image_path = image_path
        self.output_path = output_path
        self.signals = UpscaleSignals()

    def run(self):
        try:
            self._execute()
        except Exception as e:
            self.signals.error.emit(str(e))

    def _execute(self):
        self.signals.done.emit(str(self.output_path or self.image_path))


class TaskManager(QObject):
    def __init__(self, db=None, browser_manager=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.browser_manager = browser_manager
        self.account_pool = AccountPool(db)
        self.workers = {}
        self.thread_pool = QThreadPool.globalInstance()

    def start_task(self, task):
        mode = getattr(task, "mode", "")
        account_type = "grok" if mode in (TaskMode.GROK_IMAGE, TaskMode.GROK_VIDEO) else "google"
        pool = AccountPool(self.db, account_type=account_type)
        
        worker = TaskWorker(task, self.db, self.browser_manager, pool)
        task_id = getattr(task, "id", id(worker))
        self.workers[task_id] = worker
        worker.finished.connect(lambda tid=task_id: self._on_task_done(tid))
        worker.start()
        return worker

    def _get_all_workers(self):
        return list(self.workers.values())

    def retry_item(self, item_id):
        if not self.db: return None
        item = self.db.get_item(item_id)
        if not item: return None
        
        task = self.db.get_task(item.task_id)
        if not task: return None
        
        # Override parallel count to 1 for this single item retry
        task.parallel_per_account = 1
        task.items = [item]
        
        from config.constants import ItemStatus
        self.db.update_item_status(item_id, ItemStatus.PENDING)
        
        mode = getattr(task, "mode", "")
        account_type = "grok" if mode in (TaskMode.GROK_IMAGE, TaskMode.GROK_VIDEO) else "google"
        pool = AccountPool(self.db, account_type=account_type)
        
        worker = TaskWorker(task, self.db, self.browser_manager, pool)
        import time
        tid = f"retry_item_{item_id}_{int(time.time())}"
        self.workers[tid] = worker
        worker.finished.connect(lambda t=tid: self._on_task_done(t))
        worker.start()
        return worker

    def retry_all(self, task_id):
        pass


    def pause_task(self, task_id):
        worker = self.workers.get(task_id)
        if worker:
            worker.pause()

    def resume_task(self, task_id):
        worker = self.workers.get(task_id)
        if worker:
            worker.resume()

    def run_upscale(self, image_path, output_path=None):
        runnable = UpscaleRunnable(image_path, output_path)
        self.thread_pool.start(runnable)
        return runnable

    def cancel_task(self, task_id):
        worker = self.workers.get(task_id)
        if worker:
            worker.cancel()

    def cancel_all(self):
        for worker in self._get_all_workers():
            worker.cancel()

    stop_all = cancel_all
    stop_task = cancel_task

    def _on_task_done(self, task_id):
        self.workers.pop(task_id, None)

    def active_tasks(self):
        return list(self.workers)

    def available_accounts(self):
        return self.account_pool.available_count()
