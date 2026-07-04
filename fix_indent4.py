with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith('                  page = await browser.new_page()'):
        lines[i] = line.replace('                  ', '                ')
    elif line.startswith('                  await page.goto("https://labs.google/fx/")'):
        lines[i] = line.replace('                  ', '                ')
    elif line.startswith('                  # Poll for 180 seconds'):
        lines[i] = line.replace('                  ', '                ')
    elif line.startswith('                  for _ in range(180):'):
        lines[i] = line.replace('                  ', '                ')
    elif line.startswith('                    await asyncio.sleep(2)'):
        lines[i] = line.replace('                    ', '                  ')
    elif line.startswith('                    url = page.url or ""'):
        lines[i] = line.replace('                    ', '                  ')
    elif line.startswith('                    await asyncio.wait_for(client.check_credits(), timeout=30.0)'):
        lines[i] = line.replace('                    ', '                  ')
    elif line.startswith('                    pass'):
        lines[i] = line.replace('                    ', '                  ')

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
