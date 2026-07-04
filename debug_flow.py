import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    user_data = r"C:\Users\ASUS\AppData\Local\Google\Chrome\User Data"
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=user_data,
                headless=False,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )
        except Exception as e:
            print(f"Failed to launch Chrome (profile locked?): {e}")
            return
            
        page = await browser.new_page()
        print("Navigating to Flow...")
        await page.goto("https://flow.google/create", timeout=60000)
        await asyncio.sleep(5)
        
        # Click settings pill
        print("Looking for settings pill...")
        pill = None
        for text in ["Video", "Veo", "16:9", "Image", "Nano"]:
            els = await page.get_by_text(text).all()
            for el in els:
                if await el.is_visible():
                    pill = await el.evaluate_handle('el => el.closest("button, [role=\'button\'], md-suggestion-chip, div") || el')
                    break
            if pill: break
            
        if pill:
            print("Clicking settings pill...")
            await pill.as_element().click(force=True)
            await asyncio.sleep(3)
            
            # Switch to Video tab
            tabs = await page.get_by_text("Video", exact=True).all()
            for t in tabs:
                if await t.is_visible():
                    try:
                        await t.click(force=True)
                        await asyncio.sleep(2)
                        break
                    except: pass
                    
            print("Taking screenshot...")
            await page.screenshot(path="flow_settings.png", full_page=True)
            
            print("Dumping HTML...")
            html = await page.content()
            with open("flow_settings.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("SUCCESS")
        else:
            print("Failed to find settings pill")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
