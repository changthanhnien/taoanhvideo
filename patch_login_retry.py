import re

with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_login_launch = """                  browser = await p.chromium.launch_persistent_context(
                      user_data_dir=str(profile_path),
                      headless=False,
                      executable_path=chrome_exe,
                      args=[
                          "--window-size=1024,768",
                          "--no-first-run",
                          "--disable-blink-features=AutomationControlled",
                          "--disable-infobars",
                          "--disable-extensions",
                      ],
                  )"""

new_login_launch = """                  # Retry loop to wait for profile lock to release if it was just closed by a background thread
                  for attempt in range(5):
                      try:
                          browser = await p.chromium.launch_persistent_context(
                              user_data_dir=str(profile_path),
                              headless=False,
                              executable_path=chrome_exe,
                              args=[
                                  "--window-size=1024,768",
                                  "--no-first-run",
                                  "--disable-blink-features=AutomationControlled",
                                  "--disable-infobars",
                                  "--disable-extensions",
                              ],
                          )
                          break
                      except Exception as e:
                          if attempt == 4:
                              raise e
                          await asyncio.sleep(1)"""

if old_login_launch in content:
    content = content.replace(old_login_launch, new_login_launch)
else:
    print('WARNING: Could not find old_login_launch')

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(content)
