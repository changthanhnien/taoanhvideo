"""Cleanup orphan browser resources."""

from __future__ import annotations

import shutil
from pathlib import Path

from utils.logger import log


def _get_log():
    return log


def _kill_orphan_chromes():
    return 0


def _remove_stale_temp_profiles(base_dir=None):
    from config.constants import BROWSER_PROFILE_DIR
    base = Path(base_dir) if base_dir else BROWSER_PROFILE_DIR
    if not base.exists():
        return 0
    removed = 0
    import time
    now = time.time()
    for pattern in ("google_*", "grok_temp_*", "navtools_*"):
        for path in base.glob(pattern):
            if path.is_dir():
                try:
                    # Avoid deleting profiles currently in use (less than 3 hours old)
                    if now - path.stat().st_mtime > 10800:
                        shutil.rmtree(path, ignore_errors=True)
                        removed += 1
                except Exception:
                    pass
    return removed


def cleanup_orphan_resources():
    killed = _kill_orphan_chromes()
    removed = _remove_stale_temp_profiles()
    log.info(f"cleanup orphan resources: killed={killed}, removed={removed}")
    return {"killed": killed, "removed": removed}
