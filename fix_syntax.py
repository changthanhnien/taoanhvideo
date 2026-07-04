with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('!!document.querySelector(\'input[type="email"]\')', '!!document.querySelector("input[type=\\"email\\"]")')

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(content)
