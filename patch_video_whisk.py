import re

with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find('    async def _generate_image_whisk(')
end_idx = content.find('    async def generate_image(')

if start_idx == -1 or end_idx == -1:
    print("Could not find start or end index.")
    exit(1)

image_whisk_code = content[start_idx:end_idx]

# Replace signature
video_whisk_code = image_whisk_code.replace(
    '_generate_image_whisk(self, prompt, image_paths=None, model="Nano Banana 2", aspect_ratio="1:1", project_name="", count=1, callback=None):',
    '_generate_video_whisk(self, prompt, image_paths=None, model="Veo 3.1 - Fast", aspect_ratio="16:9", duration=8, project_name="", count=1, callback=None):'
)

video_whisk_code = video_whisk_code.replace("result_imgs = await self._page.query_selector_all('img')",
"result_imgs = await self._page.query_selector_all('video')")

video_whisk_code = video_whisk_code.replace("existing = await self._page.query_selector_all('img')",
"existing = await self._page.query_selector_all('video')")

video_whisk_code = video_whisk_code.replace("UI Auto: Found {len(result_media_ids)} new results",
"UI Auto: Found {len(result_media_ids)} new video results")

duration_code = """                log.info(f"UI Auto: Setting Duration to {duration}s...")
                await click_option([f"{duration}s", f"{duration} giây", f"{duration} second", str(duration)])
                
                log.info(f"UI Auto: Setting Count to {count}x...")"""

video_whisk_code = video_whisk_code.replace('                log.info(f"UI Auto: Setting Count to {count}x...")', duration_code)

video_whisk_code = video_whisk_code.replace("max_wait = 180", "max_wait = 600")
video_whisk_code = video_whisk_code.replace("> 170:", "> 550:")

content = content[:end_idx] + video_whisk_code + '\n' + content[end_idx:]

# hook generate_video
old_gen_video = re.search(r'    async def generate_video\(self, .*?return self\._extract_generation_id\(result, 0\) or result', content, re.DOTALL)
if old_gen_video:
    new_gen_video = """    async def generate_video(self, prompt, image_paths=None, model="veo-3.1-fast", aspect_ratio="16:9", duration=8, quality="720p", seed=None, project_name="", count=1, callback=None):
        return await self._generate_video_whisk(prompt, image_paths, model, aspect_ratio, duration, project_name, count, callback)"""
    content = content.replace(old_gen_video.group(0), new_gen_video)
else:
    print("Could not hook generate_video!")

with open('services/flow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully injected _generate_video_whisk!")
