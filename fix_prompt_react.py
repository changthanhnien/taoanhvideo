with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_prompt = """
                # Use insert_text to bypass Unikey/Vietnamese IME corruption
                await self._page.keyboard.insert_text(prompt)
                await asyncio.sleep(2)  # Wait for Pill button to appear!
"""

new_prompt = """
                # Use insert_text to bypass Unikey/Vietnamese IME corruption
                await self._page.keyboard.insert_text(prompt)
                await asyncio.sleep(0.5)
                # VERY IMPORTANT: insert_text bypasses normal keydown events, 
                # so React might not detect the text change and won't show the Pill button.
                # We press Space then Backspace to force a real keyboard event to wake up React!
                await self._page.keyboard.press("Space")
                await self._page.keyboard.press("Backspace")
                await asyncio.sleep(2)  # Wait for Pill button to appear!
"""

if old_prompt.strip() in content:
    content = content.replace(old_prompt.strip(), new_prompt.strip())
else:
    print("WARNING: Could not find old_prompt to replace!")

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated prompt logic to trigger React onChange!")
