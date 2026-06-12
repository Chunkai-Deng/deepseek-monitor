"""QThread worker for non-blocking API calls."""

import logging

from PySide6.QtCore import QThread, Signal

from api_client import ApiError, DeepSeekClient
from usage_model import BalanceInfo, UsageData

logger = logging.getLogger(__name__)


class RefreshWorker(QThread):
    """Runs balance + usage API calls in a background thread.

    Emits signals on completion or error. Each signal is processed
    on the main thread via Qt's automatic queued connection.
    """

    balance_ready = Signal(BalanceInfo)
    usage_ready = Signal(UsageData)
    balance_error = Signal(str)
    usage_error = Signal(str)
    finished = Signal()

    def __init__(self, client: DeepSeekClient, parent=None):
        super().__init__(parent)
        self.client = client

    def run(self):
        """Fetch balance and usage sequentially in the background thread."""
        # Fetch balance
        try:
            balance = self.client.fetch_balance()
            self.balance_ready.emit(balance)
        except ApiError as e:
            logger.warning("Balance fetch failed: %s", e)
            self.balance_error.emit(str(e))
        except Exception as e:
            logger.error("Unexpected balance error: %s", e)
            self.balance_error.emit(f"Unexpected error: {e}")

        # Fetch usage
        try:
            usage = self.client.fetch_usage(days=7)
            self.usage_ready.emit(usage)
        except ApiError as e:
            logger.debug("Usage fetch failed (endpoint may not exist): %s", e)
            self.usage_error.emit(str(e))
        except Exception as e:
            logger.debug("Unexpected usage error: %s", e)
            self.usage_error.emit(f"Unexpected error: {e}")

        self.finished.emit()
