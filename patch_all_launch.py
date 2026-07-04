import re

with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix _sync_account_tier _launch_browser
content = re.sub(
    r'return await asyncio\.wait_for\(p\.chromium\.launch_persistent_context\(\s*user_data_dir=cookie_path,\s*headless=True,\s*executable_path=find_chrome\(\),\s*args=args\),\s*timeout=15\.0\)',
    r'''for attempt in range(5):
                      try:
                          return await asyncio.wait_for(p.chromium.launch_persistent_context(
                              user_data_dir=cookie_path, headless=True, executable_path=find_chrome(), args=args), timeout=15.0)
                      except Exception as e:
                          if attempt == 4: raise e
                          await asyncio.sleep(1)''',
    content,
    flags=re.DOTALL
)

# Fix _sync_account_tier finally block
content = re.sub(
    r'finally:\s*if \'browser\' in locals\(\) and browser:\s*await browser\.close\(\)',
    r'''finally:
                  if 'browser' in locals() and browser:
                        try: await browser.close()
                        except Exception: pass''',
    content,
    flags=re.DOTALL
)

# Fix _async_health_check launch
content = re.sub(
    r'browser = await asyncio\.wait_for\(p\.chromium\.launch_persistent_context\(\s*user_data_dir=cookie_path, headless=True, executable_path=chrome_exe,\s*args=\["--no-first-run", "--disable-infobars"\]\s*\), timeout=15\.0\)',
    r'''for attempt in range(5):
                    try:
                        browser = await asyncio.wait_for(p.chromium.launch_persistent_context(
                            user_data_dir=cookie_path, headless=True, executable_path=chrome_exe,
                            args=["--no-first-run", "--disable-infobars"]
                        ), timeout=15.0)
                        break
                    except Exception as e:
                        if attempt == 4: raise e
                        await asyncio.sleep(1)''',
    content,
    flags=re.DOTALL
)

# Fix _async_health_check finally
content = re.sub(
    r'finally:\s*if browser:\s*try:\s*await browser\.close\(\)\s*except:\s*pass',
    r'''finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass''',
    content,
    flags=re.DOTALL
)

# Fix _async_renew_session launch
content = re.sub(
    r'browser = await asyncio\.wait_for\(p\.chromium\.launch_persistent_context\(\s*user_data_dir=account\.cookie_path,\s*headless=True,\s*executable_path=chrome_exe,\s*args=\[\s*"--window-size=1,1",\s*"--window-position=-2000,-2000",\s*"--no-first-run",\s*"--disable-blink-features=AutomationControlled",\s*"--disable-infobars",\s*"--disable-extensions",\s*"--disable-features=TranslateUI,GlobalMediaControls",\s*\],\s*\), timeout=15\.0\)',
    r'''for attempt in range(5):
                    try:
                        browser = await asyncio.wait_for(p.chromium.launch_persistent_context(
                            user_data_dir=account.cookie_path,
                            headless=True,
                            executable_path=chrome_exe,
                            args=[
                                "--no-first-run",
                                "--disable-blink-features=AutomationControlled",
                                "--disable-infobars",
                                "--disable-extensions",
                                "--disable-features=TranslateUI,GlobalMediaControls",
                            ],
                        ), timeout=15.0)
                        break
                    except Exception as e:
                        if attempt == 4: raise e
                        await asyncio.sleep(1)''',
    content,
    flags=re.DOTALL
)

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(content)
