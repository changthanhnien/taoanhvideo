import re

with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '                    else:\n                        err = blob_info.get("error") if blob_info else "Unknown"'
start_idx = content.find(start_marker)

end_marker = '                    if not downloaded:\n                        # Absolute final fallback: just return the URL and let the frontend try its luck'
end_idx = content.find(end_marker, start_idx)

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + content[end_idx:]
    with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Fixed!")
else:
    print(f"Failed to find markers: start={start_idx}, end={end_idx}")
