import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_settings = content.find('            log.info("UI Auto: Configuring settings for Video...")')
end_image_upload = content.find('            log.info("UI Auto: Entering prompt and clicking Generate...")')

if start_settings == -1 or end_image_upload == -1:
    print("Could not find sections to replace.")
    exit(1)

new_code = """            log.info("UI Auto: Configuring settings for Video...")
            settings_btn = None
            buttons = await self._page.query_selector_all('button, [role="button"]')
            
            # Find the pill button containing current settings
            for b in buttons:
                if await b.is_visible():
                    txt = await b.inner_text()
                    if txt and ('Video' in txt or 'Hình ảnh' in txt or 'Image' in txt):
                        # The pill button usually has these keywords
                        settings_btn = b
                        break
            
            if settings_btn:
                await settings_btn.click()
                await asyncio.sleep(1)
                
                # Switch to Video tab
                video_tab = await self._page.query_selector('button:has-text("Video")')
                if video_tab and await video_tab.is_visible():
                    await video_tab.click()
                    await asyncio.sleep(1)
                    
                async def click_segment_button(target_texts):
                    # Finds a button (not dropdown option) containing the text
                    btns = await self._page.query_selector_all('button, div[role="button"]')
                    for btn in btns:
                        if await btn.is_visible():
                            text = await btn.inner_text()
                            if text:
                                for target in target_texts:
                                    if target.lower() == text.strip().lower() or target.lower() in text.lower():
                                        await btn.click()
                                        return True
                    log.warning(f"UI Auto: Could not find segment button for {target_texts}")
                    return False

                async def click_dropdown_option(target_texts):
                    items = await self._page.query_selector_all('md-select-option, [role="option"]')
                    for item in items:
                        if await item.is_visible():
                            text = await item.inner_text()
                            if text:
                                for target in target_texts:
                                    if target.lower() == text.strip().lower() or target.lower() in text.lower():
                                        await item.click()
                                        return True
                    log.warning(f"UI Auto: Could not find dropdown option for {target_texts}")
                    return False

                # 1. Ratio (Segment buttons)
                if "16:9" in aspect_ratio:
                    ratio_options = ["16:9"]
                elif "9:16" in aspect_ratio:
                    ratio_options = ["9:16"]
                elif "4:3" in aspect_ratio:
                    ratio_options = ["4:3"]
                elif "3:4" in aspect_ratio:
                    ratio_options = ["3:4"]
                else:
                    ratio_options = ["1:1"]
                await click_segment_button(ratio_options)
                await asyncio.sleep(0.5)

                # 2. Count (Segment buttons)
                if str(count) == "1":
                    count_options = ["1x", "x1"]
                else:
                    count_options = [f"x{count}", f"{count}x"]
                await click_segment_button(count_options)
                await asyncio.sleep(0.5)

                # 3. Model (Dropdown)
                dropdowns = await self._page.query_selector_all('md-outlined-select, [role="combobox"]')
                for dd in dropdowns:
                    if await dd.is_visible():
                        await dd.click()
                        await asyncio.sleep(1)
                        model_options = [model, model.replace("-", " "), model.replace("_", " ")]
                        clicked = await click_dropdown_option(model_options)
                        await asyncio.sleep(0.5)
                        if clicked:
                            break
                
                # 4. Duration (Segment buttons)
                dur_options = [f"{duration}s", f"{duration} giây", str(duration)]
                await click_segment_button(dur_options)
                await asyncio.sleep(0.5)

                # Close settings popup by clicking the main canvas or pressing Escape
                await self._page.keyboard.press("Escape")
                await asyncio.sleep(0.5)

            if image_paths and len(image_paths) > 0:
                log.info(f"UI Auto: Uploading reference image {image_paths[0]}...")
                try:
                    # Best method: use hidden file input directly
                    file_inputs = await self._page.query_selector_all('input[type="file"]')
                    if file_inputs:
                        await file_inputs[0].set_files(image_paths[0])
                        log.info("UI Auto: Uploaded image via hidden input.")
                        await asyncio.sleep(3.0)
                    else:
                        log.warning("UI Auto: No input[type='file'] found, trying UI click...")
                        # Fallback: Click the attachment button (usually a paperclip or image icon)
                        file_chooser_promise = self._page.expect_file_chooser(timeout=10000)
                        upload_btn = None
                        buttons = await self._page.query_selector_all('button, [role="button"]')
                        for b in buttons:
                            if await b.is_visible():
                                try:
                                    icon = await b.query_selector('md-icon')
                                    if icon:
                                        txt = await icon.inner_text()
                                        if txt and ('add_photo_alternate' in txt or 'image' in txt or 'attach_file' in txt):
                                            upload_btn = b
                                            break
                                except Exception:
                                    continue
                        if upload_btn:
                            await upload_btn.click()
                            file_chooser = await file_chooser_promise
                            await file_chooser.set_files(image_paths[0])
                            await asyncio.sleep(3.0)
                except Exception as e:
                    log.warning(f"UI Auto: Image upload failed: {e}")
            
"""

content = content[:start_settings] + new_code + content[end_image_upload:]

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Injected fixes successfully!")
