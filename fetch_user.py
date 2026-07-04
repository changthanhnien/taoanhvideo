import asyncio
from playwright.async_api import async_playwright
import json
import tempfile
import shutil
from pathlib import Path
from models.database import Database

async def fetch_user():
    db = Database()
    accounts = db.get_accounts()
    if not accounts: return
    cookie_path = accounts[0].cookie_path
    
    temp_dir = tempfile.mkdtemp(prefix="navtools_test_")
    src_dir = Path(cookie_path)
    for f in ["Cookies", "Cookies-journal", "Local State"]:
        src = src_dir / f if f != "Local State" else src_dir.parent / f
        if src.exists():
            shutil.copy2(str(src), str(Path(temp_dir) / f))
            
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(temp_dir, headless=True)
        page = await browser.new_page()
        
        await page.goto("https://labs.google/fx/api/auth/session")
        session = json.loads(await page.inner_text("body"))
        
        with open("raw_session.json", "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2)
            
        await browser.close()

asyncio.run(fetch_user())
