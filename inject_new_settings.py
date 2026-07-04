import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# I will find the _generate_video_whisk method and replace its settings section
start_settings = content.find('            log.info("UI Auto: Configuring settings (Model, Ratio)...")')
end_settings = content.find('            if image_paths and len(image_paths) > 0:')

if start_settings == -1 or end_settings == -1:
    print("Could not find settings section")
    exit(1)

new_settings_code = """            log.info("UI Auto: Configuring settings for Video...")
            settings_btn = None
            buttons = await self._page.query_selector_all('button, [role="button"]')
            for b in buttons:
                try:
                    icon = await b.query_selector('md-icon')
                    if icon:
                        txt = await icon.inner_text()
                        if txt and 'settings' in txt:
                            settings_btn = b
                            break
                except Exception:
                    continue
            
            if settings_btn:
                await settings_btn.click()
                await asyncio.sleep(1)
                
                # Switch to Video tab
                video_tab = await self._page.query_selector('button:has-text("Video")')
                if video_tab:
                    await video_tab.click()
                    await asyncio.sleep(1)
                    
                async def click_segment_button(target_texts):
                    # Finds a button (not dropdown option) containing the text
                    btns = await self._page.query_selector_all('button')
                    for btn in btns:
                        if await btn.is_visible():
                            text = await btn.inner_text()
                            if text:
                                for target in target_texts:
                                    if target.lower() == text.strip().lower() or target.lower() in text.lower():
                                        await btn.click()
                                        return True
                    log.warning(f"UI Auto: Could not find segment button for {target_texts}")
                    return False

                async def click_dropdown_option(target_texts):
                    items = await self._page.query_selector_all('md-select-option')
                    for item in items:
                        text = await item.inner_text()
                        if text:
                            for target in target_texts:
                                if target.lower() == text.strip().lower() or target.lower() in text.lower():
                                    await item.click()
                                    return True
                    log.warning(f"UI Auto: Could not find dropdown option for {target_texts}")
                    return False

                # 1. Ratio (Segment buttons)
                ratio_options = [aspect_ratio, f"crop_{aspect_ratio.replace(':','_')}"]
                await click_segment_button(ratio_options)
                await asyncio.sleep(0.5)

                # 2. Count (Segment buttons)
                count_options = [f"{count}x", f"x{count}", str(count)]
                await click_segment_button(count_options)
                await asyncio.sleep(0.5)

                # 3. Model (Dropdown)
                dropdowns = await self._page.query_selector_all('md-outlined-select, [role="combobox"]')
                for dd in dropdowns:
                    if await dd.is_visible():
                        await dd.click()
                        await asyncio.sleep(1)
                        model_options = [model, model.replace("-", " "), model.replace("_", " ")]
                        clicked = await click_dropdown_option(model_options)
                        await asyncio.sleep(0.5)
                        if clicked:
                            break
                
                # 4. Duration (Segment buttons)
                dur_options = [f"{duration}s", f"{duration} giây", str(duration)]
                await click_segment_button(dur_options)
                await asyncio.sleep(0.5)
                
"""

content = content[:start_settings] + new_settings_code + content[end_settings:]

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Injected new settings logic successfully!")
