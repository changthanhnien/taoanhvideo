import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('            log.info("UI Auto: Waiting for Generation to complete...")')
end_idx = content.find('            return {"media": media_list}')

if start_idx == -1 or end_idx == -1:
    print("Could not find wait section")
    exit(1)

new_code = """            log.info("UI Auto: Waiting for Generation to complete...")
            start_time = _time.time()
            result_media_list = []
            max_wait = 600
            
            while (_time.time() - start_time) < max_wait:
                if self._page.is_closed():
                    raise RuntimeError("Browser was closed by user")
                    
                result_imgs = await self._page.query_selector_all('video')
                if len(result_imgs) > len(existing_srcs):
                    # We have new videos! Check if they are real videos (not small placeholders)
                    for img in result_imgs:
                        if await img.is_visible():
                            src = await img.get_attribute('src')
                            if src and src not in existing_srcs:
                                # Check if it's a blob URL
                                if src.startswith('blob:'):
                                    # Fetch blob size via browser
                                    blob_info = await self._page.evaluate(
                                        '''async (url) => {
                                            try {
                                                const r = await fetch(url);
                                                const b = await r.blob();
                                                if (b.size > 100000) {
                                                    return new Promise((resolve) => {
                                                        const reader = new FileReader();
                                                        reader.onloadend = () => resolve({size: b.size, data: reader.result});
                                                        reader.readAsDataURL(b);
                                                    });
                                                }
                                                return {size: b.size, data: null};
                                            } catch(e) { return null; }
                                        }''', src
                                    )
                                    if blob_info and blob_info.get("data"):
                                        log.info(f"UI Auto: Found REAL generated video of size {blob_info['size']} bytes!")
                                        existing_srcs.append(src)
                                        result_media_list.append({
                                            "image": {
                                                "generatedImage": {
                                                    "url": blob_info["data"], # We pass the Base64 Data URL!
                                                    "name": f"flow_video_{int(_time.time())}_{len(result_media_list)}",
                                                }
                                            }
                                        })
                                        if callback:
                                            try:
                                                await callback(blob_info["data"])
                                            except Exception:
                                                pass
                                    else:
                                        # Size is too small, or fetch failed. Probably a placeholder.
                                        pass
                                else:
                                    # Normal URL
                                    log.info(f"UI Auto: Found generated video with URL: {src}")
                                    existing_srcs.append(src)
                                    result_media_list.append({
                                        "image": {
                                            "generatedImage": {
                                                "url": src,
                                                "name": f"flow_video_{int(_time.time())}_{len(result_media_list)}",
                                            }
                                        }
                                    })
                                    if callback:
                                        try:
                                            await callback(src)
                                        except Exception:
                                            pass
                
                if len(result_media_list) >= count:
                    break
                await asyncio.sleep(2)
            
            if not result_media_list:
                raise RuntimeError(f"No result video found after {max_wait}s")
            
"""

content = content[:start_idx] + new_code + content[end_idx:]

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Injected video wait fix successfully!")
