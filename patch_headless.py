import re

with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace _launch_browser in _sync_account_tier
old_launch_sync = """            async def _launch_browser(p, visible=False):
                from utils.platform import find_chrome
                args = ['--no-first-run', '--disable-blink-features=AutomationControlled', '--disable-infobars', '--disable-extensions']
                if not visible:
                    args += ['--window-size=1,1', '--window-position=-2000,-2000']
                else:
                    args += ['--window-size=1024,768']
                return await asyncio.wait_for(p.chromium.launch_persistent_context(
                    user_data_dir=cookie_path, headless=False, executable_path=find_chrome(), args=args), timeout=15.0)"""

new_launch_sync = """            async def _launch_browser(p, visible=False):
                from utils.platform import find_chrome
                args = ['--no-first-run', '--disable-blink-features=AutomationControlled', '--disable-infobars', '--disable-extensions']
                return await asyncio.wait_for(p.chromium.launch_persistent_context(
                    user_data_dir=cookie_path, headless=True, executable_path=find_chrome(), args=args), timeout=15.0)"""

if old_launch_sync in content:
    content = content.replace(old_launch_sync, new_launch_sync)
else:
    print("WARNING: Could not find old_launch_sync")

# Replace browser launch in _async_health_check
old_launch_health = """                browser = await asyncio.wait_for(p.chromium.launch_persistent_context(
                    user_data_dir=cookie_path, headless=False, executable_path=chrome_exe,
                    args=["--no-first-run", "--disable-infobars", "--window-size=1280,800"]
                ), timeout=15.0)"""

new_launch_health = """                browser = await asyncio.wait_for(p.chromium.launch_persistent_context(
                    user_data_dir=cookie_path, headless=True, executable_path=chrome_exe,
                    args=["--no-first-run", "--disable-infobars"]
                ), timeout=15.0)"""

if old_launch_health in content:
    content = content.replace(old_launch_health, new_launch_health)
else:
    print("WARNING: Could not find old_launch_health")

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(content)
