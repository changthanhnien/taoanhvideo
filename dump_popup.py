import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        user_data_dir = r"C:\Users\ASUS\AppData\Local\Google\Chrome\User Data"
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=False
        )
        page = await browser.new_page()
        await page.goto("https://flow.google.com/")
        print("Waiting 10s for page load...")
        await asyncio.sleep(10)
        
        # Try to open popup
        await page.evaluate('''() => {
            const ta = document.querySelector('textarea[aria-label*="create"], textarea[placeholder*="create"], textarea');
            if (ta) {
                const container = ta.closest('div.input-container, div[class*="chat"], div[class*="prompt"]') || ta.parentElement.parentElement;
                if (container) {
                    const btns = Array.from(container.querySelectorAll('button, [role="button"]'));
                    const pill = btns.find(b => {
                        const text = (b.innerText || "").toLowerCase();
                        return text.includes("veo") || text.includes("imagen") || text.includes("nano") || text.includes("video") || text.includes("image") || text.includes("16:9") || text.includes("1x");
                    });
                    if (pill) pill.click();
                    else {
                        const sliderBtn = btns.find(b => b.innerHTML.includes('M3 17v2h6') || b.innerHTML.includes('M3,17'));
                        if (sliderBtn) sliderBtn.click();
                    }
                }
            }
        }''')
        print("Waiting 2s for popup...")
        await asyncio.sleep(2)
        
        popup_html = await page.evaluate('''() => {
            const popups = Array.from(document.querySelectorAll('md-menu[open], [role="menu"], [role="dialog"], .cdk-overlay-pane'));
            const p = popups.find(p => p.innerText && (p.innerText.includes("Aspect ratio") || p.innerText.includes("Mode") || p.innerText.includes("Tỷ lệ") || p.innerText.includes("16:9")));
            return p ? p.innerHTML : "No popup found";
        }''')
        
        with open("popup_dump.html", "w", encoding="utf-8") as f:
            f.write(popup_html)
            
        print("Dumped to popup_dump.html")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
