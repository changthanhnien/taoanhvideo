import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

fallback_code = """
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

# Insert this before `if settings_btn:`
content = content.replace("            if settings_btn:", fallback_code + "\n            if settings_btn:")

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Injected settings fallback successfully!")
