"""Thumbnail extraction."""

from __future__ import annotations

import subprocess
from pathlib import Path

from utils.platform import find_ffmpeg, get_subprocess_flags


def extract_thumbnail(video_path, output_path=None, time_sec=1):
    output = Path(output_path) if output_path else Path(video_path).with_suffix(".jpg")
    
    # Try to find ffmpeg via BASE_DIR first
    from config.constants import BASE_DIR
    ffmpeg = find_ffmpeg(BASE_DIR)
    if not ffmpeg:
        return None
        
    cmd = [ffmpeg, "-y", "-ss", str(time_sec), "-i", str(video_path), "-frames:v", "1", str(output)]
    
    kwargs = {"capture_output": True}
    flags = get_subprocess_flags()
    if flags != 0:
        kwargs["creationflags"] = flags
        
    proc = subprocess.run(cmd, **kwargs)
    return str(output) if proc.returncode == 0 and output.exists() else None
