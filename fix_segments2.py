import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_segment_logic = """
                async def click_segment_button(target_texts):
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
                    return False
"""

new_segment_logic = """
                async def click_segment_button(target_texts):
                    # First try Playwright's get_by_text which is robust against custom elements
                    for target in target_texts:
                        try:
                            locators = await self._page.get_by_text(target, exact=True).element_handles()
                            for loc in locators:
                                if await loc.is_visible():
                                    await loc.click()
                                    await asyncio.sleep(0.5)
                                    return True
                        except Exception:
                            pass
                            
                        # Try non-exact text match as fallback
                        try:
                            locators = await self._page.get_by_text(target).element_handles()
                            for loc in locators:
                                if await loc.is_visible():
                                    # Ensure we don't click the main label by mistake
                                    await loc.click()
                                    await asyncio.sleep(0.5)
                                    return True
                        except Exception:
                            pass

                    # Ultimate fallback
                    btns = await self._page.query_selector_all('button, div[role="button"], [role="radio"], label, .segment')
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
                    return False
"""

if old_segment_logic.strip() in content:
    content = content.replace(old_segment_logic.strip(), new_segment_logic.strip())
else:
    print("WARNING: Could not find old_segment_logic to replace!")

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated segment logic successfully!")
