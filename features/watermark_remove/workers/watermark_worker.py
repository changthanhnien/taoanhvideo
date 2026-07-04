from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal

from features.watermark_remove.services.lama_engine import LamaEngine
from features.watermark_remove.services.smart_engine import SmartEngine
from features.watermark_remove.services.telea_engine import TeleaEngine
from features.watermark_remove.services.blur_engine import BlurEngine

class WatermarkSignals(QObject):
    item_started = Signal(int, str)
    item_progress = Signal(int, int, int, str)
    item_done = Signal(int, str, str)
    item_error = Signal(int, str)
    all_done = Signal()
    download_progress = Signal(int, int)
    log_msg = Signal(str)

class WatermarkRemoveWorker(QThread):
    def __init__(self, items, output_folder, parent=None):
        super().__init__(parent)
        self.items = items
        self.output_folder = output_folder
        self.signals = WatermarkSignals()
        self._cancelled = False
        
        self.engines = {
            "lama": LamaEngine(),
            "smart": SmartEngine(sensitivity="medium"),
            "telea": TeleaEngine(),
            "blur": BlurEngine()
        }

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            out_dir = Path(self.output_folder) if self.output_folder else None
            if out_dir:
                out_dir.mkdir(parents=True, exist_ok=True)
                
            for index, item in enumerate(self.items):
                if self._cancelled:
                    break
                    
                path = Path(item["path"])
                rect = item["rect"]
                params = item.get("params", {})
                method = params.get("method", "lama").lower()
                
                target_dir = out_dir or path.parent
                target_dir.mkdir(parents=True, exist_ok=True)
                output_path = target_dir / f"{path.stem}_clean{path.suffix}"
                
                self.signals.item_started.emit(index, str(path))
                
                try:
                    engine = self.engines.get(method)
                    if not engine:
                        raise RuntimeError(f"Unknown method: {method}")

                    if method == "lama":
                        # LaMa engine has a check_and_download_model method
                        engine.check_and_download_model(
                            progress_cb=lambda done, total, msg="": self.signals.download_progress.emit(done, total)
                        )
                        
                    if item["is_video"]:
                        engine.process_video(
                            path, 
                            output_path, 
                            rect, 
                            params,
                            progress_cb=lambda done, total, msg="Đang xử lý video...": self.signals.item_progress.emit(index, done, total, msg)
                        )
                    else:
                        engine.process_image(path, output_path, rect, params)
                        
                    self.signals.item_done.emit(index, str(path), str(output_path))
                except Exception as e:
                    self.signals.item_error.emit(index, str(e))
        finally:
            self.signals.all_done.emit()
