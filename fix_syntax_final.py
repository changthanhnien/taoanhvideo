import re

with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# I want to delete the chunk from `                    else:\n                        err = blob_info.get("error")`
# down to the end of the `if clicked:` block.
# Let's find the start marker:
start_marker = '                    else:\n                        err = blob_info.get("error") if blob_info else "Unknown"'
start_idx = content.find(start_marker)

# Let's find the end marker:
end_marker = '                        if not downloaded:\n                            log.warning(f"UI Auto: Error searching for or waiting for download buttons: {e}")'
end_idx = content.find(end_marker, start_idx)

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + content[end_idx:]
    with open('d:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/services/flow_client.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Fixed!")
else:
    print(f"Failed to find markers: start={start_idx}, end={end_idx}")
