import re

with open('workers/task_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('                    r_url = result_urls[i] if i < len(result_urls) else result_urls[0]')
end_idx = content.find('                            log.info("Downloaded video for item {}".format(it_id))')

if start_idx == -1 or end_idx == -1:
    print("Could not find download logic in task_manager")
    exit(1)

new_code = """                    r_url = result_urls[i] if i < len(result_urls) else result_urls[0]
                    
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
                                self.signals.item_status_changed.emit(it_id, "DONE")
                        elif mode in (TaskMode.IMAGE, TaskMode.CHAR_IMAGE):
                            await self._download_file(r_url, out_path)
                            self.signals.item_status_changed.emit(it_id, "UPSCALE") 
                            log.info("Downloaded image for item {}".format(it_id))
                        else:
                            dl_url = await client.get_download_url(r_url)
                            if not dl_url:
                                log.warning("Could not get download URL for {}, trying browser fetch...".format(r_url))
                                b64 = await client._fetch_mp4_via_browser_fetch(r_url)
                                if b64:
                                    with open(out_path, "wb") as f:
                                        f.write(b64)
                                else:
                                    raise RuntimeError("Không lấy được link tải video và browser fetch thất bại")
                            else:
                                await self._download_file(dl_url, out_path)
"""

content = content[:start_idx] + new_code + content[end_idx:]

with open('workers/task_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Injected base64 download fix successfully!")
