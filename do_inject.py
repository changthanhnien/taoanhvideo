import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

with open('video_whisk_code.py', 'r', encoding='utf-8') as f:
    video_whisk = f.read()

# Insert before generate_video
if '_generate_video_whisk' not in content:
    content = content.replace("    async def generate_video(", video_whisk + "\n\n    async def generate_video(")

# Replace generate_video signature and body
old_gen_video = re.search(r'    async def generate_video\(self, .*?return self\._extract_generation_id\(result, 0\) or result', content, re.DOTALL)
if old_gen_video:
    new_gen_video = """    async def generate_video(self, prompt, image_paths=None, model="veo-3.1-fast", aspect_ratio="16:9", duration=8, quality="720p", seed=None, project_name="", count=1, callback=None):
        return await self._generate_video_whisk(prompt, image_paths, model, aspect_ratio, duration, project_name, count, callback)"""
    content = content.replace(old_gen_video.group(0), new_gen_video)

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Injected successfully!")
