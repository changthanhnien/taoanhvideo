with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(580, 620):
    if i < len(lines):
        line = lines[i]
        if line.startswith('                  page = await browser.new_page()'):
            lines[i] = '                page = await browser.new_page()\n'
        elif line.startswith('                  await page.goto("https://labs.google/fx/")'):
            lines[i] = '                await page.goto("https://labs.google/fx/")\n'
        elif line.startswith('                  # Poll for 180 seconds'):
            lines[i] = '                # Poll for 180 seconds\n'
        elif line.startswith('                  for _ in range(180):'):
            lines[i] = '                for _ in range(180):\n'
        elif line.startswith('                      await asyncio.sleep(2)'):
            lines[i] = '                    await asyncio.sleep(2)\n'
        elif line.startswith('                      url = page.url or ""'):
            lines[i] = '                    url = page.url or ""\n'
        elif line.startswith('                      await asyncio.wait_for(client.check_credits(), timeout=30.0)'):
            lines[i] = '                    await asyncio.wait_for(client.check_credits(), timeout=30.0)\n'
        elif line.startswith('                      pass'):
            lines[i] = '                    pass\n'

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
