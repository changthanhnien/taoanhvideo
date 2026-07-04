import re

with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

# For _sync_account_tier
old_sync_t2 = """                    # LAYER 2
                    await page.goto('https://labs.google/fx/vi/tools/flow', wait_until='domcontentloaded')
                    await asyncio.sleep(4)
                    html = (await page.content()).lower()
                    video_fx_ok = google_ok and 'sign in to get a sneak peek' not in html and "you don't have access" not in html and 'đăng nhập để xem' not in html
                    
                    if not google_ok or not video_fx_ok:
                        return 'Phiên đăng nhập hết hạn. Vui lòng bấm \\\'Sửa\\\' để đăng nhập lại.'
                        
                    # LAYER 3
                    tier = 'Thường'
                    session = await page.evaluate('''async () => { try { const r = await fetch('https://labs.google/fx/api/auth/session'); return await r.json(); } catch(e) { return {}; } }''')
                    token = (session or {}).get('accessToken') or (session or {}).get('access_token')"""

new_sync_t2 = """                    # LAYER 2 & 3: NextAuth API
                    session = await page.evaluate('''async () => { try { const r = await fetch('https://labs.google/fx/api/auth/session'); return await r.json(); } catch(e) { return {}; } }''')
                    token = (session or {}).get('accessToken') or (session or {}).get('access_token')
                    video_fx_ok = google_ok and bool(token)
                    
                    if not google_ok or not video_fx_ok:
                        return 'Tài khoản cần cấp lại quyền hoặc đăng nhập lại. Vui lòng bấm \\\'Sửa\\\'.'
                        
                    tier = 'Thường'"""

if old_sync_t2 in content:
    content = content.replace(old_sync_t2, new_sync_t2)
else:
    print("WARNING: Could not find old_sync_t2")

# For _async_health_check
old_health_t2 = """                # TẦNG 2: VIDEO FX ACCESS
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
                token = (session or {}).get("accessToken") or (session or {}).get("access_token")"""

new_health_t2 = """                # TẦNG 2: VIDEO FX ACCESS (API CHECK)
                emit("TẦNG 2: Video FX Access", "WAITING...")
                session = await page.evaluate('''async () => {
                    try {
                        const r = await fetch("https://labs.google/fx/api/auth/session");
                        return await r.json();
                    } catch(e) { return {}; }
                }''')
                token = (session or {}).get("accessToken") or (session or {}).get("access_token")
                video_fx_access = google_logged_in and bool(token)
                emit("TẦNG 2: Video FX Access", "OK" if video_fx_access else "FAIL (Mất token Video FX)")
                
                # CHÚT LOGIC:
                if google_logged_in and video_fx_access:
                    emit("Session tổng thể", "PASS (Không bị hết hạn)")
                else:
                    emit("Session tổng thể", "FAIL (Cần bấm 'Sửa' để cấp quyền lại)")
                    return
                
                # TẦNG 3: PLAN DETECTOR
                emit("TẦNG 3: Plan Detector", "WAITING...")
                tier = "Thường"
                await page.goto("https://labs.google/fx/vi/tools/flow", wait_until="networkidle")
                await asyncio.sleep(2)"""

if old_health_t2 in content:
    content = content.replace(old_health_t2, new_health_t2)
else:
    print("WARNING: Could not find old_health_t2")

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(content)
