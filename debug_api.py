import asyncio
import sys
import os
import shutil
import tempfile
import json
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    profile_dir = "D:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/.vidgen/browser_profiles"
    temp_dir = tempfile.mkdtemp(prefix="nav_debug_")
    
    # Copy only Cookies to bypass lock
    print("Copying profile...")
    try:
        os.makedirs(os.path.join(temp_dir, "Default", "Network"), exist_ok=True)
        shutil.copy2(os.path.join(profile_dir, "Local State"), os.path.join(temp_dir, "Local State"))
        shutil.copy2(os.path.join(profile_dir, "Default", "Network", "Cookies"), os.path.join(temp_dir, "Default", "Network", "Cookies"))
    except Exception as e:
        print(f"Copy error: {e}")
        
    print("Launching playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(temp_dir, headless=True)
        page = await browser.new_page()
        
        print("Getting session...")
        await page.goto("https://labs.google/fx/api/auth/session", wait_until="domcontentloaded")
        try:
            session = json.loads(await page.inner_text("body"))
            token = session.get("accessToken")
        except:
            print("Failed to get session")
            token = None
            
        if token:
            print("Getting user state...")
            res1 = await page.evaluate(f'''async () => {{
                try {{
                    const r = await fetch("https://aisandbox-pa.googleapis.com/v1/whisk:getUserState", {{
                        method: "GET",
                        headers: {{"Authorization": "Bearer {token}"}}
                    }});
                    return await r.json();
                }} catch(e) {{ return {{error: e.message}}; }}
            }}''')
            with open("debug_userstate.json", "w", encoding="utf-8") as f:
                json.dump(res1, f, indent=2)
                
            print("Getting user (tRPC)...")
            res2 = await page.evaluate(f'''async () => {{
                try {{
                    const r = await fetch("https://labs.google/fx/api/trpc/videoFx.getUser?input=%7B%7D", {{
                        method: "GET",
                        headers: {{"Authorization": "Bearer {token}"}}
                    }});
                    return await r.json();
                }} catch(e) {{ return {{error: e.message}}; }}
            }}''')
            with open("debug_getuser.json", "w", encoding="utf-8") as f:
                json.dump(res2, f, indent=2)
                
            print("Getting videoModelConfig...")
            res3 = await page.evaluate(f'''async () => {{
                try {{
                    const r = await fetch("https://labs.google/fx/api/trpc/videoFx.getVideoModelConfig?input=%7B%7D", {{
                        method: "GET",
                        headers: {{"Authorization": "Bearer {token}"}}
                    }});
                    return await r.json();
                }} catch(e) {{ return {{error: e.message}}; }}
            }}''')
            with open("debug_videomodelconfig.json", "w", encoding="utf-8") as f:
                json.dump(res3, f, indent=2)
                
        await browser.close()
    
    # Cleanup
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except: pass
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
