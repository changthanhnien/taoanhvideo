from pathlib import Path
from PIL import Image

from services.inpaint_lama import build_rect_mask, download_model, inpaint_image_crop, inpaint_video, model_exists

class LamaEngine:
    def __init__(self):
        self.padding = 32

    def check_and_download_model(self, progress_cb=None):
        if not model_exists():
            if progress_cb:
                progress_cb(0, 100, "Downloading LaMa model...")
            def _cb(done, total):
                if progress_cb:
                    progress_cb(done, total, "Downloading LaMa model...")
            ok = download_model(_cb)
            if not ok:
                raise RuntimeError("Cannot download LaMa model")

    def process_image(self, input_path: Path, output_path: Path, rect: tuple, params: dict):
        self.check_and_download_model()
        img = Image.open(input_path)
        mask = build_rect_mask(img.size, rect)
        result = inpaint_image_crop(img, mask, rect, padding=self.padding)
        result.save(output_path)

    def process_video(self, input_path: Path, output_path: Path, rect: tuple, params: dict, progress_cb=None):
        self.check_and_download_model()
        def _cb(done, total):
            if progress_cb:
                progress_cb(done, total, "Processing video with LaMa...")
        ok = inpaint_video(
            input_path,
            output_path,
            rect,
            padding=self.padding,
            progress_cb=_cb,
        )
        if not ok:
            raise RuntimeError("Video processing failed with LaMa")
