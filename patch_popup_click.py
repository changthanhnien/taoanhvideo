import re

with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = "            # --- 1. OPEN SETTINGS POPUP ---"
start_idx = content.find(start_marker)

end_marker = "            import asyncio\n            await asyncio.sleep(1.5)"
end_idx = content.find(end_marker, start_idx)

if start_idx != -1 and end_idx != -1:
    new_block = '''            # --- 1. OPEN SETTINGS POPUP ---
            log.info("UI Auto: Configuring settings for Video...")
            popup_opened = False
            try:
                # Native Playwright Click
                ta = self._page.locator('textarea[aria-label*="create"], textarea[placeholder*="create"], textarea').first
                if await ta.is_visible(timeout=2000):
                    container = self._page.locator('div.input-container, div[class*="chat"], div[class*="prompt"]').filter(has=ta).first
                    if await container.is_visible(timeout=500):
                        pill = container.locator('button, [role="button"]').filter(has_text=re.compile(r"veo|imagen|nano|video|image|16:9|1x", re.IGNORECASE)).first
                        if await pill.is_visible(timeout=500):
                            await pill.click(timeout=1000)
                            popup_opened = True
                        else:
                            slider = container.locator('button:has(svg)').filter(has_text=re.compile(r"settings|cài đặt", re.IGNORECASE)).first
                            if await slider.is_visible(timeout=500):
                                await slider.click(timeout=1000)
                                popup_opened = True
            except Exception as e:
                log.warning(f"UI Auto: Native pill click FAILED: {e}")
            
            if not popup_opened:
                try:
                    pill = self._page.locator('button, [role="button"]').filter(has_text=re.compile(r"veo|imagen|nano|video|image|16:9|1x", re.IGNORECASE)).first
                    if await pill.is_visible(timeout=500):
                        await pill.click(timeout=1000)
                        popup_opened = True
                except: pass
            
            log.info(f"UI Auto: Popup open triggered: {popup_opened}")
'''
    new_content = content[:start_idx] + new_block + content[end_idx:]
    with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Fixed popup click!")
else:
    print(f"Failed to find markers: start={start_idx}, end={end_idx}")
