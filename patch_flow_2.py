import os
p = r'd:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\services\flow_client.py'
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# Fix settings click by replacing query_selector_all and adding length check
old_query = "opts = await self._page.query_selector_all('button, [role=\"button\"], [role=\"menuitem\"], [role=\"option\"], [role=\"tab\"], [role=\"radio\"]')"
new_query = "opts = await self._page.query_selector_all('mat-option, md-option, [role=\"menuitem\"], [role=\"option\"], [role=\"radio\"], button, [role=\"button\"]')"
c = c.replace(old_query, new_query)

old_check = "if is_settings: continue\n                                text = (await o.inner_text()).strip()"
new_check = "if is_settings: continue\n                                text = (await o.inner_text()).strip()\n                                if len(text) > 22 or '\\n' in text: continue  # Exclude the settings pill itself which has combined text"
c = c.replace(old_check, new_check)

with open(p, 'w', encoding='utf-8') as f:
    f.write(c)
print('Patched logic again')
