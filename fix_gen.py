import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_gen_logic = """
            # Find the Generate button (it might be an arrow icon with aria-label)
            gen_btn = None
            gen_btn = await self._page.query_selector('button[aria-label*="Tạo"], button[aria-label*="Create"], button[aria-label*="Generate"], button[aria-label*="Submit"]')
            
            if not gen_btn:
                # Fallback: find any button with an arrow icon near the prompt box
                buttons = await self._page.query_selector_all('button, [role="button"]')
                for b in buttons:
                    if await b.is_visible():
                        text = await b.inner_text()
                        if text and ('Tạo' in text or 'Generate' in text or 'send' in text.lower() or 'arrow' in text.lower()):
                            gen_btn = b
                            break

            existing = await self._page.query_selector_all('video')
            existing_srcs = []
            for img in existing:
                src = await img.get_attribute('src')
                if src: existing_srcs.append(src)
                
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

new_gen_logic = """
            existing = await self._page.query_selector_all('video')
            existing_srcs = []
            for img in existing:
                src = await img.get_attribute('src')
                if src: existing_srcs.append(src)
                
            # We avoid broad text searches like 'Tạo' because it matches '+ Tác nhân' (Tạo tác nhân)
            # Instead, we rely on the exact sibling of the Pill button OR Ctrl+Enter
            gen_btn = None
            if settings_btn:
                try:
                    gen_btn_handle = await settings_btn.evaluate_handle("el => el.nextElementSibling")
                    if gen_btn_handle:
                        gen_btn = gen_btn_handle.as_element()
                except Exception:
                    pass
            
            if gen_btn:
                log.info("UI Auto: Clicking Generate button next to Settings Pill...")
                try:
                    await gen_btn.click(force=True)
                except Exception as e:
                    log.warning(f"Failed to click gen_btn: {e}")
            
            # ALWAYS fire Ctrl+Enter to guarantee submission (does no harm if already submitted)
            log.info("UI Auto: Pressing Ctrl+Enter to ensure submission...")
            if prompt_input:
                await prompt_input.click()
            await asyncio.sleep(0.5)
            await self._page.keyboard.press("Control+Enter")
            await asyncio.sleep(0.5)
            await self._page.keyboard.press("Meta+Enter")
"""

if old_gen_logic.strip() in content:
    content = content.replace(old_gen_logic.strip(), new_gen_logic.strip())
else:
    print("WARNING: Could not find old_gen_logic to replace!")

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated Generate button logic successfully!")
