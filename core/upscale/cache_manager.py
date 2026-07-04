import os
import json
import zlib
from pathlib import Path
from core.upscale.logger import upscale_log

from config.constants import DATA_DIR
CACHE_FILE = DATA_DIR / "cache" / "upscale_analysis.json"

class CacheManager:
    def __init__(self):
        self.cache = {}
        self._load_cache()

    def _load_cache(self):
        try:
            if CACHE_FILE.exists():
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
        except Exception as e:
            upscale_log.log.warning(f"Failed to load cache: {e}")

    def _save_cache(self):
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            upscale_log.log.warning(f"Failed to save cache: {e}")

    def _compute_key(self, image_path):
        """Compute a fast composite key based on crc32, size, and mtime."""
        st = os.stat(image_path)
        size = st.st_size
        mtime = st.st_mtime
        
        # Read the first 1MB and last 1MB to approximate full file crc32 super fast,
        # or just read full if it's small.
        # Actually, since it's an image, reading the whole file into crc32 takes ~5ms for 5MB.
        with open(image_path, "rb") as f:
            data = f.read()
        crc = zlib.crc32(data) & 0xFFFFFFFF
        
        return f"{crc}_{size}_{mtime}"

    def get_analysis(self, image_path):
        upscale_log.start_timer("cache_read")
        try:
            key = self._compute_key(image_path)
            if key in self.cache:
                upscale_log.end_timer("cache_read")
                return self.cache[key]
        except Exception as e:
            upscale_log.log.warning(f"Cache read error: {e}")
        upscale_log.end_timer("cache_read")
        return None

    def save_analysis(self, image_path, analysis_data):
        try:
            key = self._compute_key(image_path)
            self.cache[key] = analysis_data
            self._save_cache()
        except Exception as e:
            upscale_log.log.warning(f"Cache write error: {e}")
