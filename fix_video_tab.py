import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_tab_code = """                # Switch to Video tab
                video_tab = await self._page.query_selector('button:has-text("Video")')
                if video_tab and await video_tab.is_visible():
                    await video_tab.click()
                    await asyncio.sleep(1)"""

new_tab_code = """                # Switch to Video tab
                video_tabs = await self._page.query_selector_all('[role="tab"]:has-text("Video"), button:text-is("Video"), md-primary-tab:has-text("Video"), div[role="tab"]:has-text("Video")')
                for tab in video_tabs:
                    if await tab.is_visible():
                        await tab.click()
                        await asyncio.sleep(1)
                        break"""

if old_tab_code in content:
    content = content.replace(old_tab_code, new_tab_code)
    with open('services/flow_client.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Injected video_tab fix successfully!")
else:
    print("Could not find old_tab_code in flow_client.py")
