import re

with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_sync_logic = """                      # LAYER 1: GOOGLE SESSION
                      await page.goto('https://myaccount.google.com/', wait_until='domcontentloaded')
                      await asyncio.sleep(2)
                      google_ok = not await page.evaluate(\"\"\"!!document.querySelector('input[type=\"email\"]') || document.body.innerText.includes(\"Đăng nhập\") || document.body.innerText.includes(\"Sign in\")\"\"\")
                      
                      # LAYER 2 & 3: NextAuth API
                      session = await page.evaluate('''async () => { try { const r = await fetch('https://labs.google/fx/api/auth/session'); return await r.json(); } catch(e) { return {}; } }''')
                      token = (session or {}).get('accessToken') or (session or {}).get('access_token')
                      video_fx_ok = google_ok and bool(token)
                      
                      if not google_ok or not video_fx_ok:
                          return \"Tài khoản cần cấp quyền Video FX. Vui lòng bấm 'Sửa' để đăng nhập lại.\"
                          
                      # LAYER 3: PLAN DETECTOR
                      tier = 'Thường' 
                      
                      plan_found = False
                      if token:
                          api_res = await page.evaluate('''async ({url, token}) => { try { const r = await fetch(url, { headers: {'Authorization': 'Bearer ' + token} }); return r.ok ? await r.json() : {}; } catch(e) { return {}; } }''', {'url': 'https://labs.google/fx/api/trpc/videoFx.getUser?input=%7B%7D', 'token': token})
                          data = str(((api_res or {}).get('result', {}).get('data', {}).get('json')) or {}).lower()
                          if 'ultra' in data: tier = 'Ultra'; plan_found = True
                          elif 'tier_two' in data or 'pro' in data or 'paygate' in data: tier = 'Pro'; plan_found = True
                      
                      if not plan_found:
                          texts = await page.evaluate('() => { let walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false); let n; let res = \"\"; while(n = walker.nextNode()) res += n.nodeValue + \" \"; return res.toLowerCase(); }')
                          if 'ultra' in texts: tier = 'Ultra'
                          elif 'pro' in texts or 'tier 2' in texts: tier = 'Pro'"""

new_sync_logic = """                      # LAYER 1: GOOGLE SESSION
                      await page.goto('https://myaccount.google.com/', wait_until='domcontentloaded')
                      await asyncio.sleep(2)
                      google_ok = not await page.evaluate(\"\"\"!!document.querySelector('input[type=\"email\"]') || document.body.innerText.includes(\"Đăng nhập\") || document.body.innerText.includes(\"Sign in\")\"\"\")
                      
                      # LAYER 2 & 3: NextAuth API
                      await page.goto(\"https://labs.google/fx/vi/tools/flow\", wait_until=\"domcontentloaded\")
                      await asyncio.sleep(2)
                      session = await page.evaluate('''async () => { try { const r = await fetch('https://labs.google/fx/api/auth/session', {credentials: \"include\"}); if (!r.ok) return {}; return await r.json(); } catch(e) { return {}; } }''')
                      token = (session or {}).get('accessToken') or (session or {}).get('access_token')
                      video_fx_ok = google_ok and bool(token)
                      
                      if not google_ok or not video_fx_ok:
                          return \"Tài khoản cần cấp quyền Video FX. Vui lòng bấm 'Sửa' để đăng nhập lại.\"
                          
                      # LAYER 3: PLAN DETECTOR
                      tier = 'Thường' 
                      
                      plan_found = False
                      if token:
                          api_res = await page.evaluate('''async ({url, token}) => { try { const r = await fetch(url, { headers: {'Authorization': 'Bearer ' + token} }); return r.ok ? await r.json() : {}; } catch(e) { return {}; } }''', {'url': 'https://labs.google/fx/api/trpc/videoFx.getUser?input=%7B%7D', 'token': token})
                          data = str(((api_res or {}).get('result', {}).get('data', {}).get('json')) or {}).lower()
                          if 'ultra' in data: tier = 'Ultra'; plan_found = True
                          elif 'tier_two' in data or 'pro' in data or 'paygate' in data: tier = 'Pro'; plan_found = True
                      
                      if not plan_found:
                          texts = await page.evaluate('() => { let walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false); let n; let res = \"\"; while(n = walker.nextNode()) res += n.nodeValue + \" \"; return res.toLowerCase(); }')
                          if 'ultra' in texts: tier = 'Ultra'
                          elif 'pro' in texts or 'tier 2' in texts: tier = 'Pro'"""

if old_sync_logic in content:
    content = content.replace(old_sync_logic, new_sync_logic)
else:
    print('WARNING: old_sync_logic not found')

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(content)
