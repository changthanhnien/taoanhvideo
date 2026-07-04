import re

with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = "            logs = await self._page.evaluate(f'''([ratioKws, durKws, countKw]) => {{"
start_idx = content.find(start_marker)

end_marker = '            log.info(f"UI Auto: Configuration result: {logs}")'
end_idx = content.find(end_marker, start_idx)

if start_idx != -1 and end_idx != -1:
    new_block = '''            logs = []
            try:
                import re
                # Find the popup using playwright locator
                popup = self._page.locator('md-menu[open], [role="menu"], [role="dialog"], .cdk-overlay-pane').filter(has_text=re.compile(r"aspect ratio|mode|tỷ lệ|16:9|nano|veo|video", re.IGNORECASE)).first
                await popup.wait_for(state="visible", timeout=3000)
                
                async def pw_click(keywords):
                    for kw in keywords:
                        try:
                            # Try role tab/radio/button first
                            btn = popup.get_by_role("tab", name=re.compile(kw, re.IGNORECASE)).first
                            if await btn.is_visible(timeout=200):
                                await btn.click(timeout=1000)
                                logs.append(f"Clicked tab: {kw}")
                                return True
                        except: pass
                        try:
                            btn = popup.get_by_text(kw, exact=True).first
                            if await btn.is_visible(timeout=200):
                                await btn.click(timeout=1000)
                                logs.append(f"Clicked exact: {kw}")
                                return True
                        except: pass
                        try:
                            btn = popup.locator(f"text=/{kw}/i").first
                            if await btn.is_visible(timeout=200):
                                await btn.click(timeout=1000)
                                logs.append(f"Clicked regex: {kw}")
                                return True
                        except: pass
                    logs.append(f"Not found: {keywords[0]}")
                    return False

                # 1. Click Video Mode
                await pw_click(["Video", "Veo", "Ảnh -> Video"])
                await asyncio.sleep(0.5)
                
                # 2. Click Aspect Ratio
                await pw_click(ratio_kws)
                await asyncio.sleep(0.5)
                
                # 3. Click Duration
                await pw_click(dur_kws)
                await asyncio.sleep(0.5)
                
                # 4. Click Count
                await pw_click([count_kw])
                
            except Exception as e:
                logs.append(f"Popup manipulation error: {e}")
            
'''

    new_content = content[:start_idx] + new_block + content[end_idx:]
    with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Fixed!")
else:
    print(f"Failed to find markers: start={start_idx}, end={end_idx}")
