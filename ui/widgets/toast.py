# ui/widgets/toast.py

from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QColor
from ui.themes.tokens import THEME_TOKENS

class Toast(QWidget):
    def __init__(self, parent: QWidget, message: str, theme: str = "dark", duration_ms: int = 3000):
        super().__init__(parent)
        self.theme = theme
        self.message = message
        self.duration_ms = duration_ms
        self._opacity = 0.0
        
        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel(self.message)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        
        self._apply_style()
        self.adjustSize()
        self._position_toast()
        
        # Animation
        self.anim = QPropertyAnimation(self, b"opacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Tự động hide timer
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._hide_toast)
        
    def _apply_style(self):
        tokens = THEME_TOKENS.get(self.theme, THEME_TOKENS["dark"])
        self.label.setStyleSheet(f"""
            QLabel {{
                background-color: {tokens['bg_surface']};
                color: {tokens['text_primary']};
                border: 1px solid {tokens['border']};
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
            }}
        """)

    def _position_toast(self):
        if not self.parent():
            return
        parent_rect = self.parent().rect()
        x = parent_rect.width() - self.width() - 20
        y = parent_rect.height() - self.height() - 20
        self.move(x, y)

    def show_toast(self):
        self.show()
        self.raise_()
        self.anim.setDirection(QPropertyAnimation.Direction.Forward)
        self.anim.start()
        self.timer.start(self.duration_ms)
        
    def _hide_toast(self):
        self.anim.setDirection(QPropertyAnimation.Direction.Backward)
        self.anim.finished.connect(self.close)
        self.anim.start()

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, opacity):
        self._opacity = opacity
        self.setWindowOpacity(opacity)

    opacity = Property(float, get_opacity, set_opacity)

def show_toast(parent, message, theme="dark", duration_ms=3000):
    toast = Toast(parent, message, theme, duration_ms)
    toast.show_toast()
