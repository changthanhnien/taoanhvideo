with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read().splitlines()

# Find the start and end of the broken block
start_idx = -1
end_idx = -1

for i, line in enumerate(content):
    if '# Switch to Video tab' in line:
        start_idx = i
        break

for i in range(start_idx, len(content)):
    if 'log.info("UI Auto: Clicking Generate button next to Settings Pill...")' in content[i] or 'existing = await self._page.query_selector_all(' in content[i]:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    new_block = [
        '            # Switch to Video tab (in the Settings Panel)',
        '            video_tabs = await self._page.query_selector_all(\'[role="tab"]:has-text("Video"), button:text-is("Video"), md-primary-tab:has-text("Video"), div[role="tab"]:has-text("Video")\')',
        '            for tab in video_tabs:',
        '                if await tab.is_visible():',
        '                    await tab.click()',
        '                    await asyncio.sleep(1)',
        '                    break',
        '',
        '            async def click_segment_button(target_texts):',
        '                for target in target_texts:',
        '                    try:',
        '                        locs = await self._page.get_by_text(target, exact=True).all()',
        '                        for loc in locs:',
        '                            try:',
        '                                await loc.click(force=True, timeout=1000)',
        '                                await asyncio.sleep(0.5)',
        '                                return True',
        '                            except Exception:',
        '                                continue',
        '                    except Exception:',
        '                        pass',
        '                    try:',
        '                        locs = await self._page.get_by_text(target).all()',
        '                        for loc in locs:',
        '                            try:',
        '                                await loc.click(force=True, timeout=1000)',
        '                                await asyncio.sleep(0.5)',
        '                                return True',
        '                            except Exception:',
        '                                continue',
        '                    except Exception:',
        '                        pass',
        '                btns = await self._page.query_selector_all(\'button, div[role="button"], [role="radio"], label, .segment\')',
        '                for btn in btns:',
        '                    try:',
        '                        text = await btn.inner_text() if await btn.is_visible() else ""',
        '                        aria = await btn.get_attribute("aria-label") or ""',
        '                        title = await btn.get_attribute("title") or ""',
        '                        combined = f"{text} {aria} {title}".lower()',
        '                        if combined.strip():',
        '                            for target in target_texts:',
        '                                if target.lower() in combined:',
        '                                    try:',
        '                                        await btn.click(force=True, timeout=1000)',
        '                                        await asyncio.sleep(0.5)',
        '                                        return True',
        '                                    except Exception:',
        '                                        pass',
        '                    except Exception:',
        '                        pass',
        '                log.warning(f"UI Auto: Could not find segment button for {target_texts}")',
        '                return False',
        '',
        '            async def click_dropdown_option(target_texts):',
        '                for target in target_texts:',
        '                    try:',
        '                        locators = await self._page.get_by_text(target).all()',
        '                        for loc in locators:',
        '                            if await loc.is_visible():',
        '                                await loc.click()',
        '                                return True',
        '                    except Exception:',
        '                        pass',
        '                items = await self._page.query_selector_all(\'md-select-option, [role="option"], li\')',
        '                for item in items:',
        '                    if await item.is_visible():',
        '                        try:',
        '                            text = await item.inner_text()',
        '                            if text:',
        '                                for target in target_texts:',
        '                                    if target.lower() == text.strip().lower() or target.lower() in text.lower():',
        '                                        await item.click()',
        '                                        return True',
        '                        except Exception:',
        '                            pass',
        '                log.warning(f"UI Auto: Could not find dropdown option for {target_texts}")',
        '                return False',
        '',
        '            # 1. Ratio (Segment buttons)',
        '            if "16:9" in aspect_ratio:',
        '                ratio_options = ["16:9", "Ngang", "Landscape", "16 by 9", "16 x 9"]',
        '            elif "9:16" in aspect_ratio:',
        '                ratio_options = ["9:16", "Dọc", "Portrait", "9 by 16", "9 x 9"]',
        '            elif "4:3" in aspect_ratio:',
        '                ratio_options = ["4:3"]',
        '            elif "3:4" in aspect_ratio:',
        '                ratio_options = ["3:4"]',
        '            else:',
        '                ratio_options = ["1:1", "Vuông", "Square"]',
        '            await click_segment_button(ratio_options)',
        '            await asyncio.sleep(0.5)',
        '',
        '            # 2. Count (Segment buttons)',
        '            if str(count) == "1":',
        '                count_options = ["1x", "x1", "1"]',
        '            else:',
        '                count_options = [f"x{count}", f"{count}x", str(count)]',
        '            await click_segment_button(count_options)',
        '            await asyncio.sleep(0.5)',
        '',
        '            # 3. Model (Dropdown)',
        '            if model:',
        '                log.info(f"UI Auto: Selecting model {model}...")',
        '                dropdowns = await self._page.query_selector_all(\'md-outlined-select, [role="combobox"]\')',
        '                for dd in dropdowns:',
        '                    if await dd.is_visible():',
        '                        await dd.click()',
        '                        await asyncio.sleep(1)',
        '                        model_options = [model, model.replace("-", " "), model.replace("_", " ")]',
        '                        clicked = await click_dropdown_option(model_options)',
        '                        await asyncio.sleep(0.5)',
        '                        if clicked:',
        '                            break',
        '',
        '            # 4. Duration (Segment buttons)',
        '            dur_options = [f"{duration}s", f"{duration} giây", str(duration)]',
        '            await click_segment_button(dur_options)',
        '            await asyncio.sleep(0.5)',
        '',
        '            # Close settings popup by clicking the main canvas or pressing Escape',
        '            await self._page.keyboard.press("Escape")',
        '            await asyncio.sleep(0.5)',
        '            log.info("UI Auto: Clicking Generate button next to Settings Pill...")',
    ]
    
    # We might have an 'existing =' line at end_idx, so don't replace it if it's there
    if 'existing = ' in content[end_idx]:
        new_content = content[:start_idx] + new_block + content[end_idx:]
    else:
        new_content = content[:start_idx] + new_block + content[end_idx+1:]
        
    with open('services/flow_client.py', 'w', encoding='utf-8') as f:
        f.write('\\n'.join(new_content) + '\\n')
    print("Repaired services/flow_client.py successfully!")
else:
    print(f"Failed to find block! start_idx={start_idx}, end_idx={end_idx}")
