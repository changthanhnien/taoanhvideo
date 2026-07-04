# ui/pages/history_page.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QApplication
from ui.workflow.history_picker_dialog import HistoryPickerWidget

class HistoryPage(QWidget):
    """Global history page that displays the exact same interface as nodes picker."""
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.is_loaded = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Find the main window from top-level widgets
        main_win = None
        for w in QApplication.topLevelWidgets():
            if hasattr(w, "db"):
                main_win = w
                break
            
        # Instantiate HistoryPickerWidget directly
        self.picker = HistoryPickerWidget(
            main_win=main_win,
            media_type="all",
            multi_select=True,
            parent=self
        )
        layout.addWidget(self.picker)

    def refresh(self):
        if hasattr(self, "picker") and hasattr(self.picker, "_load_data"):
            self.picker._load_data()

    def ensure_loaded(self):
        self.is_loaded = True
        self.refresh()
