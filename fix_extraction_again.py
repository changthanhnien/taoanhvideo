with open('workers/task_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_extraction = """
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

new_extraction = """
                        else:
                            # result is usually {"media": [...]}
                            media_arr = result.get("media", [])
                            if not media_arr and "result" in result:
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

if old_extraction.strip() in content:
    content = content.replace(old_extraction.strip(), new_extraction.strip())
else:
    print("WARNING: Could not find old_extraction to replace!")

# Also fix the NoneType error in get_download_url just in case
with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    flow_content = f.read()

old_get_download = """
    async def get_download_url(self, media_id):
        \"\"\"Get video download URL via labs.google redirect endpoint.\"\"\"
        if "getMediaUrlRedirect" in media_id:
"""

new_get_download = """
    async def get_download_url(self, media_id):
        \"\"\"Get video download URL via labs.google redirect endpoint.\"\"\"
        if not media_id: return None
        if "getMediaUrlRedirect" in media_id:
"""

if old_get_download.strip() in flow_content:
    flow_content = flow_content.replace(old_get_download.strip(), new_get_download.strip())
    with open('services/flow_client.py', 'w', encoding='utf-8') as f:
        f.write(flow_content)

with open('workers/task_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated extraction logic to handle {'media': [...]} correctly!")
