import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_pill_search = """
            # Find the pill button containing current settings
            for b in buttons:
                if await b.is_visible():
                    txt = await b.inner_text()
                    if txt and ('Video' in txt or 'Hình ảnh' in txt or 'Image' in txt) and ('[' in txt or '·' in txt or 'x' in txt.lower() or 's' in txt.lower()) and len(txt.strip()) < 30:
                        # The pill button usually has these keywords
                        settings_btn = b
                        break
"""

new_pill_search = """
            # Find the pill button containing current settings
            import re
            for b in buttons:
                if await b.is_visible():
                    txt = await b.inner_text()
                    # The pill button always contains either duration (8s), count (x4), model name (Veo, Nano), or separators
                    if txt and (re.search(r'\\b[xX][1-4]\\b', txt) or re.search(r'\\b[468]s\\b', txt) or '·' in txt or '[' in txt or 'Veo' in txt or 'Nano' in txt) and len(txt.strip()) < 40:
                        settings_btn = b
                        break
"""

if old_pill_search.strip() in content:
    content = content.replace(old_pill_search.strip(), new_pill_search.strip())
else:
    print("WARNING: Could not find old_pill_search to replace!")


old_settings_config = """
                # 1. Ratio (Segment buttons)
"""

new_settings_config = """
                # 0. Switch to Video mode if needed
                log.info("UI Auto: Switching to Video tab...")
                await click_segment_button(["Video"])
                await asyncio.sleep(1.0)

                # 1. Ratio (Segment buttons)
"""

if old_settings_config.strip() in content:
    content = content.replace(old_settings_config.strip(), new_settings_config.strip())
else:
    print("WARNING: Could not find old_settings_config to replace!")

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated pill button and Video tab logic successfully!")
