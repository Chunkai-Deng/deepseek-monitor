"""DeepSeek Usage Monitor — Windows desktop floating widget.

Displays real-time DeepSeek API balance and usage info in a
frameless, always-on-top floating window with system tray integration.

Usage:
    python main.py
"""

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from api_client import DeepSeekClient
from config_manager import ConfigManager
from floating_widget import FloatingWidget
from settings_dialog import SettingsDialog
from tray_manager import TrayManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class App:
    """Main application controller — wires all components together."""

    def __init__(self):
        self.config = ConfigManager()

        # Load API key
        api_key = self.config.load_api_key()
        if api_key:
            logger.info("API key loaded from credential manager")

        self.client = DeepSeekClient(api_key)

        # Create UI
        self.widget = FloatingWidget(self.client, self.config)
        self.widget.settings_requested.connect(self._open_settings)

        self.tray = TrayManager(self.widget)

        # If no API key, open settings on first launch
        if not api_key:
            logger.info("No API key found — opening settings")
            self._open_settings()

    def _open_settings(self):
        """Open the settings dialog and apply changes."""
        dialog = SettingsDialog(
            current_api_key=self.client.api_key,
            refresh_interval=self.config.refresh_interval,
            stock_codes=self.config.stock_codes,
            parent=self.widget,
        )

        # Show dialog (non-blocking relative to the app, but modal to the dialog)
        # We bring the widget to front so the dialog appears on top
        self.widget.show()
        self.widget.raise_()

        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            new_key = dialog.api_key
            if new_key != self.client.api_key:
                self.client.api_key = new_key
                self.config.save_api_key(new_key)
                logger.info("API key updated")

            new_interval = dialog.refresh_interval
            if new_interval != self.config.refresh_interval:
                self.widget.update_timer_interval(new_interval)
                logger.info("Refresh interval updated to %ds", new_interval)

            new_stock_codes = dialog.stock_codes
            if new_stock_codes != self.config.stock_codes:
                self.config.stock_codes = new_stock_codes
                codes = [c.strip() for c in new_stock_codes.split(",") if c.strip()]
                self.widget.update_stock_codes(codes)
                logger.info("Stock codes updated to %s", new_stock_codes)

            # Refresh immediately with new credentials
            self.widget.do_refresh()


def main():
    # Enable High-DPI support before creating QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep alive when minimized to tray
    app.setApplicationName("DeepSeek Usage Monitor")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("DeepSeekMonitor")

    # Create and run
    app_controller = App()
    app_controller.widget.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
