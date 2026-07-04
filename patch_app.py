import os
path = r'D:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\features\watermark_remove\source\app.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

old_cmd = '''        cmd = [
            "ffmpeg", "-y", "-f", "rawvideo",
            "-vcodec", "rawvideo", "-s", f"{w}x{h}",
            "-pix_fmt", "bgr24", "-r", str(fps),
            "-i", "-", "-vcodec", "libx264", "-pix_fmt", "yuv420p",
            output_path
        ]'''

new_cmd = '''        cmd = [
            "ffmpeg", "-y", "-f", "rawvideo",
            "-vcodec", "rawvideo", "-s", f"{w}x{h}",
            "-pix_fmt", "bgr24", "-r", str(fps),
            "-i", "-", "-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p",
            "-b:v", "2M",
            output_path
        ]'''

code = code.replace(old_cmd, new_cmd)

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)
print('Patched successfully')
