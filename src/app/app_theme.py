from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


MIDNIGHT_BLUE_STYLESHEET = """
QWidget {
    background-color: #0b1220;
    color: #dbe7f5;
    font-size: 10pt;
}

QMainWindow, QDialog {
    background-color: #0b1220;
}

QMenuBar, QMenu {
    background-color: #0e1729;
    color: #dbe7f5;
}

QMenuBar::item:selected, QMenu::item:selected {
    background-color: #173158;
}

QDockWidget {
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}

QTabWidget::pane {
    border: 1px solid #23314a;
    border-radius: 8px;
    background-color: #101a2e;
    top: -1px;
}

QTabBar::tab {
    background-color: #101a2e;
    color: #b8c8de;
    border: 1px solid #23314a;
    padding: 8px 14px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background-color: #173158;
    color: #ffffff;
    border-color: #2f74ff;
}

QLabel {
    color: #8e9ab0;
    background: transparent;
    border: none;
}

QFrame, QSplitter::handle {
    background-color: #101a2e;
}

QTreeWidget, QListWidget, QPlainTextEdit, QTextEdit, QTextBrowser, QLineEdit, QTableWidget, QCalendarWidget {
    background-color: #0f1728;
    color: #edf4ff;
    border: 1px solid #22314b;
    border-radius: 8px;
    selection-background-color: #2f74ff;
    selection-color: #ffffff;
}

QTreeWidget::item, QListWidget::item {
    padding: 6px 8px;
}

QTableWidget::item {
    padding: 6px;
}

QHeaderView::section {
    background-color: #101a2e;
    color: #dbe7f5;
    border: none;
    padding: 6px 8px;
}

QCalendarWidget QToolButton {
    background-color: #173158;
    color: #ffffff;
    border: 1px solid #2f74ff;
    border-radius: 6px;
    padding: 4px 8px;
}

QCalendarWidget QAbstractItemView {
    selection-background-color: #2f74ff;
    selection-color: #ffffff;
}

QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #1c3d6b;
}

QPlainTextEdit, QTextEdit, QTextBrowser {
    padding: 8px;
}

QPushButton {
    background-color: #173158;
    color: #ffffff;
    border: 1px solid #2f74ff;
    border-radius: 8px;
    padding: 7px 12px;
}

QPushButton:hover {
    background-color: #1f4275;
}

QPushButton:pressed {
    background-color: #102545;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #0b1220;
}

QToolTip {
    background-color: #101a2e;
    color: #edf4ff;
    border: 1px solid #2f74ff;
}
"""


def apply_midnight_blue_theme(app: QApplication) -> None:
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0b1220"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#dbe7f5"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#0f1728"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#101a2e"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#101a2e"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#edf4ff"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#edf4ff"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#173158"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2f74ff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#7ab0ff"))
    app.setPalette(palette)
    app.setStyleSheet(MIDNIGHT_BLUE_STYLESHEET)
