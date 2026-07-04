import json
import logging
from pathlib import Path
from PySide6.QtCore import QObject, Slot
from config.constants import DATA_DIR, DEFAULT_VIDEO_OUTPUT

import sys
import importlib.util
source_dir = str(Path(__file__).resolve().parent.parent / "source")
if source_dir not in sys.path:
    sys.path.insert(0, source_dir)

# Backup original config package
original_config = sys.modules.get("config")

# Load source config.py manually
spec = importlib.util.spec_from_file_location("source_config", str(Path(source_dir) / "config.py"))
source_config = importlib.util.module_from_spec(spec)
sys.modules["source_config"] = source_config
spec.loader.exec_module(source_config)

# Temporarily replace config in sys.modules so app.py gets it
sys.modules["config"] = source_config

# Import the original Flask app directly!
# No rewriting, no duplicating logic.
from features.watermark_remove.source.app import app as source_app
import features.watermark_remove.source.app as source_app_module

# Restore original config
if original_config:
    sys.modules["config"] = original_config
else:
    del sys.modules["config"]

log = logging.getLogger(__name__)

class WatermarkBridge(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.recent_files_cache = {}
        self.session_abs_paths = {}
        
        self.app_client = source_app.test_client()
        
        self.nav_temp_dir = Path(DATA_DIR) / "watermark_transplant"
        self.nav_temp_dir.mkdir(parents=True, exist_ok=True)
        self.nav_preview_dir = self.nav_temp_dir / "previews"
        self.nav_preview_dir.mkdir(parents=True, exist_ok=True)
        
        source_app_module._videos_dir = [str(DEFAULT_VIDEO_OUTPUT)]
        source_app_module.PREVIEW_DIR = str(self.nav_preview_dir)
        source_app_module.UPLOAD_DIR = str(DEFAULT_VIDEO_OUTPUT)

        # Monkey-patch os functions in app.py to natively resolve absolute paths
        # without copying large files, which eliminates 2-minute freezes.
        orig_join = source_app_module.os.path.join
        def custom_join(path, *args):
            if path == source_app_module._videos_dir[0] and len(args) == 1:
                name = args[0]
                if name in self.session_abs_paths:
                    return self.session_abs_paths[name]
            return orig_join(path, *args)           
        orig_listdir = source_app_module.os.listdir
        def custom_listdir(p):
            entries = orig_listdir(p) if source_app_module.os.path.exists(p) else []
            if p == source_app_module._videos_dir[0]:
                entries = list(set(entries) | set(self.session_abs_paths.keys()))
                # Keep only session files and their results, ignoring leftover junk
                entries = [f for f in entries if f in self.session_abs_paths or ("_no_watermark" in f and f.replace("_no_watermark", "") in self.session_abs_paths)]
            return entries

        source_app_module.os.path.join = custom_join
        source_app_module.os.listdir = custom_listdir

    @Slot()
    def ready(self):
        log.info("[WatermarkBridge] JS Frontend is ready.")

    @Slot(result=str)
    def ping(self):
        return '{"ok":true}'

    @Slot(str, str, result=str)
    def transport_test(self, req_id, payload):
        return json.dumps({"echo_size": len(payload)})

    @Slot(str, str, result=str)
    def dispatch(self, url, json_payload):
        log.info(f"[WatermarkBridge] Dispatching to {url}")
        try:
            payload = json.loads(json_payload) if json_payload else {}
            
            if url == "/api/delete_file":
                filename = payload.get("filename")
                if filename in self.session_abs_paths:
                    del self.session_abs_paths[filename]
                # Also delete generated result
                import os
                base, ext = os.path.splitext(filename)
                out_name = f"{base}_no_watermark{ext}"
                out_path = Path(DEFAULT_VIDEO_OUTPUT) / out_name
                if out_path.exists():
                    os.remove(out_path)
                return json.dumps({"success": True})

            if url == "/api/upload":
                if "_files" in payload:
                    saved = []
                    for f in payload["_files"]:
                        path_str = f.get("path")
                        if not path_str:
                            path_str = self.recent_files_cache.get(f.get("name"))
                            
                        if path_str:
                            p = Path(path_str)
                            self.session_abs_paths[p.name] = str(p)
                            saved.append(p.name)
                    return json.dumps({"success": True, "saved": saved})

            if url == "/api/open_file_dialog":
                from PySide6.QtWidgets import QFileDialog
                from PySide6.QtWidgets import QApplication
                
                # Get the active window
                parent = QApplication.activeWindow()
                
                files, _ = QFileDialog.getOpenFileNames(
                    parent,
                    "Chọn Video hoặc Ảnh",
                    "",
                    "Video / Image Files (*.mp4 *.mov *.avi *.mkv *.wmv *.m4v *.webm *.jpg *.jpeg *.png *.webp *.bmp *.tiff *.tif)"
                )
                
                saved = []
                for abs_path in files:
                    p = Path(abs_path)
                    if p.exists():
                        self.session_abs_paths[p.name] = str(p)
                        saved.append(p.name)
                
                return json.dumps({"success": True, "saved": saved})
                
            if url == "/api/open_folder_dialog":
                from PySide6.QtWidgets import QFileDialog
                from PySide6.QtWidgets import QApplication
                import os
                
                parent = QApplication.activeWindow()
                folder = QFileDialog.getExistingDirectory(parent, "Chọn thư mục chứa Video / Ảnh")
                
                saved = []
                if folder:
                    valid_exts = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.m4v', '.webm', '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'}
                    for f in os.listdir(folder):
                        if Path(f).suffix.lower() in valid_exts:
                            abs_path = os.path.join(folder, f)
                            p = Path(abs_path)
                            self.session_abs_paths[p.name] = str(p)
                            saved.append(p.name)
                            
                return json.dumps({"success": True, "saved": saved})

            base_url = url.split("?")[0]
            if base_url in ["/api/videos", "/api/download_all"] or base_url.startswith("/api/status/"):
                response = self.app_client.get(url)
            else:
                if base_url == "/api/delete_file":
                    filename = payload.get("filename")
                    if filename in self.session_abs_paths:
                        del self.session_abs_paths[filename]
                response = self.app_client.post(url, json=payload)
            
            resp_str = response.data.decode('utf-8')
            
            # Inject session files into /api/videos response
            if base_url == "/api/videos":
                data = json.loads(resp_str)
                if "videos" in data:
                    existing_names = {v["name"] for v in data["videos"]}
                    for name, abs_path in self.session_abs_paths.items():
                        if name not in existing_names and Path(abs_path).exists():
                            p = Path(abs_path)
                            size = p.stat().st_size
                            is_img = p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif'}
                            data["videos"].append({
                                "name": name,
                                "size": size,
                                "type": "image" if is_img else "video"
                            })
                    resp_str = json.dumps(data)
            
            # Fix preview_url for QWebEngine local loading
            if '"preview_url"' in resp_str or '"before_url"' in resp_str:
                data = json.loads(resp_str)
                modified = False
                if "preview_url" in data and data["preview_url"]:
                    name = data["preview_url"].split("?")[0].split("/")[-1]
                    local_path = self.nav_preview_dir / name
                    data["preview_url"] = "file:///" + str(local_path).replace("\\", "/")
                    modified = True
                if "before_url" in data and data["before_url"]:
                    name = data["before_url"].split("?")[0].split("/")[-1]
                    local_path = self.nav_preview_dir / name
                    data["before_url"] = "file:///" + str(local_path).replace("\\", "/")
                    modified = True
                if "after_url" in data and data["after_url"]:
                    name = data["after_url"].split("?")[0].split("/")[-1]
                    local_path = self.nav_preview_dir / name
                    data["after_url"] = "file:///" + str(local_path).replace("\\", "/")
                    modified = True
                if modified:
                    resp_str = json.dumps(data)
                    
            return resp_str
        except Exception as e:
            log.error(f"[WatermarkBridge] Error dispatching {url}: {e}")
            return json.dumps({"success": False, "error": str(e)})

