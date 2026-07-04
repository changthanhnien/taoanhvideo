with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'is_signin = await page.evaluate(' in line and '!!document.querySelector' in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'is_signin = await page.evaluate("""!!document.querySelector(\'input[type="email"]\') || document.body.innerText.includes("Đăng nhập") || document.body.innerText.includes("Sign in")""")\n')
    else:
        new_lines.append(line)

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
