import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# I will find the settings section I just injected
start_settings = content.find('                # 1. Ratio (Segment buttons)')
end_settings = content.find('                # 4. Duration (Segment buttons)')

if start_settings == -1 or end_settings == -1:
    print("Could not find settings section to fix")
    exit(1)

fixed_options_code = """                # 1. Ratio (Segment buttons)
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
                    count_options = ["1x"]
                else:
                    count_options = [f"x{count}"]
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
                
"""

content = content[:start_settings] + fixed_options_code + content[end_settings:]

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Injected fixed options successfully!")
