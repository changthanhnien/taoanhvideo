import json
import re

with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/flow.html', 'r', encoding='utf-8') as f:
    content = f.read()

m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', content, re.DOTALL)
if m:
    data = json.loads(m.group(1))
    with open('next_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print('Saved to next_data.json')
else:
    print('__NEXT_DATA__ not found')
