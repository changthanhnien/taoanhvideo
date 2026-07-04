# ui/widgets/split_panel.py
from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtWidgets import QSplitter, QWidget

class SplitterHandleFilter(QObject):
    """Event filter to reset the splitter sizes to 50/50 on double click."""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonDblClick:
            parent = obj.parent()
            if isinstance(parent, QSplitter):
                w = parent.width()
                parent.setSizes([w // 2, w // 2])
            return True
        return False

class SplitPanel(QSplitter):
    """Unified resizable split layout component with strict min widths and double-click reset."""
    
    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setHandleWidth(8)  # Divider width: 6-8px
        self.setChildrenCollapsible(False)
        self.setOpaqueResize(True)
        self.setStyleSheet("""
            QSplitter::handle {
                background-color: #1f2937;
            }
            QSplitter::handle:hover {
                background-color: #3b82f6;
            }
        """)
        
        self._filter = SplitterHandleFilter(self)
        self._initialized_sizes = False
        
    def addWidget(self, widget: QWidget):
        super().addWidget(widget)
        
        # Enforce standardized panel constraints
        if self.count() == 1:
            widget.setMinimumWidth(420)
        elif self.count() == 2:
            widget.setMinimumWidth(500)
            
        # Re-install event filter for all handles
        for i in range(1, self.count()):
            handle = self.handle(i)
            if handle:
                handle.removeEventFilter(self._filter)
                handle.installEventFilter(self._filter)

    def restoreState(self, state):
        self._initialized_sizes = True
        res = super().restoreState(state)
        sizes = self.sizes()
        if len(sizes) == 2:
            left, right = sizes[0], sizes[1]
            total = left + right
            updated = False
            if left < 420:
                left = 420
                right = max(500, total - left)
                updated = True
            if right < 500:
                right = 500
                left = max(420, total - right)
                updated = True
            if updated:
                self.setSizes([left, right])
        return res

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initialized_sizes:
            self._initialized_sizes = True
            w = self.width()
            if w > 0:
                self.setSizes([w // 2, w // 2])
