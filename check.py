import re
with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

for i, m in enumerate(re.finditer(r"'''", content)):
    line_num = content.count('\n', 0, m.start()) + 1
    print(f"Match {i+1}: Line {line_num}")
