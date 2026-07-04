import re

with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith('                page = await browser.new_page()'):
        new_lines.append('                  page = await browser.new_page()\n')
    elif line.startswith('                await page.goto("https://labs.google/fx/")'):
        new_lines.append('                  await page.goto("https://labs.google/fx/")\n')
    elif line.startswith('                # Poll for 180 seconds'):
        new_lines.append('                  # Poll for 180 seconds\n')
    elif line.startswith('                for _ in range(180):'):
        new_lines.append('                  for _ in range(180):\n')
    elif line.startswith('                    await asyncio.sleep(2)'):
        new_lines.append('                      await asyncio.sleep(2)\n')
    elif line.startswith('                    url = page.url or ""'):
        new_lines.append('                      url = page.url or ""\n')
    elif line.startswith('                    '):
        new_lines.append('  ' + line)
    else:
        new_lines.append(line)

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
