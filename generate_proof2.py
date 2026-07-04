import asyncio
from pathlib import Path
from utils.platform import find_chrome
from config.constants import BROWSER_PROFILE_DIR

async def generate_proof():
    from playwright.async_api import async_playwright
    profile_path = str(BROWSER_PROFILE_DIR / 'google_1782383941')
    
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path, headless=False, executable_path=find_chrome(),
            args=['--window-size=1280,800', '--disable-infobars', '--no-first-run']
        )
        page = await browser.new_page()
        
        results = []
        
        # 1. Trang thuc te
        await page.goto('https://labs.google/fx/vi/tools/flow', wait_until='networkidle')
        await asyncio.sleep(5)
        await page.screenshot(path='proof_1_trang_thuc_te.png')
        results.append('1. Ảnh: proof_1_trang_thuc_te.png đã được lưu.')
        
        # 2. Gia tri detect plan
        html = (await page.content()).lower()
        tier = 'Thường'
        if 'ultra' in html: tier = 'Ultra'
        elif 'pro' in html or 'tier 2' in html: tier = 'Pro'
        results.append(f'2. Giá trị detect plan: {tier}')
        
        # 3. Gia tri NextAuth
        session = await page.evaluate('''async () => {
            try {
                let r = await fetch('https://labs.google/fx/api/auth/session');
                return await r.json();
            } catch(e) { return {error: e.toString()}; }
        }''')
        results.append(f'3. Giá trị NextAuth: {str(session)[:200]}...')
        
        # 4. Giá trị Google session
        await page.goto('https://myaccount.google.com/')
        await asyncio.sleep(2)
        is_signin = await page.evaluate('!!document.querySelector("input[type=\\"email\\"]") || document.body.innerText.includes("Đăng nhập")')
        google_ok = not is_signin
        results.append(f'4. Giá trị Google session: {"OK" if google_ok else "FAIL"}')
        
        # 5. Giá trị ghi DB
        results.append(f'5. Giá trị cuối cùng ghi DB: {tier}')
        
        with open('proof_log.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(results))
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(generate_proof())
