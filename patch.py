import re

with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('def _sync_account_tier(self, account, btn):')
end_idx = content.find('def _on_sync_success(self, account_id: int, tier: str):')

new_func = """    def _sync_account_tier(self, account, btn):
        async def _run_test():
            from playwright.async_api import async_playwright
            cookie_path = account.cookie_path
            
            async def _launch_browser(p, visible=False):
                from utils.platform import find_chrome
                args = ['--no-first-run', '--disable-blink-features=AutomationControlled', '--disable-infobars', '--disable-extensions']
                if not visible:
                    args += ['--window-size=1,1', '--window-position=-2000,-2000']
                else:
                    args += ['--window-size=1024,768']
                return await asyncio.wait_for(p.chromium.launch_persistent_context(
                    user_data_dir=cookie_path, headless=False, executable_path=find_chrome(), args=args), timeout=15.0)

            try:
                async with async_playwright() as p:
                    browser = await _launch_browser(p, visible=False)
                    page = await browser.new_page()
                    
                    # LAYER 1: GOOGLE SESSION
                    await page.goto('https://myaccount.google.com/', wait_until='domcontentloaded')
                    await asyncio.sleep(2)
                    google_ok = not await page.evaluate('!!document.querySelector("input[type=\\"email\\"]") || document.body.innerText.includes("Đăng nhập")')
                    
                    # LAYER 2: VIDEO FX ACCESS
                    await page.goto('https://labs.google/fx/vi/tools/flow', wait_until='domcontentloaded')
                    await asyncio.sleep(4)
                    html = (await page.content()).lower()
                    video_fx_ok = google_ok and 'sign in to get a sneak peek' not in html and "you don't have access" not in html and 'đăng nhập để xem' not in html
                    
                    if not google_ok or not video_fx_ok:
                        return "Phiên đăng nhập hết hạn. Vui lòng bấm 'Sửa' để đăng nhập lại."
                        
                    # LAYER 3: PLAN DETECTOR
                    tier = 'Thường'
                    session = await page.evaluate('''async () => { try { const r = await fetch('https://labs.google/fx/api/auth/session'); return await r.json(); } catch(e) { return {}; } }''')
                    token = (session or {}).get('accessToken') or (session or {}).get('access_token')
                    
                    plan_found = False
                    if token:
                        api_res = await page.evaluate('''async ({url, token}) => { try { const r = await fetch(url, { headers: {'Authorization': 'Bearer ' + token} }); return r.ok ? await r.json() : {}; } catch(e) { return {}; } }''', {'url': 'https://labs.google/fx/api/trpc/videoFx.getUser?input=%7B%7D', 'token': token})
                        data = str(((api_res or {}).get('result', {}).get('data', {}).get('json')) or {}).lower()
                        if 'ultra' in data: tier = 'Ultra'; plan_found = True
                        elif 'tier_two' in data or 'pro' in data or 'paygate' in data: tier = 'Pro'; plan_found = True
                    
                    if not plan_found:
                        texts = await page.evaluate('() => { let walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false); let n; let res = ""; while(n = walker.nextNode()) res += n.nodeValue + " "; return res.toLowerCase(); }')
                        if 'ultra' in texts: tier = 'Ultra'
                        elif 'pro' in texts or 'tier 2' in texts: tier = 'Pro'
                        
                    return tier
            except Exception as e:
                return str(e)
            finally:
                if 'browser' in locals() and browser:
                    await browser.close()
                    
        import threading
        def worker():
            import asyncio
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            try:
                tier = asyncio.run(_run_test())
            except Exception as e:
                tier = str(e)
                
            if tier in ('Pro', 'Ultra', 'Thường'):
                QMetaObject.invokeMethod(self, '_on_sync_success', Qt.QueuedConnection, Q_ARG(int, account.id), Q_ARG(str, tier))
            else:
                QMetaObject.invokeMethod(self, '_on_sync_failed', Qt.QueuedConnection, Q_ARG(str, tier))
                
        threading.Thread(target=worker, daemon=True).start()

    """

new_content = content[:start_idx] + new_func + content[end_idx:]

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
