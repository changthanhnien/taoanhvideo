import re

with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '            log.info("UI Auto: Configuring settings for Video...")'
start_idx = content.find(start_marker)

end_marker = '            # Close settings popup by safely clicking the main canvas background'
end_idx = content.find(end_marker, start_idx)

if start_idx != -1 and end_idx != -1:
    new_block = '''            log.info("UI Auto: Configuring settings for Video...")
            
            # --- 1. OPEN SETTINGS POPUP ---
            popup_opened = await self._page.evaluate(\'''() => {
                // Check if already open
                const popups = Array.from(document.querySelectorAll('md-menu[open], [role="menu"], [role="dialog"], .cdk-overlay-pane'));
                for (const p of popups) {
                    const t = (p.innerText || p.textContent || "").toLowerCase();
                    if (t.includes("aspect ratio") || t.includes("mode") || t.includes("tỷ lệ") || t.includes("16:9") || t.includes("video")) {
                        return true; // Already open
                    }
                }
                
                // Find prompt textarea
                const ta = document.querySelector('textarea[aria-label*="create"], textarea[placeholder*="create"], textarea');
                if (!ta) return false;
                
                // Find container
                const container = ta.closest('div.input-container, div[class*="chat"], div[class*="prompt"]') || ta.parentElement.parentElement;
                if (!container) return false;
                
                // Find the pill button
                const btns = Array.from(container.querySelectorAll('button, [role="button"]'));
                const pill = btns.find(b => {
                    const text = (b.innerText || b.textContent || "").toLowerCase();
                    return text.includes("veo") || text.includes("imagen") || text.includes("nano") || text.includes("video") || text.includes("image") || text.includes("16:9") || text.includes("1x");
                });
                
                if (pill) {
                    pill.click();
                    return true;
                }
                
                // Fallback: slider icon
                const sliderBtn = btns.find(b => b.innerHTML.includes('M3 17v2h6') || b.innerHTML.includes('M3,17'));
                if (sliderBtn) {
                    sliderBtn.click();
                    return true;
                }
                return false;
            }\''')
            
            log.info(f"UI Auto: Popup open triggered: {popup_opened}")
            import asyncio
            await asyncio.sleep(1.5) # Wait for animation
            
            # --- 2. CONFIGURE SETTINGS INSIDE POPUP ---
            # Aspect Ratio mapping
            ratio_kws = ["16:9"]
            if "9:16" in aspect_ratio: ratio_kws = ["9:16", "dọc", "vertical"]
            elif "1:1" in aspect_ratio: ratio_kws = ["1:1", "vuông", "square"]
            elif "4:3" in aspect_ratio: ratio_kws = ["4:3"]
            elif "3:4" in aspect_ratio: ratio_kws = ["3:4"]
            
            # Duration mapping
            dur_kws = ["8s", "8 giây", "8 seconds"] if "8" in str(duration) else ["4s", "4 giây", "4 seconds"]
            
            # Count mapping
            count_kw = f"x{count}" if int(count) > 1 else "1x"
            if count_kw == "x1": count_kw = "1x"
            
            logs = await self._page.evaluate(f\'''([ratioKws, durKws, countKw]) => {{
                let out = [];
                const popups = Array.from(document.querySelectorAll('md-menu[open], [role="menu"], [role="dialog"], .cdk-overlay-pane'));
                let popup = popups.find(p => {{
                    const t = (p.innerText || p.textContent || "").toLowerCase();
                    return t.includes("aspect ratio") || t.includes("mode") || t.includes("tỷ lệ") || t.includes("16:9") || t.includes("nano") || t.includes("veo") || t.includes("video");
                }});
                
                if (!popup) {{
                    out.push("Popup not found!");
                    return out;
                }}
                
                // Expand the search to anything clickable
                const btns = Array.from(popup.querySelectorAll('button, [role="button"], [role="radio"], [role="tab"], md-filter-chip, md-chip, .segment-button, md-outlined-segment, md-segment, label'));
                
                const clickBtn = (keywords) => {{
                    for (const b of btns) {{
                        let text = (b.innerText || b.textContent || b.getAttribute('aria-label') || b.getAttribute('value') || "").toLowerCase();
                        if (b.shadowRoot) {{
                            text += " " + (b.shadowRoot.innerText || b.shadowRoot.textContent || "").toLowerCase();
                        }}
                        
                        if (keywords.some(kw => text.includes(kw.toLowerCase()))) {{
                            b.click();
                            out.push("Clicked: " + keywords[0]);
                            return true;
                        }}
                    }}
                    out.push("Not found: " + keywords[0]);
                    return false;
                }};
                
                // 1. Click Video Mode
                clickBtn(["video", "veo", "ảnh -> video", "nh -> video"]);
                
                // 2. Click Aspect Ratio
                clickBtn(ratioKws);
                
                // 3. Click Duration
                clickBtn(durKws);
                
                // 4. Click Count
                clickBtn([countKw, "x"+countKw]);
                
                return out;
            }}\''', [ratio_kws, dur_kws, count_kw])
            
            log.info(f"UI Auto: Configuration result: {logs}")
            await asyncio.sleep(0.5)

'''

    new_content = content[:start_idx] + new_block + content[end_idx:]
    with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Fixed!")
else:
    print(f"Failed to find markers: start={start_idx}, end={end_idx}")
