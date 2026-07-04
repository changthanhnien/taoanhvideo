import asyncio
import os
from pathlib import Path
import httpx
from config.constants import TaskMode, ItemStatus, DEFAULT_IMAGE_OUTPUT, DEFAULT_VIDEO_OUTPUT
from services.flow_client import FlowClient

class ExecutePatchMixin:
    async def _async_execute(self):
        from automation.browser_manager import BrowserManager
        import logging
        log = logging.getLogger("task_manager")
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
            max_batch_size = 4
            
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
            
            async def get_account():
                async with self._task_account_lock:
                    if self._current_account is None:
                        acc = self.account_pool.acquire(100)
                        while not acc and not self._cancelled:
                            await asyncio.sleep(2)
                            acc = self.account_pool.acquire(100)
                        self._current_account = acc
                    return self._current_account
                    
            async def rotate_account(old_acc):
                async with self._task_account_lock:
                    if self._current_account and self._current_account.email == old_acc.email:
                        log.info("Task {}: Account {} exhausted, rotating...".format(task_id, old_acc.email))
                        self.account_pool.mark_exhausted(self._current_account)
                        self.account_pool.release(self._current_account)
                        self._current_account = None
                        acc = self.account_pool.acquire(100)
                        while not acc and not self._cancelled:
                            await asyncio.sleep(2)
                            acc = self.account_pool.acquire(100)
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
                    
                    if delay > 0 and not self._cancelled:
                        log.info("Delay {}s before starting batch {}...".format(delay, item_ids))
                        await asyncio.sleep(delay)
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
                            self.signals.item_error.emit(item_id, err_msg)
        finally:
            if getattr(self, "_current_account", None):
                self.account_pool.release(self._current_account)
                
            await local_browser_manager.stop()
            
        self.signals.task_completed.emit(task_id)

    async def _async_process_batch(self, batch, local_browser_manager, account):
        import logging
        log = logging.getLogger("task_manager")
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
                    model_key = cfg_dict.get("quality_key", "veo-3.1-fast")
                except Exception:
                    duration = 8
                    creation_mode = "Text -> Video"
                    uploaded_images = []
                    model_key = "veo-3.1-fast"
                    
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
                
                if mode in (TaskMode.IMAGE, TaskMode.CHAR_IMAGE):
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
                        elif isinstance(result, dict) and "media" in result:
                            for m in result["media"]:
                                url = m.get("image", {}).get("generatedImage", {}).get("url")
                                if url:
                                    result_urls.append(url)
                        else:
                            for i in range(count):
                                result_urls.append(result.get("name") or result.get("mediaId"))

                opened_profiles = len(local_browser_manager._browsers) if hasattr(local_browser_manager, '_browsers') else 1
                
                log.info(
                    "\\n--- EXECUTION LOG ---\\n"
                    "generation_quantity={}\\n"
                    "browser_concurrency={}\\n"
                    "account_concurrency={}\\n"
                    "selected_account={}\\n"
                    "opened_profiles={}\\n"
                    "flow_batch={}\\n"
                    "received={}\\n"
                    "---------------------\\n".format(
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
                        if mode in (TaskMode.IMAGE, TaskMode.CHAR_IMAGE):
                            await self._download_file(r_url, out_path)
                            self.signals.item_status_changed.emit(it_id, "UPSCALE") 
                            log.info("Downloaded image for item {}".format(it_id))
                        else:
                            if r_url and r_url.startswith("data:"):
                                import base64
                                b64 = r_url.split(",", 1)[1]
                                with open(out_path, "wb") as f:
                                    f.write(base64.b64decode(b64))
                                dl_url = r_url
                            else:
                                dl_url = await client.get_download_url(r_url)
                                if not dl_url:
                                    log.warning("Could not get download URL for {}, trying browser fetch...".format(r_url))
                                    b64 = await client._fetch_mp4_via_browser_fetch(r_url)
                                    if b64:
                                        with open(out_path, "wb") as f:
                                            f.write(b64)
                                    else:
                                        raise RuntimeError("Không lấy được link tải video và browser fetch thất bại.")
                                else:
                                    await client.download_result(dl_url, out_path)
                            log.info("Downloaded video for item {}".format(it_id))
                            
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
                await page.close()
                
        except Exception as e:
            raise e
