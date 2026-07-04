import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix settings_btn matcher to avoid sidebar buttons
old_settings = "if txt and ('Video' in txt or 'Hình ảnh' in txt or 'Image' in txt) and len(txt.strip()) < 30:"
new_settings = "if txt and ('Video' in txt or 'Hình ảnh' in txt or 'Image' in txt) and ('[' in txt or '·' in txt or 'x' in txt.lower() or 's' in txt.lower()) and len(txt.strip()) < 30:"
content = content.replace(old_settings, new_settings)

# 2. Fix click_segment_button to support aria-label and titles
old_segment = """                async def click_segment_button(target_texts):
                    # Finds a button (not dropdown option) containing the text
                    btns = await self._page.query_selector_all('button, div[role="button"]')
                    for btn in btns:
                        if await btn.is_visible():
                            text = await btn.inner_text()
                            if text:
                                for target in target_texts:
                                    if target.lower() == text.strip().lower() or target.lower() in text.lower():
                                        await btn.click()
                                        return True
                    log.warning(f"UI Auto: Could not find segment button for {target_texts}")
                    return False"""

new_segment = """                async def click_segment_button(target_texts):
                    # Finds a button (not dropdown option) containing the text or aria-label
                    btns = await self._page.query_selector_all('button, div[role="button"], [role="radio"]')
                    for btn in btns:
                        if await btn.is_visible():
                            text = await btn.inner_text()
                            aria_label = await btn.get_attribute('aria-label') or ""
                            title = await btn.get_attribute('title') or ""
                            combined = f"{text} {aria_label} {title}".lower()
                            if combined.strip():
                                for target in target_texts:
                                    if target.lower() in combined:
                                        await btn.click()
                                        await asyncio.sleep(0.5)
                                        return True
                    log.warning(f"UI Auto: Could not find segment button for {target_texts}")
                    return False"""

content = content.replace(old_segment, new_segment)

# 3. Enhance ratio_options and duration_options
old_ratio = """                if "16:9" in aspect_ratio:
                    ratio_options = ["16:9"]
                elif "9:16" in aspect_ratio:
                    ratio_options = ["9:16"]
                elif "4:3" in aspect_ratio:
                    ratio_options = ["4:3"]
                elif "3:4" in aspect_ratio:
                    ratio_options = ["3:4"]
                else:
                    ratio_options = ["1:1"]"""

new_ratio = """                if "16:9" in aspect_ratio:
                    ratio_options = ["16:9", "Ngang", "Landscape", "16 by 9", "16 x 9"]
                elif "9:16" in aspect_ratio:
                    ratio_options = ["9:16", "Dọc", "Portrait", "9 by 16", "9 x 16"]
                elif "4:3" in aspect_ratio:
                    ratio_options = ["4:3"]
                elif "3:4" in aspect_ratio:
                    ratio_options = ["3:4"]
                else:
                    ratio_options = ["1:1", "Vuông", "Square"]"""

content = content.replace(old_ratio, new_ratio)

# 4. Give settings popup more time to open
content = content.replace("await settings_btn.click()\n                await asyncio.sleep(1)", "await settings_btn.click()\n                await asyncio.sleep(2)")

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Injected fixes successfully!")
