import sys
import traceback
import logging

# Configure logging to see all logs
logging.basicConfig(level=logging.DEBUG)

from PySide6.QtWidgets import QApplication
from models.database import Database
from config.settings import Settings
from ui.main_window import MainWindow
from ui.pages.content_page import ContentPage

def test_start():
    app = QApplication(sys.argv)
    db = Database()
    settings = Settings(db)

    # Patch QMessageBox so we don't block
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.warning = lambda *args: print(f"WARNING BOX: {args}")

    print("Initializing MainWindow...")
    main = MainWindow(db, settings=settings)
    
    print("Navigating to frame_video...")
    main._on_page_changed("frame_video")
    page = main.pages["frame_video"]
    print("Page object:", page)

    # Make sure we're testing the real page if it's lazy
    if hasattr(page, "ensure_loaded"):
        page = page.ensure_loaded()

    # Hook the emit to see if the signal fires
    original_emit = page.start_task.emit
    def hooked_emit(config):
        print(f"DEBUG: start_task.emit called with config: {config}")
        try:
            original_emit(config)
        except Exception as e:
            print("ERROR IN EMIT:", e)
            traceback.print_exc()
    page.start_task.emit = hooked_emit

    # Hook _on_start_task in main window
    original_on_start_task = main._on_start_task
    def hooked_on_start_task(task):
        print(f"DEBUG: main_window._on_start_task received task!")
        try:
            return original_on_start_task(task)
        except Exception as e:
            print("ERROR IN _on_start_task:", e)
            traceback.print_exc()
            return None
    main._on_start_task = hooked_on_start_task

    print("Simulating action_bar.start_btn click...")
    # Actually we can just call _on_start()
    try:
        page._on_start()
    except Exception as e:
        print("ERROR IN _on_start:", e)
        traceback.print_exc()

    print("Test finished.")
    # We do not call app.exec() so it exits.

if __name__ == "__main__":
    test_start()
