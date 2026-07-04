import asyncio
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.async_api import async_playwright
from utils.platform import find_chrome
from models.database import Database

def p(msg):
    try:
        print(msg)
    except:
        print(msg.encode('ascii', 'replace').decode('ascii'))

async def dump_settings():
    db = Database()
    db.connect()
    accounts = db.get_accounts(enabled_only=True)
    if not accounts:
        p("No enabled accounts!")
        return

    cookie_path = accounts[0].cookie_path
    chrome_exe = find_chrome()

    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.launch_persistent_context(
            user_data_dir=cookie_path,
            headless=True,
            executable_path=chrome_exe,
            args=["--window-size=1280,900"],
        )
        page = await browser.new_page()

        p("=== Navigate to Flow ===")
        await page.goto("https://labs.google/fx/vi/tools/flow", wait_until="networkidle")
        await asyncio.sleep(5)

        # Click new project
        new_btn = await page.query_selector('button:has-text("Dự án mới")')
        if not new_btn:
            new_btn = await page.query_selector('button:has-text("add_2")')
        if new_btn:
            await new_btn.click()
            await page.wait_for_url("**/flow/project/**", timeout=15000)
            await asyncio.sleep(5)
            
            # Find and click settings pill
            settings_btn = await page.wait_for_selector('div.pill.settings, button[aria-label*="Setting"], md-filled-tonal-button:has-text("Setting")', timeout=5000)
            if settings_btn:
                await settings_btn.click(force=True)
                await asyncio.sleep(2)
                
                # Switch to Video tab
                video_tabs = await page.query_selector_all('[role="tab"]:has-text("Video"), button:text-is("Video"), md-primary-tab:has-text("Video"), div[role="tab"]:has-text("Video")')
                for tab in video_tabs:
                    if await tab.is_visible():
                        await tab.click()
                        await asyncio.sleep(2)
                        break
                        
                # Dump ALL buttons, dropdowns and comboboxes
                els = await page.query_selector_all('md-outlined-select, md-select, [role="combobox"], button, md-radio, .segment, label')
                for el in els:
                    if await el.is_visible():
                        tag = await el.evaluate("el => el.tagName")
                        text = await el.inner_text()
                        role = await el.get_attribute("role")
                        p(f"[{tag}] role={role} text={text.replace(chr(10), ' | ')}")
                        
                # Dump HTML of the settings panel
                html = await page.evaluate("() => document.querySelector('body').innerHTML")
                with open("settings_dump.html", "w", encoding="utf-8") as f:
                    f.write(html)
                p("HTML saved to settings_dump.html")
    finally:
        await browser.close()
        await pw.stop()

if __name__ == "__main__":
    asyncio.run(dump_settings())
