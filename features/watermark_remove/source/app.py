import os
import sys
import json
import subprocess
import threading
import uuid

# --- Kiem tra thu vien bat buoc ngay khi khoi dong ---
_missing = []
try:
    import cv2
except ImportError:
    _missing.append("opencv-python-headless")
try:
    import numpy as np
except ImportError:
    _missing.append("numpy")

if _missing:
    print("\n" + "="*50)
    print("[LOI] Thieu thu vien:", ", ".join(_missing))
    print()
    print("Vui long chay run.bat thay vi chay app.py truc tiep.")
    print("Neu da dung run.bat, xoa thu muc .venv roi chay lai.")
    print("="*50 + "\n")
    input("Nhan Enter de dong...")
    sys.exit(1)

from flask import Flask, jsonify, request, send_from_directory, send_file
from werkzeug.utils import secure_filename

import sys
import os
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

try:
    from smart_remover import SmartWatermarkRemover
except ImportError as e:
    print(f"\n[LOI] Khong the import smart_remover: {e}")
    print("Chay run.bat tu dung thu muc chua file nay.")
    input("Nhan Enter de dong...")
    sys.exit(1)

import config


app = Flask(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PREVIEW_DIR = os.path.join(BASE_DIR, "previews")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
os.makedirs(PREVIEW_DIR, exist_ok=True)

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
_videos_dir: list = [UPLOAD_DIR]

# ---------------------------------------------------------------------------
# File-type helpers
# ---------------------------------------------------------------------------
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".webm"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


def _ext(name: str) -> str:
    return os.path.splitext(name)[1].lower()


def is_video(name: str) -> bool:
    return _ext(name) in VIDEO_EXTS


def is_image(name: str) -> bool:
    return _ext(name) in IMAGE_EXTS


# ---------------------------------------------------------------------------
# ffmpeg binary
# ---------------------------------------------------------------------------
def _get_ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    return "ffmpeg"


# ---------------------------------------------------------------------------
# Robust video helpers (thread-timeout to avoid hanging on bad codecs)
# ---------------------------------------------------------------------------
def _get_video_meta(video_path: str, timeout: float = 6) -> dict:
    """Get video metadata via cv2 in a background thread with timeout.
    Returns safe defaults if the file hangs (e.g. unsupported codec)."""
    result: dict = {'w': 0, 'h': 0, 'fps': 25.0, 'duration': 0.0, 'n_frames': 0}
    ev = threading.Event()

    def _read():
        try:
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                result['w'] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                result['h'] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps_ = cap.get(cv2.CAP_PROP_FPS) or 25.0
                result['fps'] = fps_
                fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                result['n_frames'] = max(fc, 0)
                result['duration'] = (fc / fps_) if fc > 0 else 0.0
                cap.release()
        except Exception:
            pass
        ev.set()

    threading.Thread(target=_read, daemon=True).start()
    ev.wait(timeout)
    return result


def _extract_frame_ffmpeg(video_path: str, out_path: str, seek_sec: float = 1.0) -> bool:
    """Extract one frame via ffmpeg subprocess (timeout=20s).
    Handles virtually all codecs; never hangs the server.
    Returns True if the output file was written successfully."""
    ffmpeg = _get_ffmpeg_bin()
    for ss in [str(seek_sec), '0']:
        cmd = [ffmpeg, '-y']
        if ss != '0':
            cmd += ['-ss', ss]
        cmd += ['-i', video_path, '-vframes', '1', '-q:v', '2', out_path]
        try:
            r = subprocess.run(cmd, timeout=20,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if r.returncode == 0 and os.path.exists(out_path):
                return True
        except subprocess.TimeoutExpired:
            pass
    return False


# ---------------------------------------------------------------------------
# ROI mask builder
# ---------------------------------------------------------------------------
def build_roi_mask(w, h, shape, x1, y1, x2, y2, points=None):
    mask = np.zeros((h, w), dtype=np.uint8)
    x1 = max(0, min(int(x1), w))
    y1 = max(0, min(int(y1), h))
    x2 = max(0, min(int(x2), w))
    y2 = max(0, min(int(y2), h))

    if shape == "poly" and points and len(points) >= 3:
        pts = np.array([[int(px), int(py)] for px, py in points], dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)
    elif shape == "diamond":
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        pts = np.array([[cx, y1], [x2, cy], [cx, y2], [x1, cy]], dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)
    elif shape == "ellipse":
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        ax, ay = max(1, (x2 - x1) // 2), max(1, (y2 - y1) // 2)
        cv2.ellipse(mask, (cx, cy), (ax, ay), 0, 0, 360, 255, -1)
    else:
        mask[y1:y2, x1:x2] = 255
    return mask


# ---------------------------------------------------------------------------
# Video helpers
# ---------------------------------------------------------------------------
def get_video_size(video_path: str):
    meta = _get_video_meta(video_path, timeout=5)
    if meta['w'] > 0:
        return meta['w'], meta['h']
    # Fallback: extract a single frame via ffmpeg and measure it
    import tempfile
    tmp = tempfile.mktemp(suffix='.png')
    if _extract_frame_ffmpeg(video_path, tmp):
        frame = cv2.imdecode(np.fromfile(tmp, dtype=np.uint8), cv2.IMREAD_COLOR)
        try: os.unlink(tmp)
        except OSError: pass
        if frame is not None:
            return frame.shape[1], frame.shape[0]
    return 1280, 720


def pick_busy_frame(video_path: str, x1, y1, x2, y2, samples=8, timeout=15):
    """Return BGR frame with highest ROI variance (texture).
    Runs in a background thread with timeout; falls back to ffmpeg if cv2 hangs."""
    result = [None]
    ev = threading.Event()

    def _run():
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                ev.set(); return
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
            step = max(1, total // samples)
            best_var, best_frame = -1.0, None
            idx = 0
            while True:
                if idx % step == 0:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    roi = frame[y1:y2, x1:x2]
                    v = float(roi.var()) if roi.size else 0.0
                    if v > best_var:
                        best_var, best_frame = v, frame
                else:
                    if not cap.grab():
                        break
                idx += 1
            if best_frame is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                _, best_frame = cap.read()
            cap.release()
            result[0] = best_frame
        except Exception:
            pass
        ev.set()

    threading.Thread(target=_run, daemon=True).start()
    ev.wait(timeout)

    if result[0] is not None:
        return result[0]

    # cv2 hung or failed — use ffmpeg to grab at least one frame
    import tempfile
    tmp = tempfile.mktemp(suffix='.png')
    if _extract_frame_ffmpeg(video_path, tmp):
        frame = cv2.imdecode(np.fromfile(tmp, dtype=np.uint8), cv2.IMREAD_COLOR)
        try: os.unlink(tmp)
        except OSError: pass
        return frame
    return None


# ---------------------------------------------------------------------------
# Processing helpers (shared by preview + video thread + image endpoint)
# ---------------------------------------------------------------------------
def apply_method_bgr(frame_bgr, method, mask, x1, y1, x2, y2, remover, params):
    """Apply removal on a BGR frame. White = 255 in any channel order."""
    pad = 20
    h, w = frame_bgr.shape[:2]
    px1, py1 = max(0, x1 - pad), max(0, y1 - pad)
    px2, py2 = min(w, x2 + pad), min(h, y2 + pad)
    
    crop_frame = frame_bgr[py1:py2, px1:px2]
    
    if method == "smart" and remover is not None:
        frame_bgr[py1:py2, px1:px2] = remover.process_frame(crop_frame)
    elif method == "inpaint":
        crop_mask = mask[py1:py2, px1:px2]
        radius = max(1, min(int((params or {}).get("radius", 5)), 25))
        frame_bgr[py1:py2, px1:px2] = cv2.inpaint(crop_frame, crop_mask, radius, cv2.INPAINT_TELEA)
    else:
        crop_mask = mask[py1:py2, px1:px2]
        ksize = max(3, int((params or {}).get("blur", 25)) | 1)
        blurred = cv2.GaussianBlur(crop_frame, (ksize, ksize), 0)
        crop_frame[crop_mask > 0] = blurred[crop_mask > 0]
        
    return frame_bgr


def apply_method_rgb(frame_rgb, method, mask, x1, y1, x2, y2, remover, params):
    """RGB wrapper (used by preview endpoint)."""
    bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    return cv2.cvtColor(
        apply_method_bgr(bgr, method, mask, x1, y1, x2, y2, remover, params),
        cv2.COLOR_BGR2RGB,
    )


# ---------------------------------------------------------------------------
# File listing
# ---------------------------------------------------------------------------
def get_files():
    folder = _videos_dir[0]
    if not os.path.isdir(folder):
        return []
    files = []
    try:
        entries = os.listdir(folder)
    except PermissionError:
        return []
    for f in entries:
        if "_no_watermark" in f:
            continue
        if not (is_video(f) or is_image(f)):
            continue
            
        base, ext = os.path.splitext(f)
        result_ext = ".png" if is_image(f) else ".webm"
        result_name = f"{base}_no_watermark{result_ext}"
        has_result = os.path.exists(os.path.join(folder, result_name))
        
        path = os.path.join(folder, f)
        try:
            stat = os.stat(path)
            files.append({
                "name": f,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "type": "image" if is_image(f) else "video",
                "has_result": has_result,
                "result_name": result_name if has_result else None
            })
        except Exception:
            pass
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files


# ---------------------------------------------------------------------------
# In-memory task store + caches
# ---------------------------------------------------------------------------
tasks = {}

# Keyed by (video_name, x1, y1, x2, y2) — avoids re-reading video frames on slider changes
_median_cache: dict = {}
# Keyed by video_name — reuse the "busy frame" across preview calls
_frame_cache: dict = {}

# ---------------------------------------------------------------------------
# Routes — static / index
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory("templates", "index.html")


@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)


@app.route("/previews/<path:path>")
def serve_previews(path):
    return send_from_directory(PREVIEW_DIR, path)

@app.route("/uploads/<path:path>")
def serve_uploads(path):
    return send_from_directory(UPLOAD_DIR, path)

@app.route("/api/download/<path:path>")
def download_file(path):
    return send_from_directory(_videos_dir[0], path, as_attachment=True)

import zipfile
import io
@app.route("/api/download_all")
def download_all():
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for root, dirs, files in os.walk(_videos_dir[0]):
            for file in files:
                if "_no_watermark" in file:
                    zf.write(os.path.join(root, file), file)
    memory_file.seek(0)
    return send_file(memory_file, download_name='processed_videos.zip', as_attachment=True)


import subprocess

@app.route("/api/open_folder", methods=["POST"])
def api_open_folder():
    try:
        data = request.json or {}
        filename = data.get("filename")
        if filename:
            filepath = os.path.join(_videos_dir[0], filename)
            if os.path.exists(filepath):
                subprocess.run(['explorer', '/select,', os.path.normpath(filepath)])
                return jsonify({"success": True})
        os.startfile(_videos_dir[0])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "files" not in request.files:
        return jsonify({"success": False, "error": "Không có file nào được chọn"})
    
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"success": False, "error": "Chưa chọn file hợp lệ"})

    target_dir = _videos_dir[0]
    os.makedirs(target_dir, exist_ok=True)
    
    saved_files = []
    for f in files:
        if f.filename:
            filename = secure_filename(f.filename)
            # fallback if secure_filename removes all characters (e.g., full CJK name)
            if not filename:
                import uuid
                ext = os.path.splitext(f.filename)[1]
                filename = f"upload_{uuid.uuid4().hex[:8]}{ext}"
                
            filepath = os.path.join(target_dir, filename)
            f.save(filepath)
            saved_files.append(filename)
            
    return jsonify({"success": True, "saved": saved_files})


# ---------------------------------------------------------------------------
# File / video list
# ---------------------------------------------------------------------------
@app.route("/api/videos", methods=["GET"])
def api_videos():
    try:
        return jsonify({"success": True, "videos": get_files(),
                        "folder": _videos_dir[0]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Extract preview frame
# ---------------------------------------------------------------------------
@app.route("/api/extract_frame", methods=["POST"])
def api_extract_frame():
    data = request.json or {}
    name = data.get("video_name")
    if not name:
        return jsonify({"success": False, "error": "Missing video_name"})

    path = os.path.join(_videos_dir[0], name)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "File not found"})

    preview_name = f"{name}_preview.png"
    preview_path = os.path.join(PREVIEW_DIR, preview_name)

    try:
        if is_image(name):
            img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                return jsonify({"success": False, "error": "Cannot read image"})
            h, w = img.shape[:2]
            _frame_cache[name] = img
            cv2.imencode('.png', img)[1].tofile(preview_path)
            return jsonify({
                "success": True,
                "preview_url": f"/previews/{preview_name}",
                "width": w, "height": h, "duration": 0, "type": "image"
            })

        # --- video: use ffmpeg to extract frame (handles all codecs, no hanging) ---
        if not os.path.exists(preview_path):
            ok = _extract_frame_ffmpeg(path, preview_path, seek_sec=1.0)
            if not ok:
                return jsonify({"success": False,
                                "error": "Không thể trích xuất khung hình "
                                         "(codec không được hỗ trợ hoặc file bị lỗi)"})

        # Read extracted frame for exact dimensions
        frame = cv2.imdecode(np.fromfile(preview_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({"success": False, "error": "Cannot read extracted frame"})
        h, w = frame.shape[:2]
        _frame_cache[name] = frame  # cache for preview reuse

        # Get duration via cv2 with timeout (best-effort, doesn't block)
        meta = _get_video_meta(path, timeout=4)
        duration = meta['duration']

        return jsonify({
            "success": True,
            "preview_url": f"/previews/{preview_name}",
            "width": w, "height": h, "duration": duration, "type": "video"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Auto-detect watermark (video-only)
# ---------------------------------------------------------------------------
@app.route("/api/detect_watermark", methods=["POST"])
def api_detect_watermark():
    data = request.json or {}
    name = data.get("video_name")
    if not name:
        return jsonify({"success": False, "error": "Missing video_name"})

    if is_image(name):
        return jsonify({"success": True, "detected": []})

    path = os.path.join(_videos_dir[0], name)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "File not found"})

    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return jsonify({"success": False, "error": "Cannot open video"})
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, total // 20)
        frames = []
        idx = 0
        while len(frames) < 20:
            if idx % step == 0:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)
            else:
                if not cap.grab():
                    break
            idx += 1
        cap.release()
        if not frames:
            return jsonify({"success": False, "error": "No frames read"})

        arr = np.array(frames)
        var_gray = np.mean(np.var(arr, axis=0), axis=2)
        mean_gray = cv2.cvtColor(np.mean(arr, axis=0).astype(np.uint8),
                                 cv2.COLOR_BGR2GRAY)
        static_mask = ((var_gray < 8.0) & (mean_gray > 30)).astype(np.uint8) * 255

        x_m, y_m = int(w * 0.25), int(h * 0.25)
        corners = {
            "top_left":     (0,     0,     x_m,   y_m),
            "top_right":    (w-x_m, 0,     w,     y_m),
            "bottom_left":  (0,     h-y_m, x_m,   h),
            "bottom_right": (w-x_m, h-y_m, w,     h),
        }
        detected = []
        scale = h / 720.0
        for corner, (cx1, cy1, cx2, cy2) in corners.items():
            region = static_mask[cy1:cy2, cx1:cx2]
            num, _, stats, _ = cv2.connectedComponentsWithStats(region)
            for i in range(1, num):
                cw = stats[i, cv2.CC_STAT_WIDTH]
                ch_ = stats[i, cv2.CC_STAT_HEIGHT]
                area = stats[i, cv2.CC_STAT_AREA]
                bx = stats[i, cv2.CC_STAT_LEFT] + cx1
                by = stats[i, cv2.CC_STAT_TOP] + cy1
                mn, mx = int(10*scale), int(150*scale)
                if (mn <= cw <= mx and mn <= ch_ <= mx
                        and int(50*scale*scale) <= area <= int(12000*scale*scale)
                        and bx > 2 and by > 2
                        and bx+cw < w-2 and by+ch_ < h-2):
                    detected.append({"corner": corner,
                                     "bbox": {"x": int(bx), "y": int(by),
                                              "width": int(cw), "height": int(ch_)},
                                     "area": int(area)})
        detected.sort(key=lambda x: x["area"], reverse=True)
        return jsonify({"success": True, "detected": detected})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Preview (before/after, single frame)
# ---------------------------------------------------------------------------
def _parse_region(data):
    x = data.get("x"); y = data.get("y")
    w = data.get("width"); h = data.get("height")
    if None in (x, y, w, h):
        return None, "Missing region parameters"
    x1 = max(0, int(x)); y1 = max(0, int(y))
    x2 = int(x + w);     y2 = int(y + h)
    if x2 <= x1 or y2 <= y1:
        return None, "Invalid region"
    return (x1, y1, x2, y2), None


@app.route("/api/preview", methods=["POST"])
def api_preview():
    data = request.json or {}
    name = data.get("video_name")
    method = data.get("method", "smart")
    sensitivity = data.get("sensitivity", "medium")
    shape = data.get("shape", "rect")
    points = data.get("points")
    params = data.get("params") or {}

    if not name:
        return jsonify({"success": False, "error": "Missing video_name"})

    region, err = _parse_region(data)
    if err:
        return jsonify({"success": False, "error": err})
    x1, y1, x2, y2 = region

    path = os.path.join(_videos_dir[0], name)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "File not found"})

    try:
        file_is_image = is_image(name)

        # Read image once (avoids duplicate imread calls)
        if file_is_image:
            img_bgr = _frame_cache.get(name) or cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img_bgr is None:
                return jsonify({"success": False, "error": "Cannot read image"})
            _frame_cache[name] = img_bgr
            fh, fw = img_bgr.shape[:2]
        else:
            img_bgr = None
            fw, fh = get_video_size(path)

        roi_mask = build_roi_mask(fw, fh, shape, x1, y1, x2, y2, points)

        pad = 20
        px1, py1 = max(0, x1 - pad), max(0, y1 - pad)
        px2, py2 = min(fw, x2 + pad), min(fh, y2 + pad)

        remover = None
        stats = None
        if method == "smart":
            remover = SmartWatermarkRemover(sensitivity=sensitivity)
            if file_is_image:
                stats = remover.analyze_image(
                    img_bgr, (px1, py1, px2, py2), roi_mask=roi_mask,
                    gain=params.get("gain"), floor=params.get("floor"),
                    edge_expand=params.get("edge"), tophat_thr=params.get("tophat"),
                    despill=params.get("despill"), edge_blur=params.get("edge_blur"))
                frame_bgr = img_bgr
            else:
                # INSTANT PREVIEW (< 500ms requirement)
                # Instead of scanning the entire video to compute a true median (which takes seconds),
                # we use the current preview frame as the 'median' via analyze_image.
                # The true median is only computed during the final `/api/process` step.
                if name not in _frame_cache:
                    _frame_cache[name] = pick_busy_frame(path, x1, y1, x2, y2)
                frame_bgr = _frame_cache[name]
                
                stats = remover.analyze_image(
                    frame_bgr, (px1, py1, px2, py2), roi_mask=roi_mask,
                    gain=params.get("gain"), floor=params.get("floor"),
                    edge_expand=params.get("edge"), tophat_thr=params.get("tophat"),
                    despill=params.get("despill"), edge_blur=params.get("edge_blur"))
        else:
            if file_is_image:
                frame_bgr = img_bgr
            else:
                if name not in _frame_cache:
                    _frame_cache[name] = pick_busy_frame(path, x1, y1, x2, y2)
                frame_bgr = _frame_cache[name]

        after_bgr = apply_method_bgr(frame_bgr.copy(), method, roi_mask,
                                     x1, y1, x2, y2, remover, params)

        pad_x = 40
        pad_y = 40
        cx1 = max(0, x1-pad_x); cy1 = max(0, y1-pad_y)
        cx2 = min(fw, x2+pad_x); cy2 = min(fh, y2+pad_y)

        stamp = uuid.uuid4().hex[:8]
        before_name = f"prev_before_{stamp}.png"
        after_name  = f"prev_after_{stamp}.png"
        
        crop_before = frame_bgr[cy1:cy2, cx1:cx2]
        crop_after = after_bgr[cy1:cy2, cx1:cx2]
        
        ch, cw = crop_before.shape[:2]
        if max(ch, cw) < 300 and max(ch, cw) > 0:
            scale = 300 / max(ch, cw)
            crop_before = cv2.resize(crop_before, (int(cw*scale), int(ch*scale)), interpolation=cv2.INTER_NEAREST)
            crop_after = cv2.resize(crop_after, (int(cw*scale), int(ch*scale)), interpolation=cv2.INTER_NEAREST)
            
        cv2.imencode('.png', crop_before)[1].tofile(os.path.join(PREVIEW_DIR, before_name))
        cv2.imencode('.png', crop_after)[1].tofile(os.path.join(PREVIEW_DIR, after_name))
        return jsonify({
            "success": True,
            "before_url": f"/previews/{before_name}",
            "after_url":  f"/previews/{after_name}",
            "stats": stats,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Process single IMAGE (sync)
# ---------------------------------------------------------------------------
@app.route("/api/process_image", methods=["POST"])
def api_process_image():
    data = request.json or {}
    name = data.get("video_name")
    method = data.get("method", "smart")
    sensitivity = data.get("sensitivity", "medium")
    shape = data.get("shape", "rect")
    points = data.get("points")
    params = data.get("params") or {}

    region, err = _parse_region(data)
    if err:
        return jsonify({"success": False, "error": err})
    x1, y1, x2, y2 = region

    path = os.path.join(_videos_dir[0], name)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "File not found"})

    try:
        img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"success": False, "error": "Cannot read image"})
        fh, fw = img.shape[:2]
        roi_mask = build_roi_mask(fw, fh, shape, x1, y1, x2, y2, points)

        pad = 20
        px1, py1 = max(0, x1 - pad), max(0, y1 - pad)
        px2, py2 = min(fw, x2 + pad), min(fh, y2 + pad)

        remover = None
        if method == "smart":
            pad = 20
            px1, py1 = max(0, x1 - pad), max(0, y1 - pad)
            px2, py2 = min(fw, x2 + pad), min(fh, y2 + pad)
            remover = SmartWatermarkRemover(sensitivity=sensitivity)
            remover.analyze_image(
                img, (px1, py1, px2, py2), roi_mask=roi_mask,
                gain=params.get("gain"), floor=params.get("floor"),
                edge_expand=params.get("edge"), tophat_thr=params.get("tophat"),
                despill=params.get("despill"), edge_blur=params.get("edge_blur"))

        out = apply_method_bgr(img, method, roi_mask, x1, y1, x2, y2, remover, params)

        base, ext = os.path.splitext(name)
        output_name = f"{base}_no_watermark.png"
        output_path = os.path.join(_videos_dir[0], output_name)
        cv2.imencode('.png', out)[1].tofile(output_path)

        return jsonify({"success": True,
                        "output_path": output_path,
                        "output_name": output_name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Process VIDEO (async thread + polling)
# ---------------------------------------------------------------------------
def process_video_thread(task_id, video_path, output_path,
                         x1, y1, x2, y2, method, sensitivity,
                         roi_mask, params, fps=30):
    try:
        params = params or {}

        meta = _get_video_meta(video_path, timeout=5)
        w = meta['w']
        h = meta['h']
        fps = meta['fps'] or 25.0
        total = max(meta['n_frames'], 1)
        
        if w == 0 or h == 0:
            # Fallback if cv2 fails to get meta
            fw, fh = get_video_size(video_path)
            w, h = fw, fh
            if w == 0 or h == 0:
                raise Exception("Cannot open video (ffmpeg meta failed)")

        mask = (roi_mask if roi_mask is not None and roi_mask.shape[:2] == (h, w)
                else cv2.resize(roi_mask, (w, h), interpolation=cv2.INTER_NEAREST)
                if roi_mask is not None
                else (lambda m: (m.__setitem__((slice(y1, y2), slice(x1, x2)), 255), m)[1])(
                    np.zeros((h, w), dtype=np.uint8)))

        pad = 20
        px1, py1 = max(0, x1 - pad), max(0, y1 - pad)
        px2, py2 = min(w, x2 + pad), min(h, y2 + pad)
        
        remover = None
        if method == "smart":
            tasks[task_id]["status"] = "analyzing"
            remover = SmartWatermarkRemover(sensitivity=sensitivity)
            try:
                remover.analyze(video_path, (px1, py1, px2, py2), roi_mask=mask,
                                gain=params.get("gain"), floor=params.get("floor"),
                                edge_expand=params.get("edge"),
                                tophat_thr=params.get("tophat"),
                                despill=params.get("despill"),
                                edge_blur=params.get("edge_blur"))
            except Exception as e:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = f"Analyze failed: {str(e)[:150]}"
                return

        tasks[task_id]["status"] = "processing"

        # Force 1080p HD output
        scale_filter = "-2:1080" if w >= h else "1080:-2"

        ffmpeg = _get_ffmpeg_bin()
        
        # --- FFmpeg Reader (Bypasses cv2.VideoCapture hangs) ---
        read_cmd = [
            ffmpeg, "-i", video_path,
            "-f", "image2pipe", "-pix_fmt", "bgr24", "-vcodec", "rawvideo", "-"
        ]
        read_proc = subprocess.Popen(read_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        
        # --- FFmpeg Writer ---
        cmd = [
            ffmpeg, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{w}x{h}", "-pix_fmt", "bgr24", "-r", str(fps),
            "-i", "pipe:0",
            "-i", video_path,
            "-vcodec", "libvpx-vp9", "-row-mt", "1", "-cpu-used", "8", "-deadline", "realtime", "-threads", "8", "-crf", "30", "-b:v", "0", "-pix_fmt", "yuv420p",
            "-vf", f"scale={scale_filter}:flags=fast_bilinear",
            "-c:a", "libvorbis", "-b:a", "128k",
            "-map", "0:v:0", "-map", "1:a:0?",
            "-shortest", output_path,
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        
        frame_size = w * h * 3
        idx = 0
        try:
            while True:
                if tasks.get(task_id, {}).get("status") == "cancelled":
                    break
                raw_frame = read_proc.stdout.read(frame_size)
                if not raw_frame or len(raw_frame) < frame_size:
                    break
                frame = np.frombuffer(raw_frame, dtype=np.uint8).copy().reshape((h, w, 3))
                out = apply_method_bgr(frame, method, mask,
                                       x1, y1, x2, y2, remover, params)
                proc.stdin.write(out.tobytes())
                idx += 1
                tasks[task_id]["progress"] = min(int(idx / total * 100), 99)
        finally:
            read_proc.terminate()
            proc.stdin.close()

        proc.wait()
        if proc.returncode != 0:
            raise Exception(f"FFmpeg failed (exit {proc.returncode})")

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["output_path"] = output_path

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)


@app.route("/api/process", methods=["POST"])
def api_process():
    data = request.json or {}
    name = data.get("video_name")
    method = data.get("method", "smart")
    sensitivity = data.get("sensitivity", "medium")
    shape = data.get("shape", "rect")
    points = data.get("points")
    params = data.get("params") or {}

    region, err = _parse_region(data)
    if err:
        return jsonify({"success": False, "error": err})
    x1, y1, x2, y2 = region

    path = os.path.join(_videos_dir[0], name)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "File not found"})

    base, ext = os.path.splitext(name)
    output_name = f"{base}_no_watermark.webm"
    output_path = os.path.join(_videos_dir[0], output_name)

    print("[TRACE] BƯỚC 5: Backend nhận request /api/process", flush=True)
    print("[TRACE] BƯỚC 5.1: Chuẩn bị gọi cv2.VideoCapture", flush=True)
    cap = cv2.VideoCapture(path)
    print("[TRACE] BƯỚC 5.2: cv2.VideoCapture đã xong", flush=True)
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.release()
    roi_mask = build_roi_mask(fw, fh, shape, x1, y1, x2, y2, points)

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "pending", "progress": 0, "error": None,
        "output_path": None, "video_name": name, "output_name": output_name,
    }
    threading.Thread(
        target=process_video_thread,
        args=(task_id, path, output_path, x1, y1, x2, y2,
              method, sensitivity, roi_mask, params, fps),
        daemon=True,
    ).start()
    return jsonify({"success": True, "task_id": task_id})


@app.route("/api/status/<task_id>", methods=["GET"])
def api_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"success": False, "error": "Task not found"})
    return jsonify({"success": True, "task": task})

@app.route("/api/reset_tasks", methods=["POST"])
def api_reset_tasks():
    for t_id, t in list(tasks.items()):
        t['status'] = 'cancelled'
    tasks.clear()
    
    target_dir = _videos_dir[0]
    if os.path.exists(target_dir):
        for f in os.listdir(target_dir):
            path = os.path.join(target_dir, f)
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except Exception:
                pass
    _frame_cache.clear()

    return jsonify({"success": True})

@app.route("/api/delete_file", methods=["POST"])
def api_delete_file():
    data = request.json or {}
    name = data.get("filename")
    if not name:
        return jsonify({"success": False, "error": "Missing filename"})
    path = os.path.join(_videos_dir[0], name)
    if os.path.exists(path):
        try:
            os.remove(path)
            # Remove from cache if present
            _frame_cache.pop(name, None)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    return jsonify({"success": False, "error": "File not found"})


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Videos / images folder : {_videos_dir[0]}")
    print(f"Starting server        : http://{config.HOST}:{config.PORT}")
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG,
            use_reloader=False)
