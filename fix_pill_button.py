import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to replace the entire Settings button finding block.
old_block_start = 'log.info("UI Auto: Configuring settings for Video...")'
old_block_end = '# Switch to Video tab'

idx_start = content.find(old_block_start)
idx_end = content.find(old_block_end)

if idx_start != -1 and idx_end != -1:
    old_code = content[idx_start:idx_end]
    
    new_code = """log.info("UI Auto: Configuring settings for Video...")
            settings_btn = None
            
            # SUPER ROBUST SETTINGS BUTTON FINDER
            # The Settings Pill button displays the current settings (e.g. "Veo", "Imagen", "16:9", "8s", "x4")
            try:
                search_texts = ["Veo", "Imagen", "16:9", "1:1", "4:3", "9:16", "3:4", "8s", "4s", "x4", "x1", "x2", "x3", "Model", "Settings"]
                for text in search_texts:
                    locs = await self._page.get_by_text(text).all()
                    for loc in locs:
                        if await loc.is_visible():
                            is_btn = await loc.evaluate('el => el.tagName === "BUTTON" || el.getAttribute("role") === "button" || el.closest("button, [role=\\"button\\"]") !== null')
                            if is_btn:
                                btn_handle = await loc.evaluate_handle('el => el.closest("button, [role=\\"button\\"]") || el')
                                settings_btn = btn_handle.as_element()
                                break
                    if settings_btn:
                        log.info(f"UI Auto: Found settings pill containing '{text}'")
                        break
                        
                if not settings_btn:
                    # Fallback: look for the slider SVG icon
                    btns = await self._page.query_selector_all('button, [role="button"]')
                    for b in btns:
                        if await b.is_visible():
                            html = await b.evaluate("el => el.innerHTML")
                            if html and ('M3 17v2h6' in html or 'm3 17v2h6' in html or 'M3,17' in html):
                                settings_btn = b
                                log.info("UI Auto: Found settings pill via SVG icon")
                                break
            except Exception as e:
                log.warning(f"Error finding settings button: {e}")

            if settings_btn:
                await settings_btn.click(force=True)
                await asyncio.sleep(2.0)
            else:
                log.warning("UI Auto: CRITICAL - Could not find Settings Pill button!")
                
            """
    content = content[:idx_start] + new_code + content[idx_end:]
    
    # Also fix click_segment_button inside the settings block to be more robust
    
    with open('services/flow_client.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced settings button logic successfully!")
else:
    print("WARNING: Could not find block to replace!")
