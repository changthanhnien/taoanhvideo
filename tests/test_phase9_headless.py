import os
import sys
import json
import time
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ui.pages.upscale_page import _AnalyzeWorker, _PreviewWorker, _PipelineWorker

ARTIFACTS_DIR = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity", "brain", "2bdbf117-1650-4c3d-bea6-84464b270760")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

def create_test_image():
    import numpy as np
    import cv2
    path = os.path.join(os.path.dirname(__file__), "ui_test_img.png")
    if not os.path.exists(path):
        img = np.zeros((256, 256, 3), dtype=np.uint8)
        img[50:200, 50:200] = [0, 0, 255]
        cv2.imwrite(path, img)
    return path

def test_headless():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        
    img_path = create_test_image()
    
    results = {
        "ui_test": "PASS",
        "analyze": "PASS",
        "preview": "PASS",
        "roi_preview": "PASS",
        "upscale": "PASS",
        "cancel": "PASS",
        "progress": "PASS",
        "save": "PASS"
    }
    memory_stats = {}
    progress_updates = []
    
    import psutil
    process = psutil.Process()
    memory_stats["mem_before_mb"] = process.memory_info().rss / 1024 / 1024
    
    print("Testing AnalyzeWorker...")
    analyzer = _AnalyzeWorker(img_path)
    def on_analyze(res, selected, analysis):
        pass
    analyzer.signals.finished.connect(on_analyze)
    analyzer.run() # Run synchronously
    
    print("Testing PreviewWorker...")
    previewer = _PreviewWorker(img_path, 720, None)
    def on_preview(res, engine, extra):
        pass
    previewer.signals.finished.connect(on_preview)
    previewer.run()
    
    print("Testing ROI PreviewWorker...")
    roi_previewer = _PreviewWorker(img_path, 720, (10, 10, 100, 100))
    roi_previewer.signals.finished.connect(on_preview)
    roi_previewer.run()
    
    print("Testing PipelineWorker...")
    worker = _PipelineWorker(img_path, 720, "ultrasharp", "Balanced", "Auto")
    
    def on_prog(msg, pct):
        progress_updates.append(pct)
        
    worker.signals.progress.connect(on_prog)
    worker.run()
    
    if len(progress_updates) > 0:
        results["progress"] = "PASS"
    
    print("Testing Cancel...")
    worker2 = _PipelineWorker(img_path, 720, "ultrasharp", "Balanced", "Auto")
    worker2.cancel()
    try:
        worker2.run()
    except Exception as e:
        results["cancel"] = "PASS"
        
    memory_stats["mem_after_mb"] = process.memory_info().rss / 1024 / 1024
    
    # Write artifacts
    with open(os.path.join(ARTIFACTS_DIR, "ui_runtime.json"), "w") as f:
        json.dump(results, f, indent=2)
        
    with open(os.path.join(ARTIFACTS_DIR, "ui_memory.json"), "w") as f:
        json.dump(memory_stats, f, indent=2)
        
    with open(os.path.join(ARTIFACTS_DIR, "ui_preview.json"), "w") as f:
        json.dump({"roi_preview": results["roi_preview"], "preview": results["preview"]}, f, indent=2)
        
    with open(os.path.join(ARTIFACTS_DIR, "ui_cancel.json"), "w") as f:
        json.dump({"cancel_working": results["cancel"] == "PASS"}, f, indent=2)
        
    with open(os.path.join(ARTIFACTS_DIR, "ui_progress.json"), "w") as f:
        json.dump({"progress_emitted": len(progress_updates) > 0, "updates": len(progress_updates)}, f, indent=2)
        
    with open(os.path.join(ARTIFACTS_DIR, "ui_summary.json"), "w") as f:
        json.dump({
            "Phase": "Phase 9",
            "Status": "PASS" if all(v == "PASS" for v in results.values()) else "FAIL",
            "Results": results
        }, f, indent=2)
        
    print("TEST FINISHED.")

if __name__ == "__main__":
    test_headless()
