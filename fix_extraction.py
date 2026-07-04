with open('workers/task_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_result_extraction = """
                    if result:
                        if isinstance(result, list):
                            for r in result:
                                result_urls.append(r.get("mediaId") or r.get("name"))
                        else:
                            for i in range(count):
                                result_urls.append(result.get("name") or result.get("mediaId"))
"""

new_result_extraction = """
                    if result:
                        if isinstance(result, list):
                            for r in result:
                                result_urls.append(r.get("mediaId") or r.get("name"))
                        else:
                            # result might be {"status": "COMPLETED", "result": {"media": [...]}}
                            media_arr = result.get("result", {}).get("media", [])
                            for m in media_arr:
                                img = m.get("image", {}).get("generatedImage", {})
                                url = img.get("url")
                                if url:
                                    result_urls.append(url)
                            
                            # Fallback if result_urls is still empty
                            if not result_urls:
                                for i in range(count):
                                    result_urls.append(result.get("name") or result.get("mediaId"))
"""

if old_result_extraction.strip() in content:
    content = content.replace(old_result_extraction.strip(), new_result_extraction.strip())
else:
    print("WARNING: Could not find old_result_extraction to replace!")

with open('workers/task_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated task manager extraction logic successfully!")
