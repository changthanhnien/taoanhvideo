with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_get_download = """
    async def get_download_url(self, media_id):
        \"\"\"Get video download URL via labs.google redirect endpoint.\"\"\"
        redirect_url = f"https://labs.google/fx/api/trpc/media.getMediaUrlRedirect?name={media_id}"
"""

new_get_download = """
    async def get_download_url(self, media_id):
        \"\"\"Get video download URL via labs.google redirect endpoint.\"\"\"
        if "getMediaUrlRedirect" in media_id:
            redirect_url = media_id if media_id.startswith("http") else f"https://labs.google{media_id}"
        else:
            redirect_url = f"https://labs.google/fx/api/trpc/media.getMediaUrlRedirect?name={media_id}"
"""

if old_get_download.strip() in content:
    content = content.replace(old_get_download.strip(), new_get_download.strip())
else:
    print("WARNING: Could not find old_get_download to replace!")

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated get_download_url logic successfully!")
