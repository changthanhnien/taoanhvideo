import re

with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('    async def _async_health_check(self, account, dlg):')
# Find the end of _async_health_check by looking for the next top-level or class-level method, which is the end of the file or HealthCheckDialog class
end_idx = content.find('class HealthCheckDialog(', start_idx)
if end_idx == -1:
    end_idx = len(content)
else:
    # Go back before the class
    pass

new_func = """    async def _async_health_check(self, account, dlg):
        from PySide6.QtCore import QMetaObject, Qt, Q_ARG
        import os
        from playwright.async_api import async_playwright
        
        def emit(step, status):
            QMetaObject.invokeMethod(dlg, "add_step", Qt.QueuedConnection, Q_ARG(str, step), Q_ARG(str, status))
            
        emit("Đọc DB thành công", "PASS")
        
        if not account:
            emit("Tìm thấy account", "FAIL: Account rỗng")
            return
        emit("Tìm thấy account", f"PASS: {account.email}")
        
        cookie_path = account.cookie_path
        if not cookie_path:
            emit("Tìm thấy profile path", "FAIL: Profile path rỗng")
            return
        emit("Tìm thấy profile path", f"PASS: {cookie_path}")
        
        if not os.path.exists(cookie_path):
            emit("Profile tồn tại", "FAIL: Thư mục không tồn tại trên ổ đĩa")
            return
        emit("Profile tồn tại", "PASS")
        
        from utils.platform import find_chrome
        chrome_exe = find_chrome()
        browser = None
        try:
            async with async_playwright() as p:
                emit("Mở được profile", "WAITING...")
                browser = await asyncio.wait_for(p.chromium.launch_persistent_context(
                    user_data_dir=cookie_path, headless=False, executable_path=chrome_exe,
                    args=["--no-first-run", "--disable-infobars", "--window-size=1280,800"]
                ), timeout=15.0)
                emit("Mở được profile", "PASS")
                
                page = await browser.new_page()
                
                # TẦNG 1: GOOGLE SESSION
                emit("TẦNG 1: Google Session", "WAITING...")
                await page.goto("https://myaccount.google.com/", wait_until="domcontentloaded")
                await asyncio.sleep(2)
                is_signin = await page.evaluate("!!document.querySelector('input[type=\"email\"]') || document.body.innerText.includes('Đăng nhập') || document.body.innerText.includes('Sign in')")
                google_logged_in = not is_signin
                emit("TẦNG 1: Google Session", "OK" if google_logged_in else "FAIL")
                
                # TẦNG 2: VIDEO FX ACCESS
                emit("TẦNG 2: Video FX Access", "WAITING...")
                await page.goto("https://labs.google/fx/vi/tools/flow", wait_until="domcontentloaded")
                await asyncio.sleep(4)
                html = (await page.content()).lower()
                video_fx_access = False
                if google_logged_in:
                    if "sign in to get a sneak peek" not in html and "you don't have access" not in html and "đăng nhập để xem" not in html:
                        video_fx_access = True
                emit("TẦNG 2: Video FX Access", "OK" if video_fx_access else "FAIL")
                
                # CHÚT LOGIC:
                if google_logged_in and video_fx_access:
                    emit("Session tổng thể", "PASS (Không bị hết hạn)")
                else:
                    emit("Session tổng thể", "FAIL (Cần đăng nhập lại)")
                    return
                
                # TẦNG 3: PLAN DETECTOR
                emit("TẦNG 3: Plan Detector", "WAITING...")
                tier = "Thường"
                session = await page.evaluate('''async () => {
                    try {
                        const r = await fetch("https://labs.google/fx/api/auth/session");
                        return await r.json();
                    } catch(e) { return {}; }
                }''')
                token = (session or {}).get("accessToken") or (session or {}).get("access_token")
                
                plan_found = False
                if token:
                    api_res = await page.evaluate('''async ({url, token}) => {
                        try {
                            const r = await fetch(url, { headers: {"Authorization": "Bearer " + token} });
                            return r.ok ? await r.json() : {};
                        } catch(e) { return {}; }
                    }''', {"url": "https://labs.google/fx/api/trpc/videoFx.getUser?input=%7B%7D", "token": token})
                    api_data = str(((api_res or {}).get("result", {}).get("data", {}).get("json")) or {}).lower()
                    if "ultra" in api_data:
                        tier = "Ultra"
                        plan_found = True
                    elif "tier_two" in api_data or "pro" in api_data or "paygate" in api_data:
                        tier = "Pro"
                        plan_found = True
                
                if not plan_found:
                    texts = await page.evaluate('''() => {
                        let walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                        let n; let res = "";
                        while(n = walker.nextNode()) res += n.nodeValue + " ";
                        return res.toLowerCase();
                    }''')
                    if "ultra" in texts: tier = "Ultra"
                    elif "pro" in texts or "tier 2" in texts: tier = "Pro"
                
                emit("TẦNG 3: Plan Detector", tier)
                
                # Lấy Screenshot
                proof_path = str(Path(os.getcwd()) / "proof_debug_ui.png")
                await page.screenshot(path=proof_path)
                emit("Lấy Bằng Chứng", "PASS (proof_debug_ui.png)")
                
                emit("Cập nhật UI & DB", "Đang xử lý...")
                account.tier = tier
                self.db.update_account(account)
                QMetaObject.invokeMethod(self, "_load_accounts", Qt.QueuedConnection)
                emit("Cập nhật UI & DB", "PASS")
                emit("HOÀN TẤT", "Thành công!")
                
        except asyncio.TimeoutError:
            emit("Lỗi", "Quá thời gian chờ trình duyệt")
        except Exception as e:
            emit("Lỗi", str(e))
        finally:
            if browser:
                try:
                    await browser.close()
                except:
                    pass

"""

new_content = content[:start_idx] + new_func + "\n\n" + content[end_idx:]

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
