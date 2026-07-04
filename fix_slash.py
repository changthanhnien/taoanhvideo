with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("session = await page.evaluate(\\'\\'\\'async () => { try { const r = await fetch('https://labs.google/fx/api/auth/session'); return await r.json(); } catch(e) { return {}; } }\\'\\'\\')", "session = await page.evaluate('''async () => { try { const r = await fetch('https://labs.google/fx/api/auth/session'); return await r.json(); } catch(e) { return {}; } }''')")

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(content)
