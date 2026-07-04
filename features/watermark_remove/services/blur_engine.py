import os
import cv2
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
import numpy as np

from config.constants import FFMPEG_PATH
from utils.logger import log

class BlurEngine:
    def __init__(self):
        pass

    def _probe_video(self, video_path):
        ffmpeg_dir = Path(FFMPEG_PATH).parent
        ffprobe = ffmpeg_dir / "ffprobe.exe"
        cmd = [
            str(ffprobe if ffprobe.exists() else "ffprobe"),
            "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-of", "json", str(video_path)
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(out.stdout)
        stream = data["streams"][0]
        num, den = stream.get("r_frame_rate", "25/1").split("/")
        return int(stream["width"]), int(stream["height"]), float(num) / float(den), float(stream.get("duration") or 0)

    def _build_roi_mask(self, w, h, shape, x, y, rw, rh, points=None):
        mask = np.zeros((h, w), dtype=np.uint8)
        x2, y2 = x + rw, y + rh
        if shape == "polygon" and points and len(points) > 2:
            pts = np.array([[p["x"], p["y"]] for p in points], dtype=np.int32)
            cv2.fillPoly(mask, [pts], 255)
        elif shape == "diamond":
            cx, cy = (x + x2) // 2, (y + y2) // 2
            pts = np.array([[cx, y], [x2, cy], [cx, y2], [x, cy]], dtype=np.int32)
            cv2.fillPoly(mask, [pts], 255)
        elif shape == "ellipse":
            cx, cy = (x + x2) // 2, (y + y2) // 2
            ax, ay = max(1, rw // 2), max(1, rh // 2)
            cv2.ellipse(mask, (cx, cy), (ax, ay), 0, 0, 360, 255, -1)
        else: # rect
            mask[y:y2, x:x2] = 255
        return mask

    def process_image(self, input_path: Path, output_path: Path, rect: tuple, params: dict):
        img_bgr = cv2.imread(str(input_path))
        if img_bgr is None:
            raise RuntimeError("Cannot read image")
            
        x, y, rw, rh = rect
        shape = params.get("shape", "rect")
        points = params.get("points", [])
        h, w = img_bgr.shape[:2]
        roi_mask = self._build_roi_mask(w, h, shape, x, y, rw, rh, points=points)
        
        ksize = max(3, int(params.get("blur_size", 25)) | 1)
        blurred = cv2.GaussianBlur(img_bgr, (ksize, ksize), 0)
        out_bgr = img_bgr.copy()
        out_bgr[roi_mask > 0] = blurred[roi_mask > 0]
        
        cv2.imwrite(str(output_path), out_bgr)

    def process_video(self, input_path: Path, output_path: Path, rect: tuple, params: dict, progress_cb=None):
        input_path = Path(input_path).resolve()
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if progress_cb:
                progress_cb(0, 0, "Đang đọc metadata video...")
                
            cap = cv2.VideoCapture(str(input_path))
            if not cap.isOpened():
                raise RuntimeError("Cannot open video")
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

            x, y, rw, rh = rect
            shape = params.get("shape", "rect")
            points = params.get("points", [])
            roi_mask = self._build_roi_mask(width, height, shape, x, y, rw, rh, points=points)
            ksize = max(3, int(params.get("blur_size", 25)) | 1)

            scale_filter = "-2:1080" if width >= height else "1080:-2"

            cmd = [
                str(FFMPEG_PATH), "-y",
                "-f", "rawvideo", "-vcodec", "rawvideo",
                "-s", f"{width}x{height}", "-pix_fmt", "bgr24", "-r", str(fps),
                "-i", "pipe:0",
                "-i", str(input_path),
                "-vcodec", "libx264", "-preset", "ultrafast", "-crf", "18",
                "-vf", f"scale={scale_filter}:flags=fast_bilinear",
                "-c:a", "aac", "-b:a", "128k",
                "-map", "0:v:0", "-map", "1:a:0?",
                "-shortest", str(output_path),
            ]
            
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                if progress_cb and idx % 5 == 0:
                    progress_cb(idx, total_frames, "Đang xóa watermark bằng Blur...")
                    
                blurred = cv2.GaussianBlur(frame, (ksize, ksize), 0)
                out_bgr = frame.copy()
                out_bgr[roi_mask > 0] = blurred[roi_mask > 0]
                proc.stdin.write(out_bgr.tobytes())
                idx += 1
                
            proc.stdin.close()
            proc.wait()
            cap.release()
            
            if proc.returncode != 0:
                raise RuntimeError("FFMPEG encode failed")
            if not (output_path.exists() and output_path.stat().st_size > 0):
                raise RuntimeError("Video output empty")
        except Exception as e:
            raise RuntimeError(f"Lỗi khi xử lý video: {str(e)}")
