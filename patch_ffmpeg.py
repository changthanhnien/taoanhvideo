import os
path = r'D:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\features\watermark_remove\source\app.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

old_cmd = '''        cmd = [
            ffmpeg, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{w}x{h}", "-pix_fmt", "bgr24", "-r", str(fps),
            "-i", "pipe:0",
            "-i", video_path,
            "-vcodec", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-vf", f"scale={scale_filter}:flags=fast_bilinear",
            "-c:a", "aac", "-b:a", "128k",
            "-map", "0:v:0", "-map", "1:a:0?",
            "-shortest", output_path,
        ]'''

new_cmd = '''        cmd = [
            ffmpeg, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{w}x{h}", "-pix_fmt", "bgr24", "-r", str(fps),
            "-i", "pipe:0",
            "-i", video_path,
            "-vcodec", "libvpx-vp9", "-row-mt", "1", "-cpu-used", "4", "-crf", "30", "-b:v", "0", "-pix_fmt", "yuv420p",
            "-vf", f"scale={scale_filter}:flags=fast_bilinear",
            "-c:a", "libvorbis", "-b:a", "128k",
            "-map", "0:v:0", "-map", "1:a:0?",
            "-shortest", output_path,
        ]'''

if old_cmd in code:
    code = code.replace(old_cmd, new_cmd)
    code = code.replace('output_name = f"{base}_no_watermark{ext}"', 'output_name = f"{base}_no_watermark.webm"')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)
    print('Patched app.py for WebM output')
else:
    print('Failed to find old cmd')
