with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(485, 505):
    if i < len(lines):
        if lines[i] == '                  await asyncio.sleep(2)\n':
            lines[i] = '                    await asyncio.sleep(2)\n'
        elif lines[i] == '                  url = page.url or ""\n':
            lines[i] = '                    url = page.url or ""\n'

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
