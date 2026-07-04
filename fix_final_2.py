import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()


# 1. Fix Prompt clearing
old_prompt = """
            if prompt_input:
                await prompt_input.click()
                await self._page.keyboard.press("Control+a")
                await self._page.keyboard.press("Backspace")
                await self._page.keyboard.type(prompt, delay=10)
                await asyncio.sleep(2)  # Wait for Pill button to appear!
"""

new_prompt = """
            if prompt_input:
                # Force clear the prompt box by overriding its content directly
                try:
                    await prompt_input.evaluate("el => el.innerHTML = ''")
                    await prompt_input.evaluate("el => el.innerText = ''")
                    await prompt_input.evaluate("el => el.textContent = ''")
                except Exception:
                    pass
                await prompt_input.click()
                # Also try the standard fill method
                try:
                    await prompt_input.fill("")
                except Exception:
                    pass
                # Also do Ctrl+A just in case
                await self._page.keyboard.press("Control+A")
                await self._page.keyboard.press("Backspace")
                
                await self._page.keyboard.type(prompt, delay=10)
                await asyncio.sleep(2)  # Wait for Pill button to appear!
"""

if old_prompt.strip() in content:
    content = content.replace(old_prompt.strip(), new_prompt.strip())
else:
    print("WARNING: Could not find old_prompt to replace!")


# 2. Fix Segment clicking (do not check is_visible because obscured elements return false)
old_segment = """
                async def click_segment_button(target_texts):
                    # First try Playwright's get_by_text which is robust against custom elements
                    for target in target_texts:
                        try:
                            locators = await self._page.get_by_text(target, exact=True).element_handles()
                            for loc in locators:
                                # Sometimes it's technically hidden but we still want to click it
                                await loc.click(force=True)
                                await asyncio.sleep(0.5)
                                return True
                        except Exception:
                            pass
                            
                        # Try non-exact text match as fallback
                        try:
                            locators = await self._page.get_by_text(target).element_handles()
                            for loc in locators:
                                await loc.click(force=True)
                                await asyncio.sleep(0.5)
                                return True
                        except Exception:
                            pass

                    # Ultimate fallback
                    btns = await self._page.query_selector_all('button, div[role="button"], [role="radio"], label, .segment')
                    for btn in btns:
                        text = await btn.inner_text() if await btn.is_visible() else ""
                        aria_label = await btn.get_attribute('aria-label') or ""
                        title = await btn.get_attribute('title') or ""
                        combined = f"{text} {aria_label} {title}".lower()
                        if combined.strip():
                            for target in target_texts:
                                if target.lower() in combined:
                                    try:
                                        await btn.click(force=True)
                                        await asyncio.sleep(0.5)
                                        return True
                                    except Exception:
                                        pass
                    log.warning(f"UI Auto: Could not find segment button for {target_texts}")
                    return False
"""

new_segment = """
                async def click_segment_button(target_texts):
                    for target in target_texts:
                        # Exact match
                        try:
                            locs = await self._page.get_by_text(target, exact=True).all()
                            for loc in locs:
                                try:
                                    await loc.click(force=True, timeout=1000)
                                    await asyncio.sleep(0.5)
                                    return True
                                except Exception:
                                    continue
                        except Exception:
                            pass
                            
                        # Non-exact match
                        try:
                            locs = await self._page.get_by_text(target).all()
                            for loc in locs:
                                try:
                                    await loc.click(force=True, timeout=1000)
                                    await asyncio.sleep(0.5)
                                    return True
                                except Exception:
                                    continue
                        except Exception:
                            pass

                    # Ultimate fallback
                    btns = await self._page.query_selector_all('button, div[role="button"], [role="radio"], label, .segment')
                    for btn in btns:
                        try:
                            text = await btn.inner_text() if await btn.is_visible() else ""
                        except Exception:
                            text = ""
                        aria_label = await btn.get_attribute('aria-label') or ""
                        title = await btn.get_attribute('title') or ""
                        combined = f"{text} {aria_label} {title}".lower()
                        if combined.strip():
                            for target in target_texts:
                                if target.lower() in combined:
                                    try:
                                        await btn.click(force=True, timeout=1000)
                                        await asyncio.sleep(0.5)
                                        return True
                                    except Exception:
                                        pass
                    log.warning(f"UI Auto: Could not find segment button for {target_texts}")
                    return False
"""

if old_segment.strip() in content:
    content = content.replace(old_segment.strip(), new_segment.strip())
else:
    print("WARNING: Could not find old_segment to replace!")


with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated prompt clear and segment click logic successfully!")
