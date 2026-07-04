"""Workflow execution engine.

Executes workflow graphs in topological order, routing data between nodes
via an internal data store keyed by (node_id, port_name).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QMutex, QObject, QThread, QWaitCondition, Signal

from utils.logger import log

# ---------------------------------------------------------------------------
# Optional imports – gracefully degrade when modules are missing
# ---------------------------------------------------------------------------
_task_manager_available = False
try:
    from workers.task_manager import TaskManager  # noqa: F401
    from config.constants import TaskMode, FFMPEG_PATH, DEFAULT_IMAGE_OUTPUT, DEFAULT_VIDEO_OUTPUT
    _task_manager_available = True
except Exception:
    TaskMode = None  # type: ignore[assignment,misc]
    FFMPEG_PATH = "ffmpeg"
    DEFAULT_IMAGE_OUTPUT = Path.home() / ".vidgen" / "image_output"
    DEFAULT_VIDEO_OUTPUT = Path.home() / ".vidgen" / "video_output"


# ---------------------------------------------------------------------------
# Execution Thread
# ---------------------------------------------------------------------------

class ExecutionThread(QThread):
    """Worker thread that drives the executor's run plan.

    Communicates back to the :class:`WorkflowExecutor` via signals defined on
    the executor itself.  Supports *pause* / *stop* flags inspected between
    node executions and within long-running operations.
    """

    node_started = Signal(str)
    node_finished = Signal(str, str)       # node_id, 'success' | 'error'
    node_progress = Signal(str, int, int)  # node_id, current, total
    execution_finished = Signal(bool)
    log_message = Signal(str, str)         # node_id, message
    task_requested = Signal(int)        # task_id
    node_output_updated = Signal(str, dict)  # node_id, result_dict

    def __init__(
        self,
        plan: list[str],
        workflow_data: dict,
        node_configs: dict,
        connections: list[dict],
        data_store: dict[str, dict[str, Any]],
        main_win=None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._main_win = main_win
        self._plan = plan
        self._workflow_data = workflow_data
        self._node_configs = node_configs
        self._connections = connections
        self._data_store = data_store

        self._stop_flag = False
        self._pause_flag = False
        self._mutex = QMutex()
        self._pause_cond = QWaitCondition()

    # -- Control ----------------------------------------------------------

    def request_stop(self) -> None:
        self._stop_flag = True
        # Wake the thread if it is paused so it can exit
        self._pause_cond.wakeAll()

    def request_pause(self) -> None:
        self._pause_flag = True

    def request_resume(self) -> None:
        self._pause_flag = False
        self._pause_cond.wakeAll()

    @property
    def is_stopped(self) -> bool:
        return self._stop_flag

    @property
    def is_paused(self) -> bool:
        return self._pause_flag

    # -- Helpers ----------------------------------------------------------

    def _check_pause(self) -> None:
        """Block the thread while the pause flag is set."""
        self._mutex.lock()
        while self._pause_flag and not self._stop_flag:
            self._pause_cond.wait(self._mutex)
        self._mutex.unlock()

    def _gather_inputs(self, node_id: str) -> dict[str, Any]:
        """Collect input data for *node_id* from upstream connections."""
        inputs: dict[str, Any] = {}
        for conn in self._connections:
            if conn.get("target_node") == node_id:
                src_node = conn.get("source_node", "")
                src_port = conn.get("source_port", "output")
                tgt_port = conn.get("target_port", "input")
                upstream = self._data_store.get(src_node, {})
                if src_port in upstream:
                    val = upstream[src_port]
                    # Merge list-type data when multiple connections target the
                    # same port.
                    if tgt_port in inputs:
                        existing = inputs[tgt_port]
                        if isinstance(existing, list) and isinstance(val, list):
                            inputs[tgt_port] = existing + val
                        elif isinstance(existing, list):
                            inputs[tgt_port] = existing + [val]
                        else:
                            inputs[tgt_port] = [existing, val] if val != existing else existing
                    else:
                        inputs[tgt_port] = val
        return inputs

    # -- Node executors ---------------------------------------------------

    def _exec_text_prompt(self, node_data: dict, config: dict, inputs: dict) -> dict[str, Any]:
        text: str = config.get("prompt", "")
        variables: dict = config.get("variables", {})
        # Expand {{var}} placeholders
        for key, value in variables.items():
            text = text.replace("{{" + key + "}}", str(value))
        # Also expand {var} placeholders (single-brace)
        for key, value in variables.items():
            text = text.replace("{" + key + "}", str(value))
        return {"output": text}

    def _exec_upload_image(self, node_data: dict, config: dict, inputs: dict) -> dict[str, Any]:
        file_paths: list[str] = config.get("images", config.get("file_paths", []))
        valid: list[str] = []
        for fp in file_paths:
            p = Path(fp)
            if p.exists() and p.is_file():
                valid.append(str(p))
            else:
                self.log_message.emit(
                    node_data.get("id", ""),
                    f"Không tìm thấy file ảnh: {fp}",
                )
        return {"output": valid}

    def _exec_upload_video(self, node_data: dict, config: dict, inputs: dict) -> dict[str, Any]:
        file_paths: list[str] = config.get("videos", config.get("file_paths", []))
        valid: list[str] = []
        for fp in file_paths:
            p = Path(fp)
            if p.exists() and p.is_file():
                valid.append(str(p))
            else:
                self.log_message.emit(
                    node_data.get("id", ""),
                    f"Không tìm thấy file video: {fp}",
                )
        return {"output": valid}

    def _exec_history(self, node_data: dict, config: dict, inputs: dict) -> dict[str, Any]:
        node_id = node_data.get("id", "")
        items = config.get("items", [])
        if not items:
            raise RuntimeError("Chưa chọn mục nào từ lịch sử.")
            
        # Optional filter by media_type
        media_type = config.get("media_type", "Video").lower()
        
        filtered = []
        for path in items:
            ext = Path(path).suffix.lower()
            is_vid = ext in ('.mp4', '.mov', '.avi', '.webm')
            if media_type == "video" and is_vid:
                filtered.append(path)
            elif media_type == "ảnh" and not is_vid:
                filtered.append(path)
            elif media_type not in ("video", "ảnh"):
                filtered.append(path)
                
        if not filtered:
            self.log_message.emit(node_id, f"Không có file nào khớp với loại '{media_type}'")
            return {"output": []}
            
        self.log_message.emit(node_id, f"Đã xuất {len(filtered)} file từ lịch sử.")
        return {"output": filtered}

    def _exec_generate_image(self, node_data: dict, config: dict, inputs: dict) -> dict[str, Any]:
        node_id = node_data.get("id", "")
        if not _task_manager_available:
            raise RuntimeError("Module task_manager không khả dụng – không thể tạo ảnh.")
        # The "input" port can contain both text prompts and image paths (merged as a list)
        raw_inputs = inputs.get("input", inputs.get("prompt", inputs.get("output", [])))
        if not isinstance(raw_inputs, list):
            raw_inputs = [raw_inputs]
            
        prompts = []
        ref_images = []
        for item in raw_inputs:
            if isinstance(item, list):
                for subitem in item:
                    if isinstance(subitem, str) and Path(subitem).exists():
                        ref_images.append(subitem)
                    elif str(subitem).strip():
                        prompts.append(str(subitem))
            elif isinstance(item, str) and Path(item).exists():
                ref_images.append(item)
            elif str(item).strip():
                prompts.append(str(item))
                
        # If no prompt connected, fallback to config prompt
        if not prompts:
            cfg_prompt = config.get("prompt", "")
            if cfg_prompt:
                prompts.append(cfg_prompt)
                
        prompt = "\n".join(prompts)

        model = config.get("model", "Nano Banana 2")
        # Strip emoji prefix (e.g. "🍌 Nano Banana 2" → "Nano Banana 2")
        import re
        model = re.sub(r'^[\U0001F300-\U0001FAFF\u2600-\u27BF\u2702-\u27B0]+\s*', '', model).strip()
        aspect_ratio = config.get("aspect_ratio", config.get("ratio", "16:9"))
        count = int(config.get("count", 1))

        output_dir = Path(config.get("output_dir", str(DEFAULT_IMAGE_OUTPUT)))
        output_dir.mkdir(parents=True, exist_ok=True)

        self.log_message.emit(node_id, f"Tạo {count} ảnh với model {model}…")
        self.node_progress.emit(node_id, 0, count)

        # Real execution via TaskManager
        import json
        from models.task import VideoTask, TaskItem
        from config.constants import TaskMode, ItemStatus

        main_win = self._main_win

        if not main_win or not hasattr(main_win, "db"):
            self.log_message.emit(node_id, "Không tìm thấy MainWindow hoặc Database, không thể tạo ảnh thực tế.")
            return {"output": []}

        project = main_win.db.get_or_create_project("Workflow")
        
        # Determine creation mode based on input images
        creation_mode = "Ảnh -> Ảnh" if ref_images else "Text -> Image"
        
        vtask = VideoTask(
            project_id=project.id,
            name=f"Workflow_{node_id[:8]}",
            mode=TaskMode.IMAGE,
            image_model=model,
            aspect_ratio=aspect_ratio,
            output_folder=str(output_dir),
            total_count=1,
            config=json.dumps({
                "creation_mode": creation_mode, 
                "image_count": count,
                "uploaded_images": ref_images
            }),
        )
        vtask = main_win.db.create_task(vtask)
        
        item = TaskItem(
            task_id=vtask.id,
            prompt=prompt,
            reference_image=ref_images[0] if ref_images else None
        )
            
        main_win.db.add_task_items_bulk([item])
        vtask.items = [item]
        
        self.log_message.emit(node_id, f"Bắt đầu tạo {count} ảnh thực tế...")
        self.task_requested.emit(vtask.id)
        
        output_paths: list[str] = []
        last_emitted_outputs = []
        # Wait for the task to complete
        while True:
            if self._stop_flag:
                manager = main_win._get_task_manager() if hasattr(main_win, '_get_task_manager') else None
                if manager:
                    manager.cancel_task(vtask.id)
                break
            self._check_pause()
            
            # Poll db for completion
            db_items = main_win.db.get_task_items(vtask.id)
            all_done = True
            completed_count = 0
            for it in db_items:
                if it.status in (ItemStatus.COMPLETED, ItemStatus.ERROR):
                    completed_count += 1
                else:
                    all_done = False
            self.node_progress.emit(node_id, completed_count, 1)
            
            current_outputs = []
            for it in db_items:
                if it.status == ItemStatus.COMPLETED and getattr(it, "output_path", None):
                    current_outputs.extend([p for p in it.output_path.split("|") if p.strip()])
                    
            if current_outputs != last_emitted_outputs:
                last_emitted_outputs = list(current_outputs)
                output_paths = list(current_outputs)
                self.node_output_updated.emit(node_id, {"output": current_outputs})
                
            if all_done:
                break
            time.sleep(2)
            
        if not output_paths and not self._stop_flag:
            self.log_message.emit(node_id, "Tạo ảnh thất bại (không có kết quả trả về).")
            raise RuntimeError("Tạo ảnh thất bại (không có kết quả trả về).")
        else:
            self.log_message.emit(node_id, f"Đã nhận {len(output_paths)} ảnh thành công.")

        return {
            "output": output_paths,
            "prompt": prompt,
            "model": model,
            "aspect_ratio": aspect_ratio,
            "reference_images": ref_images,
        }

    def _exec_generate_video(self, node_data: dict, config: dict, inputs: dict) -> dict[str, Any]:
        node_id = node_data.get("id", "")
        if not _task_manager_available:
            raise RuntimeError("Module task_manager không khả dụng – không thể tạo video.")
        # The "input" port can contain both text prompts and video/image paths (merged as a list)
        raw_inputs = inputs.get("input", inputs.get("prompt", inputs.get("output", [])))
        if not isinstance(raw_inputs, list):
            raw_inputs = [raw_inputs]
            
        prompts = []
        ref_images = []
        for item in raw_inputs:
            if isinstance(item, list):
                for subitem in item:
                    if isinstance(subitem, str) and Path(subitem).exists():
                        ref_images.append(subitem)
                    elif str(subitem).strip():
                        prompts.append(str(subitem))
            elif isinstance(item, str) and Path(item).exists():
                ref_images.append(item)
            elif str(item).strip():
                prompts.append(str(item))
                
        # Also check config for reference_image
        cfg_ref_img = config.get("reference_image", [])
        if cfg_ref_img and isinstance(cfg_ref_img, list):
            for img in cfg_ref_img:
                if Path(img).exists() and img not in ref_images:
                    ref_images.append(img)
                
        # If no prompt connected, fallback to config prompt
        if not prompts:
            cfg_prompt = config.get("prompt", "")
            if cfg_prompt:
                prompts.append(cfg_prompt)
                
        prompt = "\n".join(prompts)

        model = config.get("model", config.get("quality", "Omni Flash"))
        aspect_ratio = config.get("aspect_ratio", config.get("ratio", "16:9"))
        duration_str = config.get("duration", "8s")
        duration = int(str(duration_str).replace("s", ""))
        count = int(config.get("count", 1))
        
        # Only Omni Flash supports 10s, clamp others to 8s max
        if "Omni Flash" not in model and duration > 8:
            duration = 8
            self.log_message.emit(node_id, f"Model {model} chỉ hỗ trợ tối đa 8s, đã giảm từ {duration_str}.")
        
        # Get start/end frame images from config (frame_pair returns {start: [...], end: [...]})
        frames_data = config.get("frames", {}) or {}
        start_frame_files = frames_data.get("start", []) if isinstance(frames_data, dict) else []
        end_frame_files = frames_data.get("end", []) if isinstance(frames_data, dict) else []
        start_frame = start_frame_files[0] if start_frame_files and Path(start_frame_files[0]).exists() else None
        end_frame = end_frame_files[0] if end_frame_files and Path(end_frame_files[0]).exists() else None

        output_dir = Path(config.get("output_dir", str(DEFAULT_VIDEO_OUTPUT)))
        output_dir.mkdir(parents=True, exist_ok=True)

        self.log_message.emit(node_id, f"Tạo {count} video ({model}, {aspect_ratio}, {duration}s)…")
        self.node_progress.emit(node_id, 0, count)

        # Real execution via TaskManager
        import json
        from models.task import VideoTask, TaskItem
        from config.constants import TaskMode, ItemStatus

        main_win = self._main_win

        if not main_win or not hasattr(main_win, "db"):
            self.log_message.emit(node_id, "Không tìm thấy MainWindow hoặc Database, không thể tạo video thực tế.")
            return {"output": []}

        project = main_win.db.get_or_create_project("Workflow")
        
        # Determine creation mode based on input images and frames
        if start_frame or end_frame:
            creation_mode = "Frame -> Video"
        elif ref_images:
            creation_mode = "Ảnh -> Video"
        else:
            creation_mode = "Text -> Video"
        
        # task_manager passes vtask.quality directly as model= to generate_video
        model_key = model
        
        vtask = VideoTask(
            project_id=project.id,
            name=f"WF_Vid_{node_id[:8]}",
            mode=TaskMode.VIDEO,
            quality=model_key,
            aspect_ratio=aspect_ratio,
            output_folder=str(output_dir),
            total_count=count,
            config=json.dumps({
                "creation_mode": creation_mode,
                "duration": f"{duration}s",
                "uploaded_images": ref_images,
            }),
        )
        vtask = main_win.db.create_task(vtask)
        
        # Create one TaskItem per video
        items = []
        for i in range(count):
            ts = int(time.time() * 1000) + i
            out_path = output_dir / f"wf_vid_{node_id[:8]}_{i}_{ts}.mp4"
            item = TaskItem(
                task_id=vtask.id,
                prompt=prompt,
                reference_image=ref_images[0] if ref_images else None,
                output_path=str(out_path),
            )
            # Attach start/end frames if available
            if start_frame:
                item.start_frame = start_frame
            if end_frame:
                item.end_frame = end_frame
            items.append(item)
            
        main_win.db.add_task_items_bulk(items)
        vtask.items = items
        
        self.log_message.emit(node_id, f"Bắt đầu tạo {count} video thực tế...")
        self.task_requested.emit(vtask.id)
        
        output_paths: list[str] = []
        last_emitted_outputs = []
        # Wait for the task to complete
        while True:
            if self._stop_flag:
                manager = main_win._get_task_manager() if hasattr(main_win, '_get_task_manager') else None
                if manager:
                    manager.cancel_task(vtask.id)
                break
            self._check_pause()
            
            # Poll db for completion
            db_items = main_win.db.get_task_items(vtask.id)
            all_done = True
            completed_count = 0
            for it in db_items:
                if it.status in (ItemStatus.COMPLETED, ItemStatus.ERROR):
                    completed_count += 1
                else:
                    all_done = False
            self.node_progress.emit(node_id, completed_count, count)
            
            current_outputs = []
            for it in db_items:
                if it.status == ItemStatus.COMPLETED and getattr(it, "output_path", None):
                    current_outputs.extend([p for p in it.output_path.split("|") if p.strip()])
                    
            if current_outputs != last_emitted_outputs:
                last_emitted_outputs = list(current_outputs)
                output_paths = list(current_outputs)
                self.node_output_updated.emit(node_id, {"output": current_outputs})
                
            if all_done:
                break
            time.sleep(3)
        if not output_paths and not self._stop_flag:
            self.log_message.emit(node_id, "Tạo video thất bại (không có kết quả trả về).")
            raise RuntimeError("Tạo video thất bại (không có kết quả trả về).")
        else:
            self.log_message.emit(node_id, f"Đã nhận {len(output_paths)} video thành công.")

        return {
            "output": output_paths,
            "prompt": prompt,
            "model": model,
            "aspect_ratio": aspect_ratio,
            "reference_images": ref_images,
        }

    def _exec_merge_video(self, node_data: dict, config: dict, inputs: dict) -> dict[str, Any]:
        node_id = node_data.get("id", "")
        
        # Read selected videos from config
        selected_videos = config.get("videos", [])
        keep_audio = True
        
        # Gather all video file paths from inputs
        raw_inputs = inputs.get("input", inputs.get("output", []))
        if isinstance(raw_inputs, str):
            raw_inputs = [raw_inputs]
        input_files = [f for f in (raw_inputs or []) if Path(f).exists()]
        
        # Build final list of videos to merge with trim info
        videos_to_merge = []
        
        if not selected_videos:
            # Fallback: Just use inputs if no config is set
            for f in input_files:
                videos_to_merge.append({"path": f, "start": 0.0, "end": 1.0})
        else:
            for v in selected_videos:
                v_path = v.get("path", "")
                if "wf_vid_" in v_path and not Path(v_path).exists():
                    # This is a reference to a connected node: wf_vid_{node_id}
                    nid = v_path.replace("wf_vid_", "")[:8]
                    # Find matching files in inputs
                    matches = [f for f in input_files if nid in Path(f).name]
                    for m in matches:
                        videos_to_merge.append({
                            "path": m,
                            "start": v.get("start", 0.0),
                            "end": v.get("end", 1.0)
                        })
                elif Path(v_path).exists():
                    videos_to_merge.append(v)
                    
        # Filter valid video and image extensions
        videos_to_merge = [v for v in videos_to_merge if Path(v["path"]).suffix.lower() in (".mp4", ".mov", ".avi", ".mkv", ".webm", ".png", ".jpg", ".jpeg", ".webp")]

        if len(videos_to_merge) < 1:
            raise RuntimeError(f"Không có video/ảnh hợp lệ nào để ghép.")

        output_dir = Path(config.get("output_dir", str(DEFAULT_VIDEO_OUTPUT)))
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        output_path = output_dir / f"merged_{node_id}_{ts}.mp4"

        ffmpeg = str(FFMPEG_PATH) if FFMPEG_PATH else "ffmpeg"

        concat_file = output_dir / f"_concat_{node_id}_{ts}.txt"
        
        def get_duration(path):
            try:
                cmd = [ffmpeg.replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                res = subprocess.run(cmd, capture_output=True, text=True, creationflags=flags)
                return float(res.stdout.strip())
            except:
                return 8.0

        has_image = False
        try:
            with open(concat_file, "w", encoding="utf-8") as f:
                for v in videos_to_merge:
                    vp = str(Path(v["path"]).resolve()).replace("'", "'\\''")
                    f.write(f"file '{vp}'\n")
                    
                    is_img = Path(v["path"]).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
                    if is_img:
                        has_image = True
                        f.write(f"duration 8.0\n")
                    else:
                        start_ratio = v.get("start", 0.0)
                        end_ratio = v.get("end", 1.0)
                        if start_ratio > 0.01 or end_ratio < 0.99:
                            dur = get_duration(vp)
                            start_sec = dur * start_ratio
                            end_sec = dur * end_ratio
                            f.write(f"inpoint {start_sec:.3f}\n")
                            f.write(f"outpoint {end_sec:.3f}\n")

            self.log_message.emit(node_id, f"Ghép {len(videos_to_merge)} mục bằng ffmpeg…")
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            
            cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]
            if not keep_audio:
                cmd.append("-an")
                
            if has_image:
                cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])
            else:
                cmd.extend(["-c", "copy"])
                
            cmd.append(str(output_path))
            
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=flags)
            if result.returncode != 0:
                err = result.stderr[:500] if result.stderr else "Unknown ffmpeg error"
                raise RuntimeError(f"ffmpeg lỗi (code {result.returncode}): {err}")

            self.log_message.emit(node_id, f"Đã ghép xong: {output_path.name}")
        finally:
            try:
                concat_file.unlink(missing_ok=True)
            except:
                pass

        return {"output": [str(output_path)]}

    def _exec_download(self, node_data: dict, config: dict, inputs: dict) -> dict[str, Any]:
        node_id = node_data.get("id", "")

        raw = inputs.get("input", inputs.get("output", []))
        if isinstance(raw, str):
            raw = [raw]
        files = [f for f in (raw or []) if Path(f).exists()]

        dest_dir = Path(config.get("output_dir", str(Path.home() / "Downloads" / "workflow_output")))
        dest_dir.mkdir(parents=True, exist_ok=True)

        quality = config.get("quality", "Gốc")
        
        # Map quality to target height
        target_heights = {"1080p": 1080, "2K": 1440, "4K": 2160}
        target_height = target_heights.get(quality, 0)
        
        copied: list[str] = []
        
        for i, fp in enumerate(files):
            if self._stop_flag:
                break
            self._check_pause()
            
            src = Path(fp)
            dst = dest_dir / src.name
            # Avoid overwriting by appending a counter
            if dst.exists():
                stem = dst.stem
                suffix = dst.suffix
                counter = 1
                while dst.exists():
                    dst = dest_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            is_image = src.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")
            
            if target_height > 0 and is_image:
                # Real upscale with PIL
                try:
                    from PIL import Image, ImageFilter
                    self.log_message.emit(node_id, f"Upscale {src.name} → {quality}...")
                    img = Image.open(fp).convert("RGB")
                    w, h = img.size
                    
                    if h < target_height:
                        scale = target_height / h
                        new_w = int(w * scale)
                        new_h = int(h * scale)
                        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                        
                        # Sharpen to compensate for upscale blur
                        radius = 1.5 if scale <= 2 else 2.0
                        percent = 100 if scale <= 2 else 150
                        img = img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=3))
                        
                        self.log_message.emit(node_id, f"Upscaled: {w}x{h} → {new_w}x{new_h}")
                    else:
                        self.log_message.emit(node_id, f"{src.name} đã đủ hoặc lớn hơn {quality}, giữ nguyên.")
                    
                    # Save with high quality
                    out_suffix = dst.suffix.lower()
                    if out_suffix in (".jpg", ".jpeg"):
                        img.save(str(dst), quality=95)
                    elif out_suffix == ".webp":
                        img.save(str(dst), quality=95)
                    else:
                        # Default to PNG for lossless
                        if out_suffix != ".png":
                            dst = dst.with_suffix(".png")
                        img.save(str(dst))
                    
                    copied.append(str(dst))
                except Exception as e:
                    self.log_message.emit(node_id, f"Upscale lỗi {src.name}: {e}, sao chép gốc.")
                    shutil.copy2(fp, dst)
                    copied.append(str(dst))
            else:
                # No upscale needed or not an image - just copy
                if target_height > 0 and not is_image:
                    self.log_message.emit(node_id, f"Sao chép {src.name} (video không hỗ trợ upscale offline).")
                else:
                    self.log_message.emit(node_id, f"Sao chép {src.name}...")
                shutil.copy2(fp, dst)
                copied.append(str(dst))
            
            self.node_progress.emit(node_id, i + 1, len(files))
        
        self.log_message.emit(node_id, f"Đã tải xuống {len(copied)} file ({quality}).")
        return {"output": copied}

    def _exec_delay(self, node_data: dict, config: dict, inputs: dict) -> dict[str, Any]:
        node_id = node_data.get("id", "")
        seconds = float(config.get("seconds", 1))
        total_ms = int(seconds * 1000)
        chunk_ms = 100
        elapsed = 0

        self.log_message.emit(node_id, f"Chờ {seconds}s…")
        while elapsed < total_ms:
            if self._stop_flag:
                break
            self._check_pause()
            QThread.msleep(chunk_ms)
            elapsed += chunk_ms
            self.node_progress.emit(node_id, min(elapsed, total_ms), total_ms)

        # Pass through any input data
        return {"output": inputs.get("input", inputs.get("output"))}

    def _exec_preview(self, node_data: dict, config: dict, inputs: dict) -> dict[str, Any]:
        node_id = node_data.get("id", "")

        raw = inputs.get("input", inputs.get("output", []))
        if isinstance(raw, str):
            raw = [raw]
        files = [f for f in (raw or []) if isinstance(f, str)]

        self.log_message.emit(node_id, f"Xem trước {len(files)} file.")
        return {"output": files, "preview_files": files}

    # -- Dispatcher -------------------------------------------------------

    _EXECUTORS: dict[str, str] = {
        "text_prompt": "_exec_text_prompt",
        "upload_image": "_exec_upload_image",
        "upload_video": "_exec_upload_video",
        "generate_image": "_exec_generate_image",
        "generate_video": "_exec_generate_video",
        "merge_video": "_exec_merge_video",
        "download": "_exec_download",
        "delay": "_exec_delay",
        "preview": "_exec_preview",
    }

    def _execute_node(self, node_data: dict, config: dict, inputs: dict) -> dict[str, Any]:
        node_type = node_data.get("node_type") or node_data.get("type", "")
        method_name = self._EXECUTORS.get(node_type)
        if method_name is None:
            raise RuntimeError(f"Loại node không được hỗ trợ: {node_type}")
        method = getattr(self, method_name)
        return method(node_data, config, inputs)

    # -- Main run loop ----------------------------------------------------

    def run(self) -> None:  # noqa: D401 – QThread override
        success = True
        nodes_by_id: dict[str, dict] = {}
        for n in self._workflow_data.get("nodes", []):
            nodes_by_id[n["id"]] = n

        try:
            for node_id in self._plan:
                if self._stop_flag:
                    self.log_message.emit(node_id, "Đã dừng thực thi.")
                    success = False
                    break

                self._check_pause()

                node_data = nodes_by_id.get(node_id)
                if node_data is None:
                    self.log_message.emit(node_id, f"Không tìm thấy node {node_id}.")
                    continue

                config = self._node_configs.get(node_id, {})
                inputs = self._gather_inputs(node_id)

                self.node_started.emit(node_id)
                self.log_message.emit(node_id, f"▶ Bắt đầu: {node_data.get('title', node_id)}")

                try:
                    result = self._execute_node(node_data, config, inputs)
                    self._data_store[node_id] = result
                    self.node_finished.emit(node_id, "success")
                    self.log_message.emit(node_id, f"✓ Hoàn thành: {node_data.get('label', node_id)}")
                except Exception as exc:
                    log.error("Node %s execution error: %s", node_id, exc)
                    self._data_store[node_id] = {"error": str(exc)}
                    self.node_finished.emit(node_id, "error")
                    self.log_message.emit(node_id, f"✗ Lỗi: {exc}")
                    success = False
                    # Continue with remaining nodes? Stop on first error.
                    if config.get("stop_on_error", True):
                        break

        except Exception as exc:
            log.error("Execution thread fatal error: %s", exc)
            success = False
        finally:
            self.execution_finished.emit(success)


# ---------------------------------------------------------------------------
# Topological Sort
# ---------------------------------------------------------------------------

def _topological_sort(nodes: list[dict], connections: list[dict]) -> list[str]:
    """Return node ids in a valid execution order (Kahn's algorithm).

    Raises ``RuntimeError`` if the graph contains a cycle.
    """
    node_ids = [n["id"] for n in nodes]
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}

    for conn in connections:
        src = conn.get("source_node", "")
        tgt = conn.get("target_node", "")
        if src in adjacency and tgt in in_degree:
            adjacency[src].append(tgt)
            in_degree[tgt] += 1

    queue: list[str] = [nid for nid, deg in in_degree.items() if deg == 0]
    order: list[str] = []

    while queue:
        # Stable sort: pick alphabetically first among zero-degree nodes
        queue.sort()
        nid = queue.pop(0)
        order.append(nid)
        for neighbor in adjacency[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(node_ids):
        raise RuntimeError("Workflow chứa vòng lặp (cycle) – không thể thực thi.")

    return order


def _upstream_ids(start_id: str, connections: list[dict]) -> set[str]:
    """Return *start_id* and all nodes required upstream from it."""
    adjacency: dict[str, list[str]] = {}
    for conn in connections:
        src = conn.get("source_node", "")
        tgt = conn.get("target_node", "")
        adjacency.setdefault(tgt, []).append(src)

    visited: set[str] = set()
    stack = [start_id]
    while stack:
        nid = stack.pop()
        if nid in visited:
            continue
        visited.add(nid)
        for parent in adjacency.get(nid, []):
            stack.append(parent)
    return visited


def _downstream_ids(start_id: str, connections: list[dict]) -> set[str]:
    """Return *start_id* and all nodes reachable downstream from it."""
    adjacency: dict[str, list[str]] = {}
    for conn in connections:
        src = conn.get("source_node", "")
        tgt = conn.get("target_node", "")
        adjacency.setdefault(src, []).append(tgt)

    visited: set[str] = set()
    stack = [start_id]
    while stack:
        nid = stack.pop()
        if nid in visited:
            continue
        visited.add(nid)
        for child in adjacency.get(nid, []):
            stack.append(child)
    return visited


# ---------------------------------------------------------------------------
# Workflow Executor  (QObject wrapper)
# ---------------------------------------------------------------------------

class WorkflowExecutor(QObject):
    """High-level executor exposed to the UI.

    Signals mirror those of :class:`ExecutionThread` and are forwarded so the
    UI can connect to a single stable object.
    """

    node_started = Signal(str)
    node_finished = Signal(str, str)
    node_progress = Signal(str, int, int)
    execution_finished = Signal(bool)
    log_message = Signal(str, str)
    task_requested = Signal(int)
    node_output_updated = Signal(str, dict)

    def __init__(self, main_win=None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._main_win = main_win
        self._thread: ExecutionThread | None = None
        self._data_store: dict[str, dict[str, Any]] = {}

    # -- Properties -------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    @property
    def data_store(self) -> dict[str, dict[str, Any]]:
        return self._data_store

    # -- Public API -------------------------------------------------------

    def run_all(self, workflow_data: dict, node_configs: dict) -> None:
        """Execute the entire workflow in topological order."""
        nodes = workflow_data.get("nodes", [])
        connections = workflow_data.get("connections", [])
        plan = _topological_sort(nodes, connections)
        self._start_execution(plan, workflow_data, node_configs, connections)

    def run_node(self, node_id: str, workflow_data: dict, node_configs: dict) -> None:
        """Execute a single node (with its upstream data already in the store)."""
        self._start_execution([node_id], workflow_data, node_configs, workflow_data.get("connections", []))

    def run_up_to_node(self, node_id: str, workflow_data: dict, node_configs: dict) -> None:
        """Execute *node_id* and all upstream dependencies."""
        nodes = workflow_data.get("nodes", [])
        connections = workflow_data.get("connections", [])
        full_order = _topological_sort(nodes, connections)
        target_ids = _upstream_ids(node_id, connections)
        plan = [nid for nid in full_order if nid in target_ids]
        self._start_execution(plan, workflow_data, node_configs, connections)

    def run_chain(self, node_id: str, workflow_data: dict, node_configs: dict) -> None:
        """Execute *node_id* and all downstream dependents."""
        nodes = workflow_data.get("nodes", [])
        connections = workflow_data.get("connections", [])
        full_order = _topological_sort(nodes, connections)
        target_ids = _downstream_ids(node_id, connections)
        plan = [nid for nid in full_order if nid in target_ids]
        self._start_execution(plan, workflow_data, node_configs, connections)

    def pause(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.request_pause()
            log.info("Workflow paused.")

    def resume(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.request_resume()
            log.info("Workflow resumed.")

    def stop(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.request_stop()
            log.info("Workflow stop requested.")

    def get_node_output(self, node_id: str) -> dict[str, Any] | None:
        """Retrieve the data produced by a completed node."""
        return self._data_store.get(node_id)

    # -- Internal ---------------------------------------------------------

    def _start_execution(
        self,
        plan: list[str],
        workflow_data: dict,
        node_configs: dict,
        connections: list[dict],
    ) -> None:
        if self.is_running:
            log.warning("Executor: execution already in progress.")
            return

        self._data_store.clear()

        self._thread = ExecutionThread(
            plan=plan,
            workflow_data=workflow_data,
            node_configs=node_configs,
            connections=connections,
            data_store=self._data_store,
            main_win=self._main_win,
            parent=self,
        )
        # Forward signals
        self._thread.node_started.connect(self.node_started)
        self._thread.node_finished.connect(self.node_finished)
        self._thread.node_progress.connect(self.node_progress)
        self._thread.execution_finished.connect(self._on_finished)
        self._thread.log_message.connect(self.log_message)
        self._thread.task_requested.connect(self.task_requested)
        self._thread.node_output_updated.connect(self.node_output_updated)
        self._thread.start()

    def _on_finished(self, success: bool) -> None:
        self.execution_finished.emit(success)
        log.info("Workflow execution finished (success=%s).", success)
