"""NAV TOOLS - Dark theme stylesheet (Slate Kinetic from Stitch)."""

DARK_THEME_QSS = """
/* ============================================================
   Global
   ============================================================ */
* {
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 15px;
    color: #f4f4f5;
    outline: none;
}

QMainWindow, QWidget, QFrame, QDialog,
QScrollArea, QAbstractScrollArea,
QStackedWidget, QTabWidget {
    background-color: #09090b;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QWidget#centralWidget {
    background-color: #09090b;
}

/* ============================================================
   Sidebar
   ============================================================ */
QWidget#sidebar {
    background-color: #18181b;
    border-right: 1px solid #27272a;
}

QLabel#sidebar-logo {
    font-family: "Segoe UI", sans-serif;
    font-size: 10px;
    font-weight: 800;
    color: #a1a1aa;
    padding: 6px 0 2px 0;
    letter-spacing: 1px;
}

QWidget[class="sidebar-btn"] {
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 6px 4px;
    margin: 1px 2px;
}

QWidget[class="sidebar-btn"]:hover {
    background-color: #27272a;
}

QWidget[class="sidebar-btn"][active="true"] {
    background-color: rgba(77, 142, 255, 0.15);
}

QWidget[class="sidebar-btn"] QLabel {
    background: transparent;
    color: #a1a1aa;
}

QWidget[class="sidebar-btn"]:hover QLabel {
    color: #f4f4f5;
}

QWidget[class="sidebar-btn"][active="true"] QLabel {
    color: #60a5fa;
    font-weight: bold;
}

QLabel#sidebar-version {
    color: #52525b;
    font-size: 10px;
}

/* ============================================================
   Config Panel (Left Panel)
   ============================================================ */
QWidget#configPanel {
    background-color: #18181b;
    border-right: 1px solid #27272a;
}

QLabel.section-title {
    font-size: 20px;
    font-weight: bold;
    color: #f4f4f5;
    padding: 4px 0;
}

QLabel.field-label {
    font-size: 14px;
    font-weight: bold;
    color: #d4d4d8;
    padding: 4px 0;
}

QLabel.model-info {
    font-size: 11px;
    color: #a1a1aa;
    font-style: italic;
}

/* ============================================================
   Form Inputs
   ============================================================ */
QLineEdit, QSpinBox, QTextEdit, QPlainTextEdit {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f4f4f5;
    font-size: 14px;
    selection-background-color: #3b82f6;
}

QLineEdit:focus, QSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #60a5fa;
    background-color: #3f3f46;
}

QLineEdit:disabled, QSpinBox:disabled {
    background-color: #18181b;
    color: #52525b;
    border-color: #27272a;
}

QComboBox {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f4f4f5;
    font-size: 14px;
}

QComboBox:hover {
    border: 1px solid #60a5fa;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border: none;
    background: transparent;
}

QComboBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #a1a1aa;
}

QComboBox:hover::down-arrow {
    border-top: 6px solid #60a5fa;
}

QComboBox QAbstractItemView {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
    padding: 4px;
    outline: none;
}

/* ---- SpinBox Arrows ---- */
QSpinBox::up-button, QSpinBox::down-button {
    subcontrol-origin: border;
    width: 24px;
    background: transparent;
    border: none;
}
QSpinBox::up-button {
    subcontrol-position: top right;
    border-bottom: 1px solid #3f3f46;
}
QSpinBox::down-button {
    subcontrol-position: bottom right;
}
QSpinBox::up-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #a1a1aa;
}
QSpinBox::down-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #a1a1aa;
}
QSpinBox::up-arrow:hover { border-bottom: 5px solid #60a5fa; }
QSpinBox::down-arrow:hover { border-top: 5px solid #60a5fa; }

/* ============================================================
   Generic Buttons
   ============================================================ */
QPushButton {
    background-color: #27272a;
    color: #f4f4f5;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    border: none;
}

QPushButton:hover {
    background-color: #3f3f46;
}

QPushButton:pressed {
    background-color: #18181b;
}

QPushButton#btn-primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366f1, stop:1 #8b5cf6);
    color: #ffffff;
    font-weight: bold;
    font-size: 14px;
    padding: 10px 20px;
    border-radius: 8px;
}

QPushButton#btn-primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #818cf8, stop:1 #a78bfa);
}

QPushButton#btn-secondary {
    background-color: #27272a;
    color: #60a5fa;
    border: 1px solid #3f3f46;
}
QPushButton#btn-secondary:hover {
    background-color: #3f3f46;
    border: 1px solid #60a5fa;
}

QPushButton#btn-success {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #22c55e, stop:1 #16a34a);
    color: #ffffff;
}

QPushButton#btn-warning {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f97316, stop:1 #ea580c);
    color: #ffffff;
}

QPushButton#btn-danger {
    background-color: #ef4444;
    color: #ffffff;
}

QPushButton#btn-ghost {
    background: transparent;
    color: #a1a1aa;
    border: 1px solid transparent;
}
QPushButton#btn-ghost:hover {
    background-color: #27272a;
    color: #f4f4f5;
}

QPushButton:disabled {
    background-color: #18181b;
    color: #52525b;
}

/* ============================================================
   Action Bar (Bottom Sticky)
   ============================================================ */
QWidget#actionBar {
    background-color: #18181b;
    border-top: 1px solid #27272a;
}

/* ============================================================
   Table (Task Table)
   ============================================================ */
QTableWidget {
    background-color: #09090b;
    alternate-background-color: #18181b;
    border: none;
    gridline-color: #27272a;
    selection-background-color: #27272a;
    selection-color: #f4f4f5;
}

QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #27272a;
}

QTableWidget::item:selected {
    background-color: #27272a;
}

QHeaderView::section {
    background-color: #18181b;
    color: #a1a1aa;
    font-weight: bold;
    font-size: 13px;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #27272a;
    border-right: 1px solid #27272a;
}
QHeaderView::section:last { border-right: none; }

/* ============================================================
   Scrollbar
   ============================================================ */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #3f3f46;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #52525b;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #3f3f46;
    border-radius: 4px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: #52525b;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    background: transparent;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* ============================================================
   Badges / Labels
   ============================================================ */
QLabel.badge-free { background-color: #27272a; color: #a1a1aa; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: bold; }
QLabel.badge-tier { background-color: rgba(96,165,250,0.15); color: #60a5fa; border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: bold; }
QLabel.badge-success { background-color: rgba(34,197,94,0.15); color: #4ade80; border-radius: 4px; padding: 2px 8px; font-size: 11px; }
QLabel.badge-error { background-color: rgba(239,68,68,0.15); color: #f87171; border-radius: 4px; padding: 2px 8px; font-size: 11px; }
QLabel.badge-pending { background-color: #27272a; color: #a1a1aa; border-radius: 4px; padding: 2px 8px; font-size: 11px; }
QLabel.badge-running { background-color: rgba(249,115,22,0.15); color: #fb923c; border-radius: 4px; padding: 2px 8px; font-size: 11px; }

/* ============================================================
   Tab Widget
   ============================================================ */
QTabWidget::pane {
    background-color: #18181b;
    border: none;
    border-top: 2px solid #6366f1;
}
QTabBar::tab {
    background-color: #09090b;
    color: #a1a1aa;
    padding: 10px 20px;
    border: none;
    font-weight: 500;
}
QTabBar::tab:selected {
    color: #8b5cf6;
    border-bottom: 2px solid #8b5cf6;
}
QTabBar::tab:hover {
    color: #f4f4f5;
    background-color: #18181b;
}

/* ============================================================
   Toggle Switch (via QCheckBox)
   ============================================================ */
QCheckBox { spacing: 8px; color: #f4f4f5; }
QCheckBox::indicator { width: 36px; height: 20px; border-radius: 10px; background-color: #3f3f46; border: none; }
QCheckBox::indicator:checked { background-color: #6366f1; }

/* ============================================================
   Dialog
   ============================================================ */
QDialog { background-color: #18181b; border: 1px solid #3f3f46; border-radius: 8px; }

/* ============================================================
   Splitter
   ============================================================ */
QSplitter::handle { background-color: #27272a; width: 5px; border-radius: 2px; }
QSplitter::handle:hover { background-color: #6366f1; }

/* ============================================================
   Context Menu
   ============================================================ */
QMenu {
    background-color: #18181b;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 4px;
    color: #f4f4f5;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
    color: #f4f4f5;
    background: transparent;
}
QMenu::item:selected {
    background-color: #3b82f6;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #27272a;
    margin: 4px 8px;
}

/* ============================================================
   Tooltip
   ============================================================ */
QToolTip {
    background-color: #27272a;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}

/* ============================================================
   QFrame (styled panels)
   ============================================================ */
QFrame[frameShape="6"] {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 8px;
}
"""
