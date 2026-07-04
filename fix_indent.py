import re

with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(len(lines)):
    if 'if blob_info and blob_info.get("data"):' in lines[i]:
        # found it, lines[i] is at index 996 roughly
        start_idx = i
        break

end_idx = -1
for i in range(start_idx, len(lines)):
    if 'if len(media_list) >= count:' in lines[i]:
        end_idx = i
        break

print(f"Fixing from {start_idx} to {end_idx}")

for i in range(start_idx, end_idx):
    # Add 4 spaces
    lines[i] = "    " + lines[i]

with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
