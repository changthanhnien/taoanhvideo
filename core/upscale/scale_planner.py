from core.upscale.models import load_models
from core.upscale.benchmark_manager import BenchmarkManager

class ScalePlanner:
    def __init__(self):
        self.models_meta = load_models()
        self.benchmark_manager = BenchmarkManager()

    def plan(self, plan_request: dict) -> dict:
        selected_model = plan_request.get("selected_model", "upscayl-lite")
        target_w = plan_request.get("target_width", 1000)
        target_h = plan_request.get("target_height", 1000)
        input_w = plan_request.get("input_width", 1000)
        input_h = plan_request.get("input_height", 1000)
        strategy = plan_request.get("strategy", "Auto")

        meta = self.models_meta.get(selected_model, {})
        preferred_scales = meta.get("preferred_scale", [2, 4])
        gpu_mem_tier = meta.get("gpu_memory", "low")

        # 1. Calculate required scale
        scale_w = target_w / max(1, input_w)
        scale_h = target_h / max(1, input_h)
        required_scale = max(scale_w, scale_h)

        # 2. Determine Execution Scale
        if required_scale <= 1.0:
            execution_scale = 1
        elif strategy == "Speed":
            # Speed mode: Use smallest preferred scale
            execution_scale = min(preferred_scales) if preferred_scales else 2
        else:
            # Auto / Quality mode: Pick the smallest preferred scale that >= required_scale
            sorted_prefs = sorted(preferred_scales)
            execution_scale = sorted_prefs[-1] if sorted_prefs else 4
            for s in sorted_prefs:
                if s >= required_scale:
                    execution_scale = s
                    break

        # 3. Determine Resize Strategy
        if execution_scale == 1:
            if required_scale < 1.0:
                resize_strategy = "LanczosDownscale"
            else:
                resize_strategy = "None"
        elif execution_scale == required_scale:
            resize_strategy = "None"
        elif execution_scale > required_scale:
            resize_strategy = "LanczosDownscale"
        else:
            resize_strategy = "LanczosUpscale"

        # 4. Memory & Tile Size Data-Driven Logic
        pixels = input_w * input_h
        
        # Use safe tile sizes to prevent GPU freezing, especially on iGPUs
        # CRITICAL: Always use tile_size = 0 (Auto) so the engine can calculate exact model padding.
        # Hardcoding tile sizes causes severe scrambling (mosaic artifacts) on new models like upscayl-lite.
        tile_size = 0
        if gpu_mem_tier == "high":
            estimated_memory = int(pixels * 0.003)
        elif gpu_mem_tier == "medium":
            estimated_memory = int(pixels * 0.002)
        else:
            estimated_memory = int(pixels * 0.001)

        estimated_memory = max(512, estimated_memory)

        # 5. Smart Timeout using Lazy Benchmark
        # Lazy Benchmark generates/gets ms_per_mp for this model
        if execution_scale == 1:
            estimated_timeout = 5
        else:
            bench_data = self.benchmark_manager.get_benchmark(selected_model)
            ms_per_mp = bench_data.get("time_ms_per_mp", 10000)
            
            # Timeout (seconds) = (megapixels * ms_per_mp * execution_scale * safety_margin) / 1000
            megapixels = pixels / 1000000.0
            base_time = (megapixels * ms_per_mp * execution_scale) / 1000.0
            safety_margin = 1.5
            estimated_timeout = max(15, int(base_time * safety_margin))

        return {
            "execution_scale": execution_scale,
            "final_scale": round(required_scale, 2),
            "resize_strategy": resize_strategy,
            "estimated_memory": estimated_memory,
            "estimated_timeout": estimated_timeout,
            "tile_size": tile_size
        }
