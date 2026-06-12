"""System tray icon and context menu."""

from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QAction, QFont
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from styles import DARK_BG, CARD_BG, TEXT_PRIMARY, GREEN


def _make_tray_icon() -> QIcon:
    """Generate a simple colored-circle tray icon programmatically."""
    size = 32
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw a circle
    painter.setBrush(QBrush(QColor(GREEN)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, size - 8, size - 8)

    # Draw "D" letter
    painter.setPen(QColor(255, 255, 255))
    font = QFont("Segoe UI", 14, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "D")

    painter.end()
    return QIcon(pixmap)


class TrayManager:
    """Manages the system tray icon and its context menu."""

    def __init__(self, floating_widget):
        self._widget = floating_widget

        self._tray_icon = QSystemTrayIcon()
        self._tray_icon.setIcon(_make_tray_icon())
        self._tray_icon.setToolTip("DeepSeek Usage Monitor")

        # Context menu
        self._menu = QMenu()
        self._menu.setStyleSheet(f"""
            QMenu {{
                background-color: {DARK_BG};
                border: 1px solid {CARD_BG};
                color: {TEXT_PRIMARY};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {CARD_BG};
            }}
            QMenu::separator {{
                height: 1px;
                background: {CARD_BG};
                margin: 4px 8px;
            }}
        """)

        # Show / Hide
        self._show_action = QAction("👁  Show Window", self._menu)
        self._show_action.triggered.connect(self._toggle_visibility)
        self._menu.addAction(self._show_action)

        self._menu.addSeparator()

        # Refresh
        refresh_action = QAction("🔄  Refresh Now", self._menu)
        refresh_action.triggered.connect(self._widget.do_refresh)
        self._menu.addAction(refresh_action)

        # Settings
        settings_action = QAction("⚙  Settings...", self._menu)
        settings_action.triggered.connect(lambda: self._widget.settings_requested.emit())
        self._menu.addAction(settings_action)

        self._menu.addSeparator()

        # Exit
        exit_action = QAction("✕  Exit", self._menu)
        exit_action.triggered.connect(self._widget.quit_app)
        self._menu.addAction(exit_action)

        self._tray_icon.setContextMenu(self._menu)

        # Double-click → toggle visibility
        self._tray_icon.activated.connect(self._on_activated)

        self._tray_icon.show()

    def _toggle_visibility(self):
        """Toggle window visibility and update menu label."""
        if self._widget.isVisible():
            self._widget.hide()
            self._show_action.setText("👁  Show Window")
        else:
            self._widget.show()
            self._show_action.setText("🙈  Hide Window")

    def _on_activated(self, reason):
        """Handle tray icon activation (double-click)."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_visibility()

    def update_icon_status(self, color: str):
        """Update the tray icon color to reflect status."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 24, 24)

        painter.setPen(QColor(255, 255, 255))
        font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "D")

        painter.end()
        self._tray_icon.setIcon(QIcon(pixmap))

    def set_visible(self, visible: bool):
        """Show or hide the tray icon."""
        self._tray_icon.setVisible(visible)
