import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=r"C:\Users\ASUS\AppData\Local\Google\Chrome\User Data",
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        page = await browser.new_page()
        await page.goto("https://flow.google/create")
        await asyncio.sleep(5)
        
        # Click settings pill
        pill = None
        for text in ["Video", "Veo", "16:9", "Image", "Nano"]:
            els = await page.get_by_text(text).all()
            for el in els:
                if await el.is_visible():
                    pill = await el.evaluate_handle('el => el.closest("button, [role=\'button\'], md-suggestion-chip, div") || el')
                    break
            if pill: break
            
        if pill:
            await pill.as_element().click()
            await asyncio.sleep(2)
            
            # Switch to Video tab
            tabs = await page.get_by_text("Video", exact=True).all()
            for t in tabs:
                if await t.is_visible():
                    try:
                        await t.click()
                        await asyncio.sleep(1)
                        break
                    except: pass
                    
            # Dump the popup HTML
            html = await page.content()
            with open("flow_settings_dump.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Dumped HTML to flow_settings_dump.html")
        else:
            print("Failed to find settings pill")
            
        await browser.close()

asyncio.run(main())
