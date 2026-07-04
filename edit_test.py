import re

with open('test_video_flow.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_code = """
            htmls = await page.evaluate('() => Array.from(document.querySelectorAll("button, [role=button]")).map(b => b.outerHTML).join("\\n")')
            with open('buttons.txt', 'w', encoding='utf-8') as bf:
                bf.write(htmls)
            await asyncio.sleep(5)
"""

content = content.replace("await asyncio.sleep(45)", new_code)

with open('test_video_flow.py', 'w', encoding='utf-8') as f:
    f.write(content)
