"""Inspect Flow project page to find prompt input and generate button."""

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


async def inspect_flow():
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
            headless=False,
            executable_path=chrome_exe,
            args=["--window-size=1280,900"],
        )
        page = await browser.new_page()

        # Step 1: Go to Flow homepage
        p("=== Step 1: Navigate to Flow ===")
        await page.goto("https://labs.google/fx/vi/tools/flow", wait_until="networkidle")
        await asyncio.sleep(5)
        p(f"URL: {page.url}")

        # Step 2: Click "Dự án mới" button  
        p("\n=== Step 2: Click 'Dự án mới' ===")
        # The button has text content containing "Dự án mới"
        new_btn = await page.query_selector('button:has-text("Dự án mới")')
        if not new_btn:
            # fallback: look for button with "add_2" icon text
            new_btn = await page.query_selector('button:has-text("add_2")')
        if new_btn:
            p("  Found 'Dự án mới' button, clicking...")
            await new_btn.click()
            # Wait for navigation to project page
            await page.wait_for_url("**/flow/project/**", timeout=15000)
            await asyncio.sleep(5)
            p(f"  Navigated to: {page.url}")
        else:
            p("  ERROR: Could not find 'Dự án mới' button!")
            return

        # Step 3: Find prompt input
        p("\n=== Step 3: Find prompt input ===")
        # Try multiple selectors
        input_selectors = [
            'textarea',
            'div[role="textbox"]',
            'div[contenteditable="true"]',
            'input[type="text"]',
            '[data-placeholder]',
        ]
        target_input = None
        for sel in input_selectors:
            els = await page.query_selector_all(sel)
            for el in els:
                visible = await el.is_visible()
                if visible:
                    tag = await el.evaluate("el => el.tagName")
                    bbox = await el.bounding_box()
                    ph = await el.get_attribute("placeholder") or ""
                    aria = await el.get_attribute("aria-label") or ""
                    role = await el.get_attribute("role") or ""
                    p(f"  FOUND: sel='{sel}' tag={tag} placeholder='{ph}' aria='{aria}' role='{role}' box={bbox}")
                    if not target_input:
                        target_input = el

        if target_input:
            p("  -> Typing prompt...")
            await target_input.click()
            await asyncio.sleep(0.5)
            await page.keyboard.type("A red apple on a white background", delay=30)
            await asyncio.sleep(2)
            p("  Prompt typed successfully")
        else:
            p("  ERROR: No prompt input found!")
            # Let's dump the full page HTML to look at structure
            html = await page.content()
            p(f"  Page HTML length: {len(html)}")
            # Look for any input-like elements
            all_inputs = await page.query_selector_all('input, textarea, [contenteditable]')
            for inp in all_inputs:
                tag = await inp.evaluate("el => el.tagName")
                visible = await inp.is_visible()
                inp_type = await inp.get_attribute("type") or ""
                p(f"    input: tag={tag} type={inp_type} visible={visible}")

        # Step 4: Find and identify the generate/submit button
        p("\n=== Step 4: Find generate/submit button ===")
        buttons = await page.query_selector_all("button")
        bottom_buttons = []
        for i, btn in enumerate(buttons):
            visible = await btn.is_visible()
            if not visible:
                continue
            try:
                text = (await btn.inner_text()).strip().replace('\n', ' | ')[:80]
                aria = await btn.get_attribute("aria-label") or ""
                data_testid = await btn.get_attribute("data-testid") or ""
                has_svg = await btn.evaluate("el => el.querySelector('svg') !== null")
                enabled = await btn.is_enabled()
                bbox = await btn.bounding_box()
                if not bbox:
                    continue
                bbox_str = f"x={bbox['x']:.0f} y={bbox['y']:.0f} w={bbox['width']:.0f} h={bbox['height']:.0f}"
                # Get first 300 chars of outerHTML
                outer = await btn.evaluate("el => el.outerHTML.substring(0, 400)")
                p(f"  btn[{i}] text='{text}' aria='{aria}' testid='{data_testid}' svg={has_svg} enabled={enabled} {bbox_str}")
                p(f"    HTML: {outer[:250]}")
                
                # Track buttons in bottom half
                if bbox['y'] > 400:
                    bottom_buttons.append((i, btn, text, aria, bbox))
            except Exception as e:
                pass

        p(f"\n  Bottom buttons count: {len(bottom_buttons)}")
        for i, btn, text, aria, bbox in bottom_buttons:
            p(f"    btn[{i}] text='{text}' aria='{aria}' y={bbox['y']:.0f}")

        # Step 5: Also look for the submit button near the prompt area
        p("\n=== Step 5: Look for submit near prompt ===")
        # The generate button from the screenshot is a circular button with arrow icon
        # Try to find it by looking at button shape (circular = width ~= height, small)
        for i, btn, text, aria, bbox in bottom_buttons:
            w, h = bbox['width'], bbox['height']
            if abs(w - h) < 10 and w < 80:  # Circular-ish button
                p(f"  CIRCULAR btn[{i}] text='{text}' aria='{aria}' w={w:.0f} h={h:.0f}")
                outer = await btn.evaluate("el => el.outerHTML.substring(0, 500)")
                p(f"    FULL HTML: {outer}")

        await asyncio.sleep(15)
        p("\n=== DONE ===")

    finally:
        if "browser" in locals():
            await browser.close()
        await pw.stop()


if __name__ == "__main__":
    asyncio.run(inspect_flow())
