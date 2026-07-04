import asyncio
from playwright.async_api import async_playwright
import sqlite3
import json

def get_cookie_path():
    db = sqlite3.connect('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/.vidgen/vidgen.db')
    cursor = db.cursor()
    cursor.execute("SELECT cookie_path FROM accounts WHERE email='huyt7036@gmail.com'")
    row = cursor.fetchone()
    db.close()
    return row[0] if row else None

async def run_diag():
    cookie_path = get_cookie_path()
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=cookie_path,
            headless=True,
            args=['--no-first-run', '--disable-blink-features=AutomationControlled', '--disable-infobars', '--disable-extensions']
        )
        page = await browser.new_page()
        await page.goto('https://labs.google/fx/vi/tools/flow', wait_until='networkidle')
        
        texts = await page.evaluate('document.body.innerText')
        with open('inner_text.txt', 'w', encoding='utf-8') as f:
            f.write(texts)
            
        await browser.close()

if __name__ == '__main__':
    asyncio.run(run_diag())
