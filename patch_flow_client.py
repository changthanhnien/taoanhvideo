import os
import re

p = r'd:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\services\flow_client.py'
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# Fix 1: Settings button
c = c.replace(
    "buttons = await self._page.query_selector_all('button')",
    "buttons = await self._page.query_selector_all('button, [role=\"button\"]')",
    1 # only the first one for settings
)

# Fix 2: Prompt input logic
old_prompt_logic = """            # Get prompt input element
            prompt_input = None
            for sel in ['textarea', 'div[role="textbox"]', 'div[contenteditable="true"]']:
                els = await self._page.query_selector_all(sel)
                for el in els:
                    if await el.is_visible():
                        prompt_input = el
                        break
                if prompt_input:
                    break
            if not prompt_input:
                await self._page.mouse.click(500, 580)
                await asyncio.sleep(0.5)
                for sel in ['textarea', 'div[role="textbox"]', 'div[contenteditable="true"]']:
                    els = await self._page.query_selector_all(sel)
                    for el in els:
                        if await el.is_visible():
                            prompt_input = el
                            break
                    if prompt_input:
                        break"""

new_prompt_logic = """            # Get prompt input element
            prompt_input = None
            try:
                # Wait for the prompt input to appear naturally
                prompt_input = await self._page.wait_for_selector('textarea, div[role="textbox"], div[contenteditable="true"]', timeout=5000)
            except Exception:
                pass
                
            if not prompt_input:
                for sel in ['textarea', 'div[role="textbox"]', 'div[contenteditable="true"]']:
                    els = await self._page.query_selector_all(sel)
                    for el in els:
                        if await el.is_visible():
                            prompt_input = el
                            break
                    if prompt_input:
                        break
                        
            if not prompt_input:
                log.warning("UI Auto: Could not find prompt input, clicking bottom center (500, 800) instead of middle screen...")
                await self._page.mouse.click(500, 800)
                await asyncio.sleep(0.5)
                for sel in ['textarea', 'div[role="textbox"]', 'div[contenteditable="true"]']:
                    els = await self._page.query_selector_all(sel)
                    for el in els:
                        if await el.is_visible():
                            prompt_input = el
                            break
                    if prompt_input:
                        break"""

c = c.replace(old_prompt_logic, new_prompt_logic)

# Fix 3: Generate button selector
old_gen_selectors = """            gen_selectors = [
                'button:has-text("arrow_forward")',
                'button:has-text("Generate")',
                'button:has-text("Create")',
                'button[aria-label*="Generate"]',
                'button[aria-label*="Create"]',
                'button[aria-label*="Submit"]',
            ]"""

new_gen_selectors = """            gen_selectors = [
                'button:has-text("arrow_forward")',
                'button:has-text("Generate")',
                'button:has-text("Create")',
                'button[aria-label*="Generate"]',
                'button[aria-label*="Create"]',
                'button[aria-label*="Submit"]',
                '[role="button"][aria-label*="Generate"]',
                '[role="button"][aria-label*="Create"]',
                'div[role="button"]:has-text("arrow_forward")'
            ]"""

c = c.replace(old_gen_selectors, new_gen_selectors)

# Fix 4: Generate button fallback loop
c = c.replace(
    "buttons = await self._page.query_selector_all('button')",
    "buttons = await self._page.query_selector_all('button, [role=\"button\"]')"
) # Replaces any remaining instances (like the generate button fallback)

with open(p, 'w', encoding='utf-8') as f:
    f.write(c)
print("Patched flow_client.py")
