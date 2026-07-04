import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the overly aggressive prompt clear logic with just Ctrl+A, Backspace, and insert_text
old_prompt_chunk = """
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

new_prompt_chunk = """
            if prompt_input:
                await prompt_input.click()
                # Use only Ctrl+A and Backspace to clear, to preserve the React/Lit internal state
                await self._page.keyboard.press("Control+a")
                await self._page.keyboard.press("Backspace")
                
                # Use insert_text to bypass Unikey/Vietnamese IME corruption
                await self._page.keyboard.insert_text(prompt)
                await asyncio.sleep(2)  # Wait for Pill button to appear!
"""

if old_prompt_chunk.strip() in content:
    content = content.replace(old_prompt_chunk.strip(), new_prompt_chunk.strip())
else:
    print("WARNING: Could not find old_prompt_chunk to replace!")


with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated prompt input logic successfully!")
