import re

with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(
    r'# LAYER 2: VIDEO FX ACCESS.*?# LAYER 3: PLAN DETECTOR\s+tier = \'Thường\'\s+session = await page\.evaluate\(\'\'\'async \(\) => { try { const r = await fetch\(\'https://labs\.google/fx/api/auth/session\'\); return await r\.json\(\); } catch\(e\) { return {}; } }\'\'\'\)\s+token = \(session or {}\)\.get\(\'accessToken\'\) or \(session or {}\)\.get\(\'access_token\'\)',
    r'''# LAYER 2 & 3: NextAuth API
                    session = await page.evaluate(\'\'\'async () => { try { const r = await fetch('https://labs.google/fx/api/auth/session'); return await r.json(); } catch(e) { return {}; } }\'\'\')
                    token = (session or {}).get('accessToken') or (session or {}).get('access_token')
                    video_fx_ok = google_ok and bool(token)
                    
                    if not google_ok or not video_fx_ok:
                        return "Tài khoản cần cấp quyền Video FX. Vui lòng bấm 'Sửa' để đăng nhập lại."
                        
                    # LAYER 3: PLAN DETECTOR
                    tier = 'Thường' ''',
    content,
    flags=re.DOTALL
)

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(content)
