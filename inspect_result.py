"""Quick inspect: find img alt text on the result page."""
import asyncio, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.async_api import async_playwright
from utils.platform import find_chrome
from models.database import Database

async def main():
    db = Database(); db.connect()
    accounts = db.get_accounts(enabled_only=True)
    cookie_path = accounts[0].cookie_path
    chrome_exe = find_chrome()
    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir=cookie_path, headless=False, executable_path=chrome_exe,
        args=["--window-size=1280,900"])
    page = await browser.new_page()
    # Go directly to the last generated project
    await page.goto("https://labs.google/fx/vi/tools/flow", wait_until="networkidle")
    await asyncio.sleep(5)
    
    # Find all img elements
    print("\n=== ALL IMG ELEMENTS ===")
    imgs = await page.query_selector_all('img')
    for i, img in enumerate(imgs):
        visible = await img.is_visible()
        if not visible:
            continue
        alt = await img.get_attribute('alt') or ''
        src = (await img.get_attribute('src') or '')[:100]
        bbox = await img.bounding_box()
        bstr = f"w={bbox['width']:.0f} h={bbox['height']:.0f}" if bbox else "no-bbox"
        cls = (await img.get_attribute('class') or '')[:60]
        print(f"  img[{i}] alt='{alt}' {bstr} src='{src}' class='{cls}'")

    # Now click on one of the project cards to enter a project with results
    print("\n=== Looking for project cards (edit buttons) ===")
    edit_btns = await page.query_selector_all('button:has-text("edit")')
    for btn in edit_btns:
        visible = await btn.is_visible()
        if visible:
            text = (await btn.inner_text()).strip()
            print(f"  edit btn: '{text}'")
            await btn.click()
            await asyncio.sleep(5)
            break

    print(f"\nURL: {page.url}")
    
    # Now check imgs on the project page
    print("\n=== IMG ON PROJECT PAGE ===")
    imgs = await page.query_selector_all('img')
    for i, img in enumerate(imgs):
        visible = await img.is_visible()
        if not visible:
            continue
        alt = await img.get_attribute('alt') or ''
        src = (await img.get_attribute('src') or '')[:120]
        bbox = await img.bounding_box()
        bstr = f"w={bbox['width']:.0f} h={bbox['height']:.0f} x={bbox['x']:.0f} y={bbox['y']:.0f}" if bbox else "no-bbox"
        print(f"  img[{i}] alt='{alt}' {bstr}")
        print(f"    src='{src}'")

    # Also check for any button/div with image content
    print("\n=== BUTTON CARDS WITH IMAGES ===")
    cards = await page.query_selector_all('button:has(img)')
    for i, card in enumerate(cards):
        visible = await card.is_visible()
        if not visible:
            continue
        text = (await card.inner_text()).strip().replace('\n', ' | ')[:80]
        bbox = await card.bounding_box()
        bstr = f"w={bbox['width']:.0f} h={bbox['height']:.0f}" if bbox else ""
        print(f"  card[{i}] text='{text}' {bstr}")

    await asyncio.sleep(5)
    await browser.close()
    await pw.stop()

asyncio.run(main())
