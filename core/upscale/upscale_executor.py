import os
import time
import subprocess
import cv2
import json

class UpscaleExecutor:
    def __init__(self, bin_dir=None):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.bin_dir = bin_dir or os.path.abspath(os.path.join(self.base_dir, "..", "..", "bin", "realesrgan-ncnn"))
        self.ncnn_exe = os.path.join(self.bin_dir, "realesrgan-ncnn-vulkan.exe")
        self.models_dir = os.path.join(self.bin_dir, "models")

    def execute(self, input_path: str, output_path: str, plan: dict, selected_model: str, target_width: int = None, target_height: int = None, progress_callback=None, cancel_event=None) -> dict:
        """
        Executes the upscale pipeline according to the ScalePlanner plan.
        """
        t0 = time.perf_counter()
        
        execution_scale = plan.get("execution_scale", 4)
        tile_size = plan.get("tile_size", 256)
        timeout = plan.get("estimated_timeout", 300)
        resize_strategy = plan.get("resize_strategy", "None")
        
        target_model = selected_model
        if selected_model in ["ultrasharp", "remacri", "upscayl-lite"]:
            target_model = f"{selected_model}-4x"
        if not os.path.exists(self.ncnn_exe):
            raise FileNotFoundError(f"Engine not found: {self.ncnn_exe}")
            
        # Post-processing requirements
        needs_resize = resize_strategy != "None" and target_width and target_height
        temp_out = output_path
        if needs_resize:
            temp_out = output_path + ".tmp.png"
            
        cmd = [
            self.ncnn_exe,
            "-i", input_path,
            "-o", temp_out,
            "-s", str(execution_scale),
            "-t", str(tile_size),
            "-n", target_model,
            "-m", self.models_dir,
            "-j", "1:1:1"
        ]
        
        try:
            # Bug 14: Log full command
            command_str = " ".join(cmd)
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=False,
                creationflags=0x08000000, cwd=os.path.dirname(self.ncnn_exe)
            )
            
            buf = b""
            stderr_full = b""
            last_progress_time = time.time()
            
            # We will use the estimated timeout as an idle timeout (with a minimum of 60s)
            idle_timeout = max(60.0, float(plan.get("estimated_timeout", 60.0)))
            
            while True:
                if cancel_event and cancel_event.is_set():
                    self._process.kill()
                    return {"status": "cancelled"}
                    
                if time.time() - last_progress_time > idle_timeout:
                    self._process.kill()
                    err_text = stderr_full.decode("utf-8", errors="replace")
                    raise RuntimeError(f"Engine Timeout: No progress for {idle_timeout}s\nCommand: {command_str}\nStderr: {err_text}")
                    
                # Read 1 byte at a time in binary to handle \r perfectly
                char = self._process.stdout.read(1)
                if not char and self._process.poll() is not None:
                    break
                    
                if char:
                    buf += char
                    stderr_full += char
                    # When we hit a percent sign, attempt to extract progress
                    if char == b'%':
                        s = buf.decode("utf-8", errors="ignore")
                        import re
                        m = re.search(r'([0-9.]+)', s)
                        if m and progress_callback:
                            try:
                                pct = float(m.group(1))
                                progress_callback(pct)
                                last_progress_time = time.time()
                            except:
                                pass
                        buf = b""
                    elif char == b'\r' or char == b'\n':
                        buf = b""
                        
            self._process.wait()
            if self._process.returncode != 0:
                if cancel_event and cancel_event.is_set():
                    raise RuntimeError("Cancelled by user")
                err_text = stderr_full.decode('utf-8', errors='ignore')
                raise RuntimeError(f"Engine failed with return code {self._process.returncode}\nCommand: {command_str}\nOutput: {err_text}")
                
        except Exception as e:
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("Cancelled by user")
            if "Cancelled by user" in str(e):
                raise
            raise RuntimeError(f"Engine Error: {str(e)}") from e
            
        # Post-processing (Lanczos)
        if needs_resize:
            img = cv2.imread(temp_out, cv2.IMREAD_UNCHANGED)
            if img is None:
                raise RuntimeError("Failed to read engine output for resizing")
                
            resized_img = cv2.resize(img, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
            cv2.imwrite(output_path, resized_img)
            
            if os.path.exists(temp_out):
                os.remove(temp_out)
                
        t_el = time.perf_counter() - t0
        
        return {
            "status": "PASS",
            "execution_time_ms": int(t_el * 1000),
            "command": " ".join(cmd),
            "resize_applied": needs_resize
        }
