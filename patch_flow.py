import os
p = r'd:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\services\flow_client.py'
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# Fix settings click
c = c.replace(
    'if await o.is_visible():\n                                text = (await o.inner_text()).strip()',
    'if await o.is_visible():\n                                is_settings = await o.evaluate(\'(el, btn) => el === btn\', settings_btn)\n                                if is_settings: continue\n                                text = (await o.inner_text()).strip()'
)

# Remove early failure check
c = c.replace(
    'if err_panel and await err_panel.is_visible():\n                    log.warning("UI Auto: Detected partial failure (\'Không thành công\').")\n                    partial_fail = True',
    '# if err_panel and await err_panel.is_visible():\n                #     log.warning("UI Auto: Detected partial failure (\'Không thành công\').")\n                #     partial_fail = True'
)

with open(p, 'w', encoding='utf-8') as f:
    f.write(c)
print('Patched logic')
