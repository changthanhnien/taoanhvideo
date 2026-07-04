with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace any occurrence of the bad string
# We want the python source to be:
# is_signin = await page.evaluate('!!document.querySelector("input[type=\\"email\\"]") || document.body.innerText.includes("Đăng nhập") || document.body.innerText.includes("Sign in")')
# Wait, let's just make it a triple quoted string!
import re

content = re.sub(
    r'is_signin = await page.evaluate\(.*?"!!document\.querySelector.*?\)',
    r'is_signin = await page.evaluate("""!!document.querySelector(\'input[type="email"]\') || document.body.innerText.includes("Đăng nhập") || document.body.innerText.includes("Sign in")""")',
    content,
    flags=re.DOTALL
)

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(content)
