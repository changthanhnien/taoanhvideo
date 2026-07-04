import os

p = r'd:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\workers\execute_new.py'
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# Fix the result parsing logic for images!
old_parse = """                    if result and isinstance(result, list):
                        result_urls.extend([r.get("mediaId") for r in result if r.get("mediaId")])"""

new_parse = """                    if result:
                        if isinstance(result, list):
                            result_urls.extend([r.get("mediaId") for r in result if isinstance(r, dict) and r.get("mediaId")])
                        elif isinstance(result, dict) and "media" in result:
                            for m in result["media"]:
                                url = m.get("image", {}).get("generatedImage", {}).get("url")
                                if url:
                                    result_urls.append(url)"""

c = c.replace(old_parse, new_parse)

with open(p, 'w', encoding='utf-8') as f:
    f.write(c)

print('Patched execute_new.py')
