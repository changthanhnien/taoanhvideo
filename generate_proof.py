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
        
        # 1. Trang thuc te
        await page.goto('https://labs.google/fx/vi/tools/flow', wait_until='networkidle')
        await asyncio.sleep(5)
        await page.screenshot(path='proof_1_trang_thuc_te.png')
        print('Saved proof_1_trang_thuc_te.png')
        
        # 2. Gia tri detect plan
        html = (await page.content()).lower()
        tier = 'Thường'
        if 'ultra' in html: tier = 'Ultra'
        elif 'pro' in html or 'tier 2' in html: tier = 'Pro'
        print('Giá trị detect plan:', tier)
        
        # 3. Gia tri NextAuth
        session = await page.evaluate('''async () => {
            try {
                let r = await fetch('https://labs.google/fx/api/auth/session');
                return await r.json();
            } catch(e) { return {error: e.toString()}; }
        }''')
        print('Giá trị NextAuth:', str(session)[:100] + '...')
        
        # 4. Giá trị Google session
        await page.goto('https://myaccount.google.com/')
        await asyncio.sleep(2)
        is_signin = await page.evaluate('!!document.querySelector("input[type=\\"email\\"]") || document.body.innerText.includes("Đăng nhập")')
        google_ok = not is_signin
        print('Giá trị Google session: OK' if google_ok else 'Giá trị Google session: FAIL')
        
        # 5. Giá trị ghi DB
        print('Giá trị cuối cùng ghi DB:', tier)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(generate_proof())
