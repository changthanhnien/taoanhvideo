import os
import time
import cv2
import tempfile
from core.upscale.image_analyzer import ImageAnalyzer
from core.upscale.model_selector import ModelSelector
from core.upscale.scale_planner import ScalePlanner
from core.upscale.upscale_executor import UpscaleExecutor
from core.upscale.quality_checker import QualityChecker

class PreviewManager:
    def __init__(self):
        self.analyzer = ImageAnalyzer()
        self.selector = ModelSelector()
        self.planner = ScalePlanner()
        self.executor = UpscaleExecutor()
        self.checker = QualityChecker()

    def run_preview(self, input_path: str, output_path: str, roi=None, target_width=None, target_height=None) -> dict:
        """
        Runs the full upscale pipeline on a cropped region (default 256x256 center).
        roi: (x, y, w, h)
        """
        img = cv2.imread(input_path)
        if img is None:
            raise ValueError(f"Cannot read image: {input_path}")
            
        h, w = img.shape[:2]
        
        # 1. Determine ROI (Default Center Crop 256x256)
        if roi is None:
            crop_w, crop_h = min(256, w), min(256, h)
            x = (w - crop_w) // 2
            y = (h - crop_h) // 2
            roi = (x, y, crop_w, crop_h)
            
        x, y, crop_w, crop_h = roi
        
        # Ensure ROI is within bounds
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        crop_w = max(1, min(crop_w, w - x))
        crop_h = max(1, min(crop_h, h - y))
        
        cropped_img = img[y:y+crop_h, x:x+crop_w]
        
        # Calculate proportional target size for the crop
        if target_width and target_height:
            scale_w = target_width / max(1, w)
            scale_h = target_height / max(1, h)
            preview_target_w = int(crop_w * scale_w)
            preview_target_h = int(crop_h * scale_h)
        else:
            preview_target_w, preview_target_h = crop_w * 4, crop_h * 4 # Default 4x
            
        preview_target_w = max(1, preview_target_w)
        preview_target_h = max(1, preview_target_h)
        
        # Use temp file for crop, use .bmp to avoid PNG compression/decompression overhead
        fd_in, temp_in = tempfile.mkstemp(suffix=".bmp")
        os.close(fd_in)
        cv2.imwrite(temp_in, cropped_img)
        
        try:
            t_start_pipeline = time.perf_counter()
            
            # Pipeline
            analysis = self.analyzer.analyze(temp_in)
            selected_model = self.selector.select(analysis)["selected_model"]
            
            plan_request = {
                "selected_model": selected_model,
                "input_width": crop_w,
                "input_height": crop_h,
                "target_width": preview_target_w,
                "target_height": preview_target_h,
                "strategy": "Speed" # Use Speed for Preview to ensure < 1s
            }
            plan = self.planner.plan(plan_request)
            
            # We use the dynamically estimated timeout from ScalePlanner which accounts for machine speed
            
            t_start_engine = time.perf_counter()
            exec_res = self.executor.execute(temp_in, output_path, plan, selected_model, preview_target_w, preview_target_h)
            t_engine = (time.perf_counter() - t_start_engine) * 1000
            
            quality = self.checker.check(output_path)
            
            total_time = (time.perf_counter() - t_start_pipeline) * 1000
            manager_overhead = total_time - t_engine
            engine_bottleneck_ratio = t_engine / max(1, total_time)
            
            return {
                "status": "PASS",
                "preview_time_ms": total_time,
                "engine_time_ms": t_engine,
                "manager_overhead_ms": manager_overhead,
                "engine_bottleneck_ratio": engine_bottleneck_ratio,
                "roi": (x, y, crop_w, crop_h),
                "plan": plan,
                "execution_result": exec_res,
                "quality": quality
            }
        finally:
            if os.path.exists(temp_in):
                try:
                    os.remove(temp_in)
                except:
                    pass
