import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# I want to inject the popup dismissal logic right before: if project_name:

popup_logic = """
            # --- POPUP DISMISSAL ---
            # The UI might show a "Maps Imagery Grounding" or other onboarding popup for new accounts
            try:
                log.info("UI Auto: Checking for any onboarding popups...")
                
                # 1. Try to click specific dismiss buttons
                dismiss_btns = await self._page.query_selector_all('button:has-text("Bắt đầu"), button:has-text("Get started"), button:has-text("Got it"), button:has-text("Đã hiểu"), button:has-text("Tiếp tục"), button:has-text("Continue")')
                for btn in dismiss_btns:
                    if await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(0.5)
                        
                # 2. Press Escape a couple of times to close modals
                await self._page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                await self._page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                
                # 3. Click outside the modal in the dark overlay area (left edge, middle vertically)
                # This guarantees the modal closes if it requires clicking outside
                await self._page.mouse.click(10, 300)
                await asyncio.sleep(0.5)
                await self._page.mouse.click(10, 400)
                await asyncio.sleep(0.5)
                
            except Exception as e:
                log.warning(f"UI Auto: Error dismissing popups: {e}")
            # -----------------------

            if project_name:"""

content = content.replace("            if project_name:", popup_logic)

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Injected popup dismissal logic successfully!")
