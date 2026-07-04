import re

with open("automation/browser_manager.py", "r", encoding="utf-8") as f:
    code = f.read()

old_block = """            import json as _json

            has_persistent_profile = False
        if cookie_path and Path(cookie_path).exists():
            if (Path(cookie_path) / "Default").exists() or (Path(cookie_path) / "Local State").exists():
                has_persistent_profile = True
                
        cookies = []
        if not has_persistent_profile and cookie_path and Path(cookie_path).exists():
            cookies_file = Path(cookie_path) / "cookies_export.json"
            if cookies_file.exists():
                try:
                    with open(cookies_file, "r", encoding="utf-8") as f:
                        cookies = _json.load(f)
                    log.info(f"Loaded {len(cookies)} cookies from {cookies_file}")
                except Exception as e:
                    log.warning(f"Failed to load cookies: {e}")

        if not has_persistent_profile and not cookies:
            raise RuntimeError(f"No cookies for {email}. Please login/renew account first.")

        self._profiles[account_id] = cookie_path or ""
        pw = self._playwrights[account_id]

        log.info(f"Launching Chromium for {email}...")
        chrome_exe = find_chrome()
        if chrome_exe:
            log.info(f"Using system Chrome: {chrome_exe}")
        else:
            log.info("System Chrome not found, fallback to bundled chromium")

        args = [
            "--window-size=1024,768",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-default-apps",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-extensions",
            "--disable-features=TranslateUI,GlobalMediaControls",
        ]

        if has_persistent_profile:
            log.info(f"Using persistent profile at {cookie_path}")
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=cookie_path,
                headless=False,
                executable_path=chrome_exe,
                args=args,
            )
            # Store 'browser' as the context itself for cleanup compatibility
            self._browsers[account_id] = context
        else:
            browser = await pw.chromium.launch(
                headless=False,
                executable_path=chrome_exe,
                args=args,
            )
            self._browsers[account_id] = browser
            context = await browser.new_context()
            if cookies:
                await context.add_cookies(cookies)
                log.info(f"Chromium ready for {email} ({len(cookies)} cookies injected)")

        self._pages[account_id] = context.pages
        return context"""

new_block = """            import json as _json

            has_persistent_profile = False
            if cookie_path and Path(cookie_path).exists():
                if (Path(cookie_path) / "Default").exists() or (Path(cookie_path) / "Local State").exists():
                    has_persistent_profile = True
                    
            cookies = []
            if not has_persistent_profile and cookie_path and Path(cookie_path).exists():
                cookies_file = Path(cookie_path) / "cookies_export.json"
                if cookies_file.exists():
                    try:
                        with open(cookies_file, "r", encoding="utf-8") as f:
                            cookies = _json.load(f)
                        log.info(f"Loaded {len(cookies)} cookies from {cookies_file}")
                    except Exception as e:
                        log.warning(f"Failed to load cookies: {e}")

            if not has_persistent_profile and not cookies:
                raise RuntimeError(f"No cookies for {email}. Please login/renew account first.")

            self._profiles[account_id] = cookie_path or ""
            pw = self._playwrights[account_id]

            log.info(f"Launching Chromium for {email}...")
            chrome_exe = find_chrome()
            if chrome_exe:
                log.info(f"Using system Chrome: {chrome_exe}")
            else:
                log.info("System Chrome not found, fallback to bundled chromium")

            args = [
                "--window-size=1024,768",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-default-apps",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-extensions",
                "--disable-features=TranslateUI,GlobalMediaControls",
            ]

            if has_persistent_profile:
                log.info(f"Using persistent profile at {cookie_path}")
                context = await pw.chromium.launch_persistent_context(
                    user_data_dir=cookie_path,
                    headless=False,
                    executable_path=chrome_exe,
                    args=args,
                )
                # Store 'browser' as the context itself for cleanup compatibility
                self._browsers[account_id] = context
            else:
                browser = await pw.chromium.launch(
                    headless=False,
                    executable_path=chrome_exe,
                    args=args,
                )
                self._browsers[account_id] = browser
                context = await browser.new_context()
                if cookies:
                    await context.add_cookies(cookies)
                    log.info(f"Chromium ready for {email} ({len(cookies)} cookies injected)")

            self._pages[account_id] = context.pages
            return context"""

code = code.replace(old_block, new_block)

with open("automation/browser_manager.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Updated browser_manager.py")
