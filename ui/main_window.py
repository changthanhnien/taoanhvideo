"""VidGen AI - Main Window with TaskManager integration."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QWidget, QVBoxLayout

from config.constants import APP_NAME, APP_VERSION, ASSETS_DIR, TaskMode, TaskStatus
from config.settings import Settings
from models.database import Database
from models.task import TaskItem, VideoTask
from utils.file_utils import generate_task_name
from utils.logger import log
from ui.widgets.command_palette import CommandPalette


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, db: Database, settings=None, browser_manager=None, parent=None):
        super().__init__(parent)
        self.db = db
        self._db = db
        self.browser_manager = browser_manager
        self._browser_mgr = browser_manager
        self.settings = settings or Settings(db)
        self._settings = self.settings
        self.task_manager = None
        self._task_manager = None
        self._open_settings_dialog = None
        self._content_pages = []
        self.pages = {}
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1200, 720)
        self.resize(1440, 820)
        for candidate in (
            Path(ASSETS_DIR) / "assets" / "navtools.ico",
            Path(ASSETS_DIR) / "navtools.ico",
        ):
            if candidate.exists():
                self.setWindowIcon(QIcon(str(candidate)))
                break
        self._init_ui()
        self._connect_signals()
        self._apply_theme()
        self._check_accounts_on_startup()
        
        # Preload heavy machine learning modules in a background thread to make tab switching instant
        import threading
        def preload_heavy_modules():
            try:
                log.info("[MainWindow] Preloading heavy modules (PyTorch/diffusers) in background thread...")
                import torch
                import torchvision
                from services.flow_model_provider import model_provider
                log.info("[MainWindow] Heavy modules preloaded successfully.")
            except Exception as e:
                log.warning(f"[MainWindow] Preload failed: {e}")
        threading.Thread(target=preload_heavy_modules, daemon=True).start()

    def _init_ui(self):
        central = QWidget()
        central.setObjectName("main_window")
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        try:
            from ui.sidebar import Sidebar
            self.sidebar = Sidebar()
            main_layout.addWidget(self.sidebar)
        except Exception as e:
            log.warning(f"Could not create sidebar: {e}")
            self.sidebar = None

        workspace_container = QWidget()
        workspace_layout = QVBoxLayout(workspace_container)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        from ui.widgets.header import Header
        self.header = Header(theme=self.settings.get("theme", "dark"))
        self.header.open_palette.connect(self._open_command_palette)
        self.header.theme_toggled.connect(self._toggle_theme)
        workspace_layout.addWidget(self.header)

        self.stack = QStackedWidget()
        workspace_layout.addWidget(self.stack, 1)
        
        self.log_dock = QWidget()
        self.log_dock.setFixedHeight(250)
        self.log_dock.setVisible(False)
        self.log_dock_layout = QVBoxLayout(self.log_dock)
        self.log_dock_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.addWidget(self.log_dock, 0)

        main_layout.addWidget(workspace_container, 1)
        self.setCentralWidget(central)

        from ui.pages.content_page import ContentPage
        from ui.widgets.lazy_page import LazyPage

        modes = [
            TaskMode.IMAGE,
            TaskMode.CHAR_IMAGE,
            TaskMode.CHAR_VIDEO,
            TaskMode.VIDEO,
            TaskMode.FRAME_VIDEO,
            TaskMode.GROK_IMAGE,
            TaskMode.GROK_VIDEO,
        ]
        mode_keys = ["image", "char_image", "char_video", "video", "frame_video", "grok_image", "grok_video"]
        self._content_pages = []
        for key, mode in zip(mode_keys, modes):
            page = ContentPage(mode=mode, db=self.db)
            page.start_task.connect(self._on_start_task)
            page.open_settings.connect(self._open_settings)
            self._content_pages.append(page)
            self.pages[key] = page
            self.stack.addWidget(page)

        long_page = self._build_long_video_page()
        self.long_video_page = long_page
        self.pages["long_video"] = long_page
        self.stack.insertWidget(5, long_page)

        lazy_builders = [
            ("workflow_studio", self._build_workflow_studio_page, "WorkflowStudioPage"),
            ("history", self._build_history_page, "HistoryPage"),
        ]
        for key, builder, name in lazy_builders:
            lazy = LazyPage(builder, name=name)
            setattr(self, f"{key}_page_lazy", lazy)
            self.pages[key] = lazy
            self.stack.addWidget(lazy)
            
        # Preload Watermark page to avoid delay/white flash
        self.watermark_page = self._build_watermark_page()
        self.pages["watermark"] = self.watermark_page
        self.stack.addWidget(self.watermark_page)
        
        # Log Page goes to bottom dock
        self.log_page_lazy = LazyPage(self._build_log_page, name="LogViewerPage")
        self.pages["log"] = self.log_page_lazy
        self.log_dock_layout.addWidget(self.log_page_lazy)

        state = self.settings.get("splitter_state")
        if state:
            from PySide6.QtCore import QByteArray
            try:
                state_bytes = QByteArray.fromHex(state.encode("utf-8"))
                for page in self._content_pages:
                    if hasattr(page, "splitter"):
                        page.splitter.restoreState(state_bytes)
            except Exception as e:
                log.error(f"Could not restore splitter state: {e}")

        if self.sidebar:
            self.sidebar._on_item_clicked("image")
        else:
            self.stack.setCurrentIndex(0)

    def _safe_page(self, module_name, class_name):
        try:
            module = __import__(module_name, fromlist=[class_name])
            cls = getattr(module, class_name)
            attempts = (
                lambda: cls(db=self.db, browser_mgr=self.browser_manager, settings=self.settings),
                lambda: cls(db=self.db, browser_manager=self.browser_manager, settings=self.settings),
                lambda: cls(db=self.db, settings=self.settings),
                lambda: cls(self.db, self.browser_manager, self.settings),
                lambda: cls(self.db, self.settings),
                lambda: cls(self.db),
                lambda: cls(),
            )
            for attempt in attempts:
                try:
                    return attempt()
                except TypeError:
                    continue
            return cls()
        except Exception as e:
            log.warning(f"Could not load {class_name}: {e}")
            return QWidget()

    def _open_command_palette(self):
        palette = CommandPalette(self, theme=self.settings.get("theme", "dark"))
        palette.command_selected.connect(self._on_page_changed)
        palette.exec()

    def _connect_signals(self):
        QShortcut(QKeySequence("Ctrl+K"), self, self._open_command_palette)
        
        if self.sidebar is not None:
            if hasattr(self.sidebar, "open_palette"):
                self.sidebar.open_palette.connect(self._open_command_palette)
            signal = getattr(self.sidebar, "page_changed", None) or getattr(self.sidebar, "navigation_changed", None)
            if signal is not None:
                try:
                    signal.connect(self._on_page_changed)
                except Exception:
                    pass
        for page in self.pages.values():
            if hasattr(page, "page_loaded"):
                page.page_loaded.connect(self._connect_page_signals)
            else:
                self._connect_page_signals(page)

    def _connect_page_signals(self, page):
        for name, handler in (
            ("start_task", self._on_start_task),
            ("pause_task", self._on_pause_task),
            ("stop_task", self._on_stop_task),
            ("new_task", self._on_new_task),
            ("retry_item", self._on_retry_item),
            ("retry_all", self._on_retry_all),
            ("concat_requested", self._on_concat),
            ("youtube_start_video", self._on_youtube_start_video),
            ("youtube_cancel", self._on_youtube_cancel),
            ("youtube_retry_row", self._on_youtube_retry_row),
            ("youtube_auto_start", self._on_youtube_auto_start),
            ("youtube_send", self._on_youtube_send),
            ("script_start_video", self._on_script_start_video),
            ("script_cancel", self._on_script_cancel),
            ("script_retry_row", self._on_script_retry_row),
            ("script_send_single_prompt", self._on_script_send_single_prompt),
            ("script_cancel_single_prompt", self._on_script_cancel_single_prompt),
            ("upscale_image", self._on_upscale_image),
            ("sync_requested", self._on_sync_requested),
            ("test_requested", self._on_test_requested),
            ("test_video_requested", self._on_test_video_requested),
        ):
            sig = getattr(page, name, None)
            if sig is not None:
                try:
                    sig.connect(handler)
                except Exception:
                    pass

    def _get_task_manager(self):
        if self.task_manager is None:
            if not hasattr(self, "browser_manager") or self.browser_manager is None:
                try:
                    from automation.browser_manager import BrowserManager
                    self.browser_manager = BrowserManager()
                except ImportError as e:
                    log.warning(f"Failed to import BrowserManager: {e}")
                    self.browser_manager = None
            try:
                from workers.task_manager import TaskManager
                self.task_manager = TaskManager(self.db, self.browser_manager)
            except TypeError:
                self.task_manager = TaskManager(self.db)
            except Exception as e:
                log.warning(f"TaskManager unavailable: {e}")
                self.task_manager = None
        return self.task_manager

    def _on_account_disabled(self, account_id, email, reason):
        QMessageBox.warning(self, "Account disabled", f"{email}: {reason}")
        self._refresh_account_headers()

    def _on_page_changed(self, page):
        # Auto-close any active HistoryPickerDialog when changing pages
        try:
            from PySide6.QtWidgets import QApplication
            from ui.workflow.history_picker_dialog import HistoryPickerDialog
            for w in QApplication.topLevelWidgets():
                if isinstance(w, HistoryPickerDialog):
                    w.reject()
        except Exception:
            pass

        # Stop any active video playbacks across all pages when switching
        for page_widget in self.pages.values():
            real_widget = page_widget.real if hasattr(page_widget, "real") else page_widget
            if real_widget is None:
                continue
            if hasattr(real_widget, "picker") and real_widget.picker:
                if hasattr(real_widget.picker, "_reset_preview"):
                    real_widget.picker._reset_preview()
            elif hasattr(real_widget, "_reset_preview"):
                real_widget._reset_preview()
            elif hasattr(real_widget, "player") and real_widget.player:
                try:
                    real_widget.player.stop()
                except Exception:
                    pass



        if page == "settings":
            self._open_settings()
            return

        if isinstance(page, int):
            index = page
        else:
            widget = self.pages.get(page)
            if not widget:
                return
            index = self.stack.indexOf(widget)
            
        if index < 0 or index >= self.stack.count():
            return
            
        widget = self.stack.widget(index)
        if hasattr(widget, "ensure_loaded") and not widget.is_loaded:
            widget.ensure_loaded()
            
        if page in ("log", "history"):
            if hasattr(widget, "widget") and hasattr(widget.widget, "refresh"):
                widget.widget.refresh()
            elif hasattr(widget, "refresh"):
                widget.refresh()
                
        # Sync splitter sizes between ContentPages to avoid collapsed state on hidden layouts
        try:
            from ui.pages.content_page import ContentPage
            active_page = self.stack.currentWidget()
            if isinstance(active_page, ContentPage) and hasattr(active_page, "splitter"):
                sizes = active_page.splitter.sizes()
                if len(sizes) == 2 and sizes[0] > 0:
                    next_page = self.stack.widget(index)
                    if isinstance(next_page, ContentPage) and hasattr(next_page, "splitter"):
                        next_page.splitter.setSizes(sizes)
        except Exception as e:
            log.warning(f"Could not sync splitter sizes: {e}")
                    
        self.stack.setCurrentIndex(index)

    def _build_long_video_page(self):
        try:
            from ui.pages.long_video_page import LongVideoPage

            try:
                return LongVideoPage(db=self.db, browser_mgr=self.browser_manager, settings=self.settings)
            except TypeError:
                try:
                    return LongVideoPage(self.db, self.browser_manager, self.settings)
                except TypeError:
                    return LongVideoPage()
        except Exception as e:
            log.warning(f"Could not load LongVideoPage: {e}")
            return QWidget()

    def _build_youtube_page(self):
        return self._safe_page("ui.pages.youtube_prompt_page", "YouTubePromptPage")

    def _build_script_page(self):
        return self._safe_page("ui.pages.script_to_prompt_page", "ScriptToPromptPage")

    def _build_bg_remove_page(self):
        return self._safe_page("ui.pages.bg_remove_page", "BgRemovePage")

    def _build_watermark_page(self):
        return self._safe_page("ui.pages.watermark_remove_page", "WatermarkRemovePage")

    def _build_img_to_prompt_page(self):
        return self._safe_page("ui.pages.image_to_prompt_page", "ImageToPromptPage")

    def _build_upscale_page(self):
        return self._safe_page("ui.pages.upscale_page", "UpscalePage")

    def _build_audio_merge_page(self):
        return self._safe_page("ui.pages.audio_merge_page", "AudioMergePage")

    def _build_subtitle_page(self):
        return self._safe_page("ui.pages.subtitle_page", "SubtitlePage")

    def _build_batch_resize_page(self):
        return self._safe_page("ui.pages.batch_resize_page", "BatchResizePage")

    def _build_workflow_studio_page(self):
        return self._safe_page("ui.workflow.workflow_page", "WorkflowStudioPage")

    def _build_history_page(self):
        return self._safe_page("ui.pages.history_page", "HistoryPage")

    def _build_log_page(self):
        page = self._safe_page("ui.pages.log_viewer", "LogViewerPage")
        self.log_page = page
        return page

    def _apply_theme(self):
        try:
            theme = str(self.settings.get("theme", "dark")).lower()
            from ui.themes.engine import compile_theme
            qss = compile_theme(theme)
            self.setStyleSheet(qss)
            if hasattr(self, 'header') and self.header:
                self.header.update_theme(theme)
            if hasattr(self, 'sidebar') and self.sidebar:
                self.sidebar.update_theme(theme)
            
            # Broadcast to all instantiated pages
            if hasattr(self, 'pages'):
                for page in self.pages.values():
                    if hasattr(page, '_instance') and page._instance:
                        if hasattr(page._instance, 'update_theme'):
                            page._instance.update_theme(theme)
                        elif hasattr(page._instance, 'result_panel'):
                            page._instance.result_panel.update_theme(theme)
                            
        except Exception as e:
            log.warning(f"Could not apply theme: {e}")

    def _toggle_theme(self):
        theme = str(self.settings.get("theme", "dark")).lower()
        new_theme = "light" if theme == "dark" else "dark"
        self.settings.set("theme", new_theme)
        self._apply_theme()

    def _open_settings(self):
        try:
            from ui.dialogs.settings_dialog import SettingsDialog

            dlg = SettingsDialog(self.db, self.settings, self)
            dlg.exec()
            self._refresh_account_headers()
        except Exception as e:
            QMessageBox.warning(self, "Settings", str(e))

    def _check_accounts_on_startup(self):
        try:
            accounts = self.db.get_accounts(enabled_only=True)
            if not accounts:
                log.warning("No enabled accounts configured")
        except Exception:
            pass

    def _refresh_account_headers(self):
        for page in self.pages.values():
            fn = getattr(page, "refresh_accounts", None) or getattr(page, "refresh_account_headers", None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass

    def _on_start_task(self, task):
        if isinstance(task, dict):
            import json
            import os
            from models.task import VideoTask, TaskItem
            mode = task.get("mode", TaskMode.VIDEO)
            name = generate_task_name(mode)
            prompts = task.get("prompts", [])
            
            if not prompts and task.get("input_folder"):
                input_folder = task.get("input_folder")
                if os.path.isdir(input_folder):
                    files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.mp4'))]
                    prompts = [{"text": f} for f in files]
                elif os.path.isfile(input_folder):
                    prompts = [{"text": os.path.basename(input_folder)}]
            
            if not prompts and (task.get("start_frame") or task.get("end_frame")):
                prompts = [{"text": "Video từ ảnh"}]
            
            # User expects 'Đồng thời' (parallel_per_account) to also mean 'Số lượng kết quả' (Quantity)
            parallel_per_account = task.get("parallel_per_account", 1)
            if parallel_per_account > 1 and prompts:
                new_prompts = []
                for p in prompts:
                    new_prompts.extend([p] * parallel_per_account)
                prompts = new_prompts
            
            if not prompts:
                QMessageBox.warning(self, "Lỗi", "Không có prompt hoặc dữ liệu đầu vào!")
                return None

            project = self.db.get_or_create_project("Default")
            char_images = task.get("character_images", {})
            char_images_list = list(char_images.values()) if isinstance(char_images, dict) else char_images

            config_json = json.dumps({
                "creation_mode": task.get("creation_mode", ""),
                "duration": task.get("duration", "8s"),
                "quality_key": task.get("quality_key", ""),
                "uploaded_images": task.get("uploaded_images", []),
            })

            quality_model = task.get("quality", "Veo 3.1 - Fast")
            image_model = task.get("image_model", "Nano Banana 2")
            if mode == TaskMode.GROK_IMAGE:
                image_model = f"Grok ({task.get('grok_mode', 'Tốc độ')})"
            elif mode == TaskMode.GROK_VIDEO:
                quality_model = f"Grok ({task.get('quality', '720p')})"

            task_concurrent = task.get("concurrent", 1)
            if mode in (TaskMode.GROK_IMAGE, TaskMode.GROK_VIDEO):
                task_concurrent = len(prompts)

            vtask = VideoTask(
                project_id=project.id,
                name=name,
                mode=mode,
                quality=quality_model,
                image_model=image_model,
                aspect_ratio=task.get("aspect_ratio", "16:9"),
                concurrent=task_concurrent,
                parallel_per_account=task.get("parallel_per_account", 1),
                character_images=char_images_list,
                input_folder=task.get("input_folder", ""),
                output_folder=task.get("output_folder", ""),
                delay=task.get("delay", 0),
                total_count=len(prompts),
                config=config_json,
            )
            vtask = self.db.create_task(vtask)

            items = []
            per_row = task.get("per_row_character_images", {})
            for i, p in enumerate(prompts):
                p_text = p.get("text", "") if isinstance(p, dict) else str(p)
                ref_img = None
                if i in per_row and per_row[i]:
                    ref_img = json.dumps(per_row[i])
                item = TaskItem(
                    task_id=vtask.id,
                    prompt=p_text,
                    reference_image=ref_img,
                    start_frame=task.get("start_frame"),
                    end_frame=task.get("end_frame")
                )
                items.append(item)

            self.db.add_task_items_bulk(items)
            vtask.items = items
            task = vtask

        manager = self._get_task_manager()
        if manager and hasattr(manager, "start_task"):
            # Auto-cancel any existing workers for this mode to prevent ghost tasks
            if hasattr(manager, "workers"):
                for t_id, w in list(manager.workers.items()):
                    if hasattr(w, "task") and getattr(w.task, "mode", None) == mode:
                        try:
                            w.cancel()
                        except:
                            pass

            worker = manager.start_task(task)
            
            page = self.stack.currentWidget()
            if hasattr(page, "widget"):
                page = page.widget
                
            if hasattr(page, "task_table"):
                if getattr(task, "mode", "") in ("image", "char_image", "grok_image"):
                    task_model = getattr(task, "image_model", "") or getattr(task, "model", "") or ""
                else:
                    task_model = getattr(task, "quality", "") or getattr(task, "model", "") or ""
                task_ratio = getattr(task, "aspect_ratio", "") or ""
                page.task_table.set_items(task.items, task_model=task_model, task_ratio=task_ratio)
                
                # Map item.id to row
                id_to_row = {item.id: row for row, item in enumerate(task.items)}
                
                def on_status_changed(iid, st):
                    if iid in id_to_row:
                        page.task_table.update_item_status(id_to_row[iid], st)
                def on_completed(iid, out):
                    if iid in id_to_row:
                        page.task_table.update_item_output(id_to_row[iid], out)
                        page.task_table.update_item_status(id_to_row[iid], "COMPLETED", out)
                def on_error(iid, err):
                    if iid in id_to_row:
                        # Only call update_item_error - it handles status + actions internally
                        page.task_table.update_item_error(id_to_row[iid], err)
                
                worker.signals.item_status_changed.connect(on_status_changed)
                worker.signals.item_completed.connect(on_completed)
                worker.signals.item_error.connect(on_error)
                
                # Switch to History tab if it's there
                if hasattr(page, "result_panel") and hasattr(page.result_panel, "tabs"):
                    page.result_panel.tabs.setCurrentIndex(1)
            
            try:
                from ui.widgets.toast import ToastManager
                ToastManager.success(self, f"Đã bắt đầu {task.total_count} tiến trình!")
            except Exception:
                pass
            return worker
        return None

    def _on_pause_task(self, task_id):
        manager = self._get_task_manager()
        if manager and hasattr(manager, "pause_task"):
            return manager.pause_task(task_id)

    def _on_stop_task(self, task_id):
        manager = self._get_task_manager()
        if manager and hasattr(manager, "stop_task"):
            return manager.stop_task(task_id)

    def _on_youtube_start_video(self, payload):
        return self._do_youtube_start(payload, self.pages.get("youtube"))

    def _do_youtube_start(self, payload, page=None):
        try:
            from services.youtube_analyzer import YouTubeAnalyzer

            analyzer = YouTubeAnalyzer()
            if page is not None:
                setattr(page, "_youtube_analyzer", analyzer)
            return analyzer
        except Exception as e:
            QMessageBox.warning(self, "YouTube analyzer", str(e))
            return None

    def _on_youtube_cancel(self):
        page = self.pages.get("youtube")
        analyzer = getattr(page, "_youtube_analyzer", None)
        if analyzer and hasattr(analyzer, "cancel"):
            analyzer.cancel()

    def _on_youtube_retry_row(self, row):
        page = self.pages.get("youtube")
        fn = getattr(page, "retry_row", None)
        if callable(fn):
            fn(row)

    def _on_youtube_auto_start(self, *args):
        return self._on_youtube_start_video(args[0] if args else {})

    def _on_youtube_send(self, payload):
        return self._on_start_task(payload)

    def _on_script_start_video(self, payload):
        return self._do_script_start(payload, self.pages.get("script"))

    def _do_script_start(self, payload, page=None):
        try:
            from services.script_analyzer import ScriptAnalyzer

            analyzer = ScriptAnalyzer()
            if page is not None:
                setattr(page, "_script_analyzer", analyzer)
            return analyzer
        except Exception as e:
            QMessageBox.warning(self, "Script analyzer", str(e))
            return None

    def _on_script_cancel(self):
        page = self.pages.get("script")
        analyzer = getattr(page, "_script_analyzer", None)
        if analyzer and hasattr(analyzer, "cancel"):
            analyzer.cancel()

    def _on_script_retry_row(self, row):
        page = self.pages.get("script")
        fn = getattr(page, "retry_row", None)
        if callable(fn):
            fn(row)

    def _on_script_send_single_prompt(self, prompt):
        return self._on_start_task({"prompt": prompt})

    def _on_script_cancel_single_prompt(self, *args):
        return self._on_script_cancel()

    def _on_upscale_image(self, payload):
        page = self.pages.get("upscale")
        fn = getattr(page, "start_upscale", None)
        if callable(fn):
            fn(payload)

    def _stop_spinner(self, page=None):
        fn = getattr(page, "stop_spinner", None) if page else None
        if callable(fn):
            fn()

    def _on_done(self, *args):
        log.info(f"Operation done: {args}")

    def _on_err(self, message):
        QMessageBox.warning(self, "Error", str(message))

    def _on_new_task(self, task):
        self._apply_new_task_cooldown()
        return self._on_start_task(task)

    def _apply_new_task_cooldown(self):
        return None

    def _on_resume_task(self, task_id):
        manager = self._get_task_manager()
        if manager and hasattr(manager, "resume_task"):
            return manager.resume_task(task_id)

    def _reattach_per_item_char_images(self, task):
        return task

    def _on_retry_item(self, item_id):
        manager = self._get_task_manager()
        if manager and hasattr(manager, "retry_item"):
            worker = manager.retry_item(item_id)
            if worker:
                worker.signals.task_started.connect(self._on_task_started)
                worker.signals.task_completed.connect(self._on_task_completed)
                worker.signals.task_error.connect(self._on_task_error)
                worker.signals.task_progress.connect(self._on_task_progress)
                worker.signals.item_status_changed.connect(self._on_item_status_changed)
                worker.signals.item_completed.connect(self._on_item_completed)
                worker.signals.item_error.connect(self._on_item_error)
            return worker

    def _on_retry_all(self, task_id):
        manager = self._get_task_manager()
        if manager and hasattr(manager, "retry_all"):
            return manager.retry_all(task_id)

    def _on_concat(self, payload):
        try:
            task_id = payload.get("task_id")
            if not task_id:
                return
                
            # 1. Fetch completed task item video paths
            rows = self.db.execute(
                "SELECT output_path FROM task_items WHERE task_id = ? AND status = 'COMPLETED' ORDER BY id ASC",
                (task_id,)
            ).fetchall()
            
            input_paths = []
            for r in rows:
                p = r[0]
                if p and Path(p).exists():
                    input_paths.append(p)
                    
            if not input_paths:
                QMessageBox.warning(self, "Ghép Video", "Không tìm thấy video nào đã hoàn thành để ghép!")
                return
                
            if len(input_paths) < 2:
                QMessageBox.warning(self, "Ghép Video", f"Cần ít nhất 2 video hoàn thành để thực hiện ghép nối! (Hiện tại: {len(input_paths)})")
                return
                
            # 2. Determine output path
            first_path = Path(input_paths[0])
            output_dir = first_path.parent
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"concat_{task_id}_{timestamp}.mp4"
            
            # 3. Perform concatenation
            from services.video_concat import concat_videos
            from ui.widgets.toast import ToastManager
            
            ToastManager.info(self, "Đang tiến hành ghép nối video...")
            success = concat_videos(input_paths, output_path)
            
            if success:
                ToastManager.success(self, f"Ghép nối video thành công! Lưu tại:\n{output_path.name}")
            else:
                QMessageBox.warning(self, "Ghép Video", "Quá trình ghép nối video bằng FFmpeg thất bại.")
        except Exception as e:
            QMessageBox.warning(self, "Concat", str(e))

    def _on_task_started(self, task_id):
        log.info(f"Task started: {task_id}")

    def _on_task_completed(self, task_id):
        log.info(f"Task completed: {task_id}")

    def _on_task_error(self, task_id, error):
        log.warning(f"Task error {task_id}: {error}")

    def _cleanup_script_extra_task(self, task_id):
        return None

    def _on_task_progress(self, task_id, done, total):
        page = self._find_page_by_task(task_id)
        fn = getattr(page, "update_task_progress", None) if page else None
        if callable(fn):
            fn(task_id, done, total)

    def _on_item_status_changed(self, item_id, status, output_path=None):
        page = self._get_current_content_page()
        fn = getattr(page, "update_item_status", None) if page else None
        if callable(fn):
            import inspect
            sig = inspect.signature(fn)
            if "output_path" in sig.parameters:
                fn(item_id, status, output_path=output_path)
            else:
                fn(item_id, status)

    def _on_item_completed(self, item_id, output_path):
        if self.db:
            self.db.update_item_status(item_id, "COMPLETED", output_path=output_path)
        self._on_item_status_changed(item_id, "COMPLETED", output_path=output_path)

    def _on_item_error(self, item_id, error):
        if self.db:
            self.db.update_item_status(item_id, "ERROR", error_message=str(error))
        self._on_item_status_changed(item_id, "ERROR")

    def _on_credit_updated(self, account_id, credit):
        self._refresh_account_headers()

    def _get_current_content_page(self):
        widget = self.stack.currentWidget()
        return widget

    def _find_page_by_task(self, task_id):
        for page in self.pages.values():
            if getattr(page, "task_id", None) == task_id:
                return page
        return self._get_current_content_page()

    def _on_sync_requested(self):
        accounts = self.db.get_accounts(enabled_only=True)
        if not accounts:
            QMessageBox.warning(self, "Lỗi", "Chưa có tài khoản nào được bật!")
            return
        cookie_path = accounts[0].cookie_path
            
        from services.flow_model_provider import model_provider
        import asyncio
        import threading
        
        # Disable all Sync buttons while syncing
        for page in self.pages.values():
            if hasattr(page, "config_form"):
                form = page.config_form
                if hasattr(form, "sync_model_btn"):
                    form.sync_model_btn.setText("⏳")
                if hasattr(form, "sync_video_btn"):
                    form.sync_video_btn.setText("⏳")
        
        def run_sync():
            try:
                asyncio.run(model_provider.sync_models(cookie_path))
            except Exception as e:
                log.error(f"Sync model failed: {e}")
            finally:
                from PySide6.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(self, "_refresh_model_ui", Qt.QueuedConnection)
                
        threading.Thread(target=run_sync, daemon=True).start()

    from PySide6.QtCore import Slot
    @Slot()
    def _refresh_model_ui(self):
        from services.flow_model_provider import model_provider
        img_count = len(model_provider.models.get("image_models", []))
        vid_count = len(model_provider.models.get("video_models", []))
        
        try:
            from ui.widgets.toast import ToastManager
            if img_count > 0 or vid_count > 0:
                ToastManager.success(self, f"OK! {img_count} image, {vid_count} video models")
            else:
                ToastManager.error(self, "Sync failed - no models found")
        except:
            pass
        
        for page in self.pages.values():
            if hasattr(page, "config_form"):
                form = page.config_form
                form.update_image_models()
                form.update_video_models()
                # Re-enable Sync buttons
                if hasattr(form, "sync_model_btn"):
                    form.sync_model_btn.setText("🔄")
                if hasattr(form, "sync_video_btn"):
                    form.sync_video_btn.setText("🔄")
        
        if hasattr(self, "stack"):
            widget = self.stack.currentWidget()
            if hasattr(widget, "config_form"):
                widget.config_form.update_image_models()
                widget.config_form.update_video_models()

    def _on_test_requested(self, model_name):
        self._run_benchmark("image", model_name)

    def _on_test_video_requested(self, quality_name):
        self._run_benchmark("video", quality_name)

    def _run_benchmark(self, mode, model_name):
        accounts = self.db.get_accounts(enabled_only=True)
        if not accounts:
            QMessageBox.warning(self, "Lỗi", "Chưa có tài khoản nào được bật!")
            return
        cookie_path = accounts[0].cookie_path
            
        import threading
        
        try:
            from ui.widgets.toast import ToastManager
            ToastManager.info(self, f"Đang test {model_name} qua Flow UI thật...")
        except:
            pass
            
        def _do_benchmark():
            import asyncio
            import time
            from playwright.async_api import async_playwright
            
            async def test_ui():
                from utils.platform import find_chrome
                chrome_exe = find_chrome()
                log.info(f"Benchmark: model='{model_name}' mode={mode}")
                pw = await async_playwright().start()
                try:
                    browser = await pw.chromium.launch_persistent_context(
                        user_data_dir=cookie_path,
                        headless=False,
                        executable_path=chrome_exe,
                        args=["--window-size=1280,900"]
                    )
                    page = await browser.new_page()
                    
                    # Step 1: Navigate to Flow
                    await page.goto("https://labs.google/fx/vi/tools/flow", wait_until="networkidle")
                    await asyncio.sleep(5)
                    
                    # Step 2: Click "Dự án mới"
                    new_btn = await page.query_selector('button:has-text("Dự án mới")')
                    if not new_btn:
                        new_btn = await page.query_selector('button:has-text("New project")')
                    if new_btn:
                        await new_btn.click()
                        try:
                            await page.wait_for_url("**/flow/project/**", timeout=15000)
                        except:
                            await asyncio.sleep(3)
                        await asyncio.sleep(5)
                    
                    # Step 3: Type prompt
                    prompt_input = None
                    for sel in ['textarea', 'div[role="textbox"]', 'div[contenteditable="true"]']:
                        els = await page.query_selector_all(sel)
                        for el in els:
                            if await el.is_visible():
                                prompt_input = el
                                break
                        if prompt_input:
                            break
                    if not prompt_input:
                        await page.mouse.click(500, 580)
                        await asyncio.sleep(1)
                        for sel in ['textarea', 'div[role="textbox"]', 'div[contenteditable="true"]']:
                            els = await page.query_selector_all(sel)
                            for el in els:
                                if await el.is_visible():
                                    prompt_input = el
                                    break
                            if prompt_input:
                                break
                    
                    test_prompt = "A simple red apple"
                    if prompt_input:
                        await prompt_input.click()
                        await asyncio.sleep(0.3)
                        await page.keyboard.press("Control+a")
                        await page.keyboard.press("Delete")
                        await page.keyboard.type(test_prompt, delay=20)
                        await asyncio.sleep(1)
                    else:
                        await page.mouse.click(500, 600)
                        await asyncio.sleep(0.5)
                        await page.keyboard.type(test_prompt, delay=20)
                        await asyncio.sleep(1)
                    
                    # Step 4: Click Generate (arrow_forward button)
                    start_time = time.time()
                    generate_btn = None
                    buttons = await page.query_selector_all('button')
                    for btn in buttons:
                        if not await btn.is_visible():
                            continue
                        text = (await btn.inner_text()).strip()
                        if 'arrow_forward' in text:
                            disabled = await btn.get_attribute('aria-disabled')
                            if disabled != 'true':
                                generate_btn = btn
                                break
                    
                    if generate_btn:
                        await generate_btn.click()
                        log.info("Generate clicked!")
                    else:
                        log.error("Generate button not found!")
                        return -1
                    
                    # Step 5: Wait for result images (media.getMediaUrlRedirect pattern)
                    initial_count = 0
                    existing = await page.query_selector_all('img[src*="media.getMediaUrlRedirect"]')
                    for img in existing:
                        if await img.is_visible():
                            bbox = await img.bounding_box()
                            if bbox and bbox['width'] > 100:
                                initial_count += 1
                    
                    await asyncio.sleep(5)
                    max_wait = 120
                    result_found = False
                    while (time.time() - start_time) < max_wait:
                        result_imgs = await page.query_selector_all('img[src*="media.getMediaUrlRedirect"]')
                        visible_count = 0
                        for img in result_imgs:
                            if await img.is_visible():
                                bbox = await img.bounding_box()
                                if bbox and bbox['width'] > 100:
                                    visible_count += 1
                        if visible_count > initial_count:
                            result_found = True
                            break
                        await asyncio.sleep(2)
                    
                    duration = time.time() - start_time
                    log.info(f"Benchmark done: {duration:.1f}s result={'found' if result_found else 'timeout'}")
                    return duration
                except Exception as e:
                    log.error(f"Benchmark failed: {e}")
                    return -1
                finally:
                    if 'browser' in locals():
                        await browser.close()
                    await pw.stop()

            duration = asyncio.run(test_ui())
            
            def notify():
                try:
                    from ui.widgets.toast import ToastManager
                    if duration > 0:
                        ToastManager.success(self, f"Test hoàn tất! {model_name}: {duration:.1f}s")
                    else:
                        ToastManager.error(self, f"Lỗi khi test {model_name}!")
                except:
                    pass
                    
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, notify)

        threading.Thread(target=_do_benchmark, daemon=True).start()

    def closeEvent(self, event):
        if self._content_pages and hasattr(self._content_pages[0], "splitter"):
            try:
                state = self._content_pages[0].splitter.saveState().toHex().data().decode("utf-8")
                self.settings.set("splitter_state", state)
            except Exception as e:
                log.error(f"Could not save splitter state: {e}")

        manager = self._get_task_manager()
        if manager and hasattr(manager, "stop_all"):
            try:
                manager.stop_all()
            except Exception:
                pass
        super().closeEvent(event)
