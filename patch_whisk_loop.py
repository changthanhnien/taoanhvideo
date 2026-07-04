import re

with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to find the start of the bad block and the end.
start_marker = '                        # NATIVE DOWNLOAD'

start_idx = content.find(start_marker)
if start_idx == -1:
    print('Start marker not found')
    exit(1)

# Find where the block ends (the loop continuation or fallback)
end_idx = content.find('                    if blob_info and blob_info.get("data"):', start_idx)

if end_idx == -1:
    print('End marker not found')
    exit(1)

new_block = '''                        # NATIVE DOWNLOAD
                        downloaded = False
                        blob_info = {"data": None, "error": "Init", "size": 0}
                        
                        try:
                            log.info("UI Auto: Attempting native download for video...")
                            async with self._page.expect_download(timeout=15000) as download_info:
                                await self._page.evaluate(f"""() => {{
                                    const a = document.createElement('a');
                                    a.href = "{src}";
                                    a.download = "video.mp4";
                                    document.body.appendChild(a);
                                    a.click();
                                    document.body.removeChild(a);
                                }}""")
                            
                            download = await download_info.value
                            import tempfile, os, base64
                            save_path = os.path.join(tempfile.gettempdir(), f"flow_video_{int(_time.time())}.mp4")
                            await download.save_as(save_path)
                            
                            with open(save_path, "rb") as f:
                                video_bytes = f.read()
                                
                            file_size = len(video_bytes)
                            if file_size > 50000:
                                b64_data = base64.b64encode(video_bytes).decode('utf-8')
                                blob_info = {
                                    "size": file_size,
                                    "data": f"data:video/mp4;base64,{b64_data}"
                                }
                                downloaded = True
                                log.info(f"UI Auto: Native Download SUCCESS! Size: {file_size} bytes.")
                            else:
                                blob_info = {"error": "Too small", "size": file_size, "data": None}
                                
                            try: os.remove(save_path)
                            except: pass
                            
                        except Exception as e:
                            log.warning(f"UI Auto: Native download failed: {e}")
                            
                        if not downloaded:
                            log.warning(f"UI Auto: Falling back to HTTP memory fetch...")
                            blob_info = await self._page.evaluate(
                                \'\'\'async (url) => {
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
                                }\'\'\', src
                            )
'''

new_content = content[:start_idx] + new_block + content[end_idx:]

with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('Patch applied successfully')
