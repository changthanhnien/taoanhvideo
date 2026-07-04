import os
import json
import time
import subprocess
import cv2
import numpy as np
import threading
from pathlib import Path
from config.constants import DATA_DIR

class BenchmarkManager:
    _env_cache = None
    _lock = threading.RLock()
    
    # Singleton pattern to share lock across instances if needed
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BenchmarkManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, bin_dir=None):
        if not hasattr(self, 'initialized'):
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            self.benchmark_file = os.path.join(DATA_DIR, "benchmark.json")
            self.bin_dir = bin_dir or os.path.abspath(os.path.join(self.base_dir, "..", "..", "bin", "realesrgan-ncnn"))
            self.ncnn_exe = os.path.join(self.bin_dir, "realesrgan-ncnn-vulkan.exe")
            self.models_dir = os.path.join(self.bin_dir, "models")
            self.initialized = True
        
    def get_environment(self):
        with self._lock:
            if self._env_cache is not None:
                return self._env_cache
                
            # 1. GPU Name
            gpu_name = "Unknown"
            try:
                out = subprocess.check_output('wmic path win32_VideoController get name', shell=True, text=True, creationflags=0x08000000)
                lines = [line.strip() for line in out.split('\n') if line.strip()]
                if len(lines) > 1: gpu_name = lines[1]
            except: pass
            
            # 2. Driver Version
            driver_ver = "Unknown"
            try:
                out = subprocess.check_output('wmic path win32_VideoController get DriverVersion', shell=True, text=True, creationflags=0x08000000)
                lines = [line.strip() for line in out.split('\n') if line.strip()]
                if len(lines) > 1: driver_ver = lines[1]
            except: pass
            
            # 3. NCNN Executable Hash / MTime
            ncnn_mtime = 0
            if os.path.exists(self.ncnn_exe):
                ncnn_mtime = int(os.path.getmtime(self.ncnn_exe))
                
            BenchmarkManager._env_cache = {
                "gpu": gpu_name,
                "driver": driver_ver,
                "ncnn_mtime": ncnn_mtime
            }
            return self._env_cache
        
    def load_benchmarks(self):
        with self._lock:
            env = self.get_environment()
            if not os.path.exists(self.benchmark_file):
                return {"version": 2, "environment": env, "benchmarks": {}}
            try:
                with open(self.benchmark_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    # Corruption / Version / Missing fields test
                    if not isinstance(data, dict):
                        raise ValueError("Not a dict")
                    if "environment" not in data or "benchmarks" not in data:
                        raise ValueError("Missing fields")
                    if data.get("version", 1) < 2:
                        raise ValueError("Old version")
                        
                    if data.get("environment") != env:
                        return {"version": 2, "environment": env, "benchmarks": {}}
                    return data
            except Exception:
                # Recover without crash
                return {"version": 2, "environment": env, "benchmarks": {}}
            
    def save_benchmarks(self, data):
        with self._lock:
            # Atomic write to prevent file corruption from concurrent access
            tmp_file = self.benchmark_file + ".tmp"
            try:
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                os.replace(tmp_file, self.benchmark_file)
            except Exception:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
            
    def get_benchmark(self, model_name):
        with self._lock:
            data = self.load_benchmarks()
            if model_name in data["benchmarks"]:
                return data["benchmarks"][model_name]
            return self._run_benchmark(model_name, data)
        
    def _run_benchmark(self, model_name, data):
        import tempfile
        target_model = model_name
        if model_name in ["ultrasharp", "remacri"]:
            target_model = model_name + "-4x"
            
        sizes = [512, 1024, 2048, 4096]
        results = []
        total_ms_per_mp = 0
        
        for size in sizes:
            w, h = size, size
            pixels = w * h
            megapixels = pixels / 1000000.0
            
            # Pure noise is realistic worst-case for inference time
            img = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
            
            fd_in, in_path = tempfile.mkstemp(suffix=".png")
            os.close(fd_in)
            fd_out, out_path = tempfile.mkstemp(suffix=".png")
            os.close(fd_out)
            
            cv2.imwrite(in_path, img)
            
            cmd = [
                self.ncnn_exe,
                "-i", in_path,
                "-o", out_path,
                "-s", "2",
                "-n", target_model,
                "-m", self.models_dir
            ]
            
            t0 = time.perf_counter()
            try:
                subprocess.run(cmd, check=True, capture_output=True, creationflags=0x08000000, timeout=20)
                t_el_ms = (time.perf_counter() - t0) * 1000
            except Exception:
                # Fallback on timeout or error
                t_el_ms = 5000 * megapixels
            finally:
                if os.path.exists(in_path): os.remove(in_path)
                if os.path.exists(out_path): os.remove(out_path)
                
            ms_per_mp = t_el_ms / megapixels if megapixels > 0 else 0
            results.append({
                "size": size,
                "time_ms": t_el_ms,
                "ms_per_mp": ms_per_mp
            })
            total_ms_per_mp += ms_per_mp
            
        avg_ms_per_mp = total_ms_per_mp / len(sizes) if sizes else 0
        
        bench = {
            "time_ms_per_mp": avg_ms_per_mp,
            "details": results,
            "timestamp": time.time()
        }
        
        data["benchmarks"][model_name] = bench
        self.save_benchmarks(data)
        return bench
