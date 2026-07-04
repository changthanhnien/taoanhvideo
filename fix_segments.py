import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_segment_logic = """
                async def click_segment_button(target_texts):
                    segments = await self._page.query_selector_all('md-filter-chip, md-suggestion-chip, button, [role="button"], [role="radio"]')
                    for btn in segments:
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
                                    # Ensure we don't click the main label by mistake, though clicking it might focus it
                                    await loc.click()
                                    await asyncio.sleep(0.5)
                                    return True
                        except Exception:
                            pass

                    # Ultimate fallback: check innerText of all visible elements with a pointer cursor or specific roles
                    segments = await self._page.query_selector_all('md-filter-chip, md-suggestion-chip, button, [role="button"], [role="radio"], label, .segment')
                    for btn in segments:
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


# Also do the same for click_dropdown_option because Model dropdown might suffer from the same issue!
old_dropdown_logic = """
                async def click_dropdown_option(target_texts):
                    items = await self._page.query_selector_all('md-select-option, [role="option"]')
                    for item in items:
                        if await item.is_visible():
                            text = await item.inner_text()
                            if text:
                                for target in target_texts:
                                    if target.lower() == text.strip().lower() or target.lower() in text.lower():
                                        await item.click()
                                        return True
                    log.warning(f"UI Auto: Could not find dropdown option for {target_texts}")
                    return False
"""

new_dropdown_logic = """
                async def click_dropdown_option(target_texts):
                    for target in target_texts:
                        try:
                            locators = await self._page.get_by_text(target).element_handles()
                            for loc in locators:
                                if await loc.is_visible():
                                    await loc.click()
                                    return True
                        except Exception:
                            pass
                    
                    items = await self._page.query_selector_all('md-select-option, [role="option"], li')
                    for item in items:
                        if await item.is_visible():
                            text = await item.inner_text()
                            if text:
                                for target in target_texts:
                                    if target.lower() == text.strip().lower() or target.lower() in text.lower():
                                        await item.click()
                                        return True
                    log.warning(f"UI Auto: Could not find dropdown option for {target_texts}")
                    return False
"""

if old_dropdown_logic.strip() in content:
    content = content.replace(old_dropdown_logic.strip(), new_dropdown_logic.strip())
else:
    print("WARNING: Could not find old_dropdown_logic to replace!")


with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated segment and dropdown logic successfully!")
