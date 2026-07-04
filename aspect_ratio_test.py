import asyncio
import os
import sys
import json
import logging
from playwright.async_api import async_playwright

sys.path.insert(0, r"d:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted")
from services.flow_client import FlowClient
logging.basicConfig(level=logging.INFO)

async def test_ratio(ratio, user_data_dir):
    async with async_playwright() as p:
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        page = browser_context.pages[0] if browser_context.pages else await browser_context.new_page()
        client = FlowClient(page)
        
        actual_ratio_sent = None
        
        # Intercept network requests to capture the generation payload
        async def handle_request(request):
            nonlocal actual_ratio_sent
            if request.method == "POST" and "generate" in request.url:
                try:
                    post_data = request.post_data
                    if post_data:
                        if "aspectRatio" in post_data or "ASPECT_RATIO" in post_data or ratio in post_data or "9:16" in post_data or "16:9" in post_data:
                            print(f"[NETWORK] Intercepted generate request! Payload: {post_data[:200]}...")
                            if "16:9" in post_data or "16x9" in post_data or "ASPECT_RATIO_16_9" in post_data:
                                actual_ratio_sent = "16:9"
                            elif "9:16" in post_data or "9x16" in post_data or "ASPECT_RATIO_9_16" in post_data:
                                actual_ratio_sent = "9:16"
                            elif "1:1" in post_data or "1x1" in post_data or "ASPECT_RATIO_1_1" in post_data:
                                actual_ratio_sent = "1:1"
                except:
                    pass
        
        page.on("request", handle_request)
        
        print(f"--- TESTING RATIO {ratio} ---")
        try:
            # Generate video (this will trigger the whisking)
            async def abort_after_click():
                while actual_ratio_sent is None:
                    await asyncio.sleep(0.5)
                print(f"Captured network ratio: {actual_ratio_sent}. Aborting generation!")
                raise Exception("Generation triggered successfully. Aborting to save time.")
                
            task1 = asyncio.create_task(client.generate_video(f"Test aspect ratio {ratio}", aspect_ratio=ratio))
            task2 = asyncio.create_task(abort_after_click())
            
            done, pending = await asyncio.wait([task1, task2], return_when=asyncio.FIRST_EXCEPTION)
            for task in pending:
                task.cancel()
            
            for task in done:
                e = task.exception()
                if e and "Aborting to save time" not in str(e):
                    print(f"Task exception: {e}")
                
        except Exception as e:
            if "Aborting to save time" not in str(e):
                print(f"Error during generation: {e}")
                
        # Close the browser manually since we intercepted
        await browser_context.close()
        return actual_ratio_sent

async def main():
    user_data_dir = r"d:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\chrome_profile"
    results = []
    
    for ratio in ["16:9", "9:16", "1:1"]:
        actual = await test_ratio(ratio, user_data_dir)
        print(f"Requested: {ratio}, Actual: {actual}")
        results.append({
            "Requested Ratio": ratio,
            "Actual Ratio": actual or "UNKNOWN (maybe 9:16 default?)",
            "PASS/FAIL": "PASS" if actual == ratio else "FAIL"
        })
        await asyncio.sleep(2) # cooldown
        
    with open("aspect_ratio_test.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print(json.dumps(results, indent=4))

if __name__ == "__main__":
    asyncio.run(main())
