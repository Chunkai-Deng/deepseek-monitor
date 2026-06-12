"""Modal settings dialog for API key configuration."""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from api_client import ApiError, DeepSeekClient
from styles import (
    ACCENT_BLUE,
    CARD_BG,
    DARK_BG,
    GRAY,
    GREEN,
    RED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

DIALOG_STYLE = f"""
QDialog {{
    background-color: {DARK_BG};
    color: {TEXT_PRIMARY};
}}
QLabel {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}
QLineEdit {{
    background-color: {CARD_BG};
    border: 1px solid {GRAY};
    border-radius: 4px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    font-size: 12px;
    min-width: 280px;
}}
QLineEdit:focus {{
    border-color: {ACCENT_BLUE};
}}
QSpinBox {{
    background-color: {CARD_BG};
    border: 1px solid {GRAY};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TEXT_PRIMARY};
    font-size: 12px;
    min-width: 100px;
}}
QSpinBox:focus {{
    border-color: {ACCENT_BLUE};
}}
QPushButton {{
    background-color: {CARD_BG};
    border: 1px solid {GRAY};
    border-radius: 4px;
    padding: 6px 16px;
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}
QPushButton:hover {{
    border-color: {ACCENT_BLUE};
}}
QPushButton#testBtn {{
    background-color: transparent;
    border: 1px solid {ACCENT_BLUE};
    color: {ACCENT_BLUE};
}}
QPushButton#testBtn:hover {{
    background-color: {ACCENT_BLUE};
    color: white;
}}
QDialogButtonBox QPushButton {{
    min-width: 80px;
}}
"""


class _TestWorker(QThread):
    """Background thread for testing API connection."""

    result = Signal(bool, str)  # success, message

    def __init__(self, api_key: str, parent=None):
        super().__init__(parent)
        self.api_key = api_key

    def run(self):
        client = DeepSeekClient(self.api_key)
        try:
            balance = client.fetch_balance()
            self.result.emit(
                True,
                f"Connected! Balance: ¥{balance.total_balance:,.2f}",
            )
        except ApiError as e:
            self.result.emit(False, str(e))
        except Exception as e:
            self.result.emit(False, f"Connection failed: {e}")


class SettingsDialog(QDialog):
    """Dialog for configuring API key and preferences."""

    def __init__(self, current_api_key: str | None, refresh_interval: int, stock_codes: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("DeepSeek Monitor Settings")
        self.setFixedSize(420, 350)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setStyleSheet(DIALOG_STYLE)
        self._new_api_key: str | None = None
        self._new_interval: int = refresh_interval
        self._new_stock_codes: str = stock_codes

        self._setup_ui(current_api_key, refresh_interval, stock_codes)

    def _setup_ui(self, current_api_key: str | None, refresh_interval: int, stock_codes: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("⚙  Settings")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding-bottom: 4px;")
        layout.addWidget(title)

        # Form
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        # API Key
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxx")
        if current_api_key:
            self._key_input.setText(current_api_key)
        form.addRow("API Key:", self._key_input)

        # Refresh interval
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(5, 300)
        self._interval_spin.setValue(refresh_interval)
        self._interval_spin.setSuffix(" seconds")
        form.addRow("Refresh every:", self._interval_spin)

        # Stock code
        self._stock_input = QLineEdit()
        self._stock_input.setPlaceholderText("e.g. 600519,000858")
        if stock_codes:
            self._stock_input.setText(stock_codes)
        form.addRow("Stock codes:", self._stock_input)

        # Hint below stock input
        stock_hint = QLabel("  多个代码用逗号分隔，例如 600519,000858,300750")
        stock_hint.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 10px; padding-left: 2px;")
        form.addRow("", stock_hint)

        layout.addLayout(form)

        # Test connection button + result
        test_layout = QHBoxLayout()
        test_layout.setSpacing(10)

        self._test_btn = QPushButton("🔍  Test Connection")
        self._test_btn.setObjectName("testBtn")
        self._test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_btn.clicked.connect(self._on_test_connection)
        test_layout.addWidget(self._test_btn)

        self._test_result = QLabel("")
        self._test_result.setStyleSheet(f"font-size: 11px; color: {TEXT_SECONDARY};")
        test_layout.addWidget(self._test_result, 1)

        layout.addLayout(test_layout)

        layout.addStretch()

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_test_connection(self):
        """Test the API key in a background thread."""
        key = self._key_input.text().strip()
        if not key:
            self._test_result.setStyleSheet(f"color: {RED}; font-size: 11px;")
            self._test_result.setText("Please enter an API key first")
            return

        self._test_btn.setEnabled(False)
        self._test_result.setStyleSheet(f"color: {ACCENT_BLUE}; font-size: 11px;")
        self._test_result.setText("Testing...")

        self._worker = _TestWorker(key)
        self._worker.result.connect(self._on_test_result)
        self._worker.start()

    def _on_test_result(self, success: bool, message: str):
        """Handle the test connection result."""
        self._test_btn.setEnabled(True)
        color = GREEN if success else RED
        self._test_result.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._test_result.setText(message)

    def _on_accept(self):
        """Validate and accept."""
        key = self._key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Missing API Key", "Please enter your DeepSeek API key.")
            return
        self._new_api_key = key
        self._new_interval = self._interval_spin.value()
        self._new_stock_codes = self._stock_input.text().strip()
        self.accept()

    @property
    def api_key(self) -> str | None:
        return self._new_api_key

    @property
    def refresh_interval(self) -> int:
        return self._new_interval

    @property
    def stock_codes(self) -> str:
        return self._new_stock_codes
