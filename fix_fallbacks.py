import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the fallback for settings_btn to use the Tune icon SVG path
old_settings_fallback = """
            if not settings_btn:
                log.info("UI Auto: Pill button not found, falling back to sliders/settings icon...")
                btns = await self._page.query_selector_all('button, [role="button"]')
                for b in btns:
                    if await b.is_visible():
                        label = await b.get_attribute('aria-label') or ""
                        title = await b.get_attribute('title') or ""
                        combined = f"{label} {title}".lower()
                        if 'cài đặt' in combined or 'settings' in combined or 'điều chỉnh' in combined or 'tune' in combined or 'tùy chọn' in combined or 'options' in combined:
                            settings_btn = b
                            break

            if not settings_btn:
                # Absolute fallback: Find the button next to the submit arrow that has an SVG
                # We can just look for the submit button and get its previous sibling!
                submit_btn = await self._page.query_selector('button[aria-label*="Tạo"], button[aria-label*="Create"], button[aria-label*="Generate"], button[aria-label*="Submit"]')
                if submit_btn:
                    # In DOM it's usually the button right before it
                    prev = await submit_btn.evaluate_handle("el => el.previousElementSibling")
                    if prev:
                        settings_btn = prev.as_element()
"""

new_settings_fallback = """
            if not settings_btn:
                log.info("UI Auto: Pill button not found, falling back to sliders/settings icon...")
                btns = await self._page.query_selector_all('button, [role="button"], div, span')
                for b in btns:
                    if await b.is_visible():
                        html = await b.evaluate("el => el.innerHTML")
                        if html and ('M3 17v2h6' in html or 'm3 17v2h6' in html or 'M3,17' in html or 'M3 17 v 2 h 6' in html):
                            # Ensure it's a clickable element or find its closest button
                            parent_btn = await b.evaluate_handle("el => el.closest('button, [role=\"button\"]') || el")
                            settings_btn = parent_btn.as_element() if parent_btn else b
                            break

            if not settings_btn:
                # Fallback: check aria-label again just in case
                btns = await self._page.query_selector_all('button, [role="button"]')
                for b in btns:
                    if await b.is_visible():
                        label = await b.get_attribute('aria-label') or ""
                        title = await b.get_attribute('title') or ""
                        combined = f"{label} {title}".lower()
                        if 'cài đặt' in combined or 'settings' in combined or 'điều chỉnh' in combined or 'tune' in combined or 'tùy chọn' in combined or 'options' in combined:
                            settings_btn = b
                            break
"""

if old_settings_fallback.strip() in content:
    content = content.replace(old_settings_fallback.strip(), new_settings_fallback.strip())
else:
    print("WARNING: Could not find old_settings_fallback to replace!")


# 2. Update the fallback for Generate button to use Control+Enter
old_submit_fallback = """
            if gen_btn:
                await gen_btn.click()
            else:
                # Fallback: focus the prompt box and press Enter to submit
                if prompt_input:
                    await prompt_input.click()
                await self._page.keyboard.press("Enter")
"""

new_submit_fallback = """
            if gen_btn:
                await gen_btn.click()
            else:
                log.info("UI Auto: Generate button not found, using Ctrl+Enter fallback")
                if prompt_input:
                    await prompt_input.click()
                await asyncio.sleep(0.5)
                # Press Control+Enter to submit in Google Flow
                await self._page.keyboard.press("Control+Enter")
                await asyncio.sleep(0.5)
                # Fallback for Mac
                await self._page.keyboard.press("Meta+Enter")
"""

if old_submit_fallback.strip() in content:
    content = content.replace(old_submit_fallback.strip(), new_submit_fallback.strip())
else:
    print("WARNING: Could not find old_submit_fallback to replace!")


with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated fallbacks successfully!")
