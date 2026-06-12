"""Core floating widget — frameless, always-on-top window."""

import logging
from datetime import datetime

from PySide6.QtCore import (
    Qt, QTimer, QPoint, Signal, Property, QEasingCurve,
    QPropertyAnimation, QVariantAnimation,
)
from PySide6.QtGui import QAction, QMouseEvent, QEnterEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from api_client import DeepSeekClient
from config_manager import ConfigManager
from refresh_worker import RefreshWorker
from stock_card_widget import StockCardWidget
from stock_worker import StockData, StockWorker
from styles import (
    ACCENT_BLUE,
    CARD_BG,
    DARK_BG,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    GRAY,
    GREEN,
    MAIN_STYLE,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    ORANGE,
    RED,
    RESIZE_MARGIN,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TITLE_BAR_HEIGHT,
    health_color,
    health_label,
)
from usage_model import BalanceInfo, UsageData

logger = logging.getLogger(__name__)


class FloatingWidget(QWidget):
    """Main floating window showing DeepSeek API usage info."""

    # Signals
    settings_requested = Signal()  # Emitted when user wants to open settings
    refresh_requested = Signal()  # Emitted for external refresh triggers

    def __init__(
        self,
        client: DeepSeekClient,
        config: ConfigManager,
        parent=None,
    ):
        super().__init__(parent)
        self.client = client
        self.config = config

        self._balance: BalanceInfo | None = None
        self._usage: UsageData | None = None
        self._status: str = "No API Key"
        self._status_color: str = GRAY
        self._drag_offset: QPoint | None = None
        self._refreshing: bool = False

        # Resize state
        self._resize_edge: str | None = None
        self._resize_start_geom: None = None  # QRect
        self._resize_start_pos: QPoint | None = None

        # Auto-hide (dock to edge) state
        self._is_docked: bool = False
        self._normal_pos: QPoint | None = None
        self._dock_animating: bool = False
        self._auto_hide_enabled: bool = True

        # Stock state (multi-stock)
        self._stock_codes: list[str] = []
        self._stock_cards: dict[str, StockCardWidget] = {}
        self._stock_workers: dict[str, StockWorker] = {}

        self._setup_window()
        self._setup_ui()
        self._setup_timer()
        self._setup_auto_hide()
        self._apply_styles()

        # Parse initial stock codes and build cards
        initial_codes = [c.strip() for c in self.config.stock_codes.split(",") if c.strip()]
        if initial_codes:
            self.update_stock_codes(initial_codes)

        # Initial balance refresh
        if self.client.api_key:
            self.do_refresh()
        else:
            self.settings_requested.emit()

    # -- Window setup --

    def _setup_window(self):
        """Configure frameless, always-on-top, translucent window."""
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.93)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.setMouseTracking(True)  # needed for edge cursor updates
        self.setWindowTitle("DeepSeek Usage Monitor")

        # Restore saved size, or use default
        saved_size = self.config.window_size
        if saved_size is not None and saved_size.isValid():
            saved_w = max(saved_size.width(), MIN_WINDOW_WIDTH)
            saved_h = max(saved_size.height(), MIN_WINDOW_HEIGHT)
            self.resize(saved_w, saved_h)
        else:
            self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Restore saved position, or default to top-right
        saved_pos = self.config.window_position
        if saved_pos is not None:
            self.move(saved_pos)
        else:
            screen = QApplication.primaryScreen()
            if screen:
                geom = screen.availableGeometry()
                self.move(
                    geom.right() - DEFAULT_WINDOW_WIDTH - 20,
                    geom.top() + 60,
                )

        # Drop shadow for the frameless window
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(Qt.GlobalColor.black)
        # Apply shadow to the central widget (set in _setup_ui)

    def _get_resize_edge(self, pos) -> str | None:
        """Return which edge/corner the local position is near, or None."""
        lx, ly = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = RESIZE_MARGIN

        on_left = lx < m
        on_right = lx > w - m
        on_top = ly < m
        on_bottom = ly > h - m

        if on_top and on_left:
            return "topleft"
        if on_top and on_right:
            return "topright"
        if on_bottom and on_left:
            return "bottomleft"
        if on_bottom and on_right:
            return "bottomright"
        if on_left:
            return "left"
        if on_right:
            return "right"
        if on_top:
            return "top"
        if on_bottom:
            return "bottom"
        return None

    @staticmethod
    def _cursor_for_edge(edge: str | None):
        """Return the cursor shape for a given resize edge."""
        if edge in ("left", "right"):
            return Qt.CursorShape.SizeHorCursor
        if edge in ("top", "bottom"):
            return Qt.CursorShape.SizeVerCursor
        if edge in ("topleft", "bottomright"):
            return Qt.CursorShape.SizeFDiagCursor
        if edge in ("topright", "bottomleft"):
            return Qt.CursorShape.SizeBDiagCursor
        return Qt.CursorShape.ArrowCursor

    # -- UI construction --

    def _setup_ui(self):
        """Build the widget layout."""
        # Root layout (no margins — the central widget handles padding)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Central widget with rounded corners background
        self._central = QWidget()
        self._central.setObjectName("centralWidget")
        root_layout.addWidget(self._central)

        central_layout = QVBoxLayout(self._central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # -- Title bar --
        self._title_bar = self._make_title_bar()
        self._title_bar.setObjectName("titleBar")
        central_layout.addWidget(self._title_bar)

        # -- Balance section --
        self._section_balance_header = QLabel("💰  BALANCE")
        self._section_balance_header.setObjectName("sectionHeader")
        central_layout.addWidget(self._section_balance_header)

        self._balance_card = QFrame()
        self._balance_card.setObjectName("infoCard")
        balance_layout = QVBoxLayout(self._balance_card)
        balance_layout.setContentsMargins(0, 0, 0, 0)
        balance_layout.setSpacing(1)

        self._lbl_total = self._make_info_row("Total:", "¥ ---")
        self._lbl_topped_up = self._make_info_row("Top-up:", "¥ ---")
        self._lbl_granted = self._make_info_row("Granted:", "¥ ---")

        # Divider
        divider = QFrame()
        divider.setObjectName("balanceDivider")
        divider.setFrameShape(QFrame.Shape.HLine)

        # Today Spent row
        self._lbl_today_spent = self._make_info_row("Today Spent:", "¥ ---")
        # Override label styles for today-spent row
        if hasattr(self._lbl_today_spent, "_value_label"):
            self._lbl_today_spent._value_label.setObjectName("todaySpentValue")
        for i in range(self._lbl_today_spent.count()):
            item = self._lbl_today_spent.itemAt(i)
            if item and item.widget():
                lbl = item.widget()
                if isinstance(lbl, QLabel) and lbl.objectName() == "infoLabel":
                    lbl.setObjectName("todaySpentLabel")

        balance_layout.addLayout(self._lbl_total)
        balance_layout.addLayout(self._lbl_topped_up)
        balance_layout.addLayout(self._lbl_granted)
        balance_layout.addWidget(divider)
        balance_layout.addLayout(self._lbl_today_spent)
        central_layout.addWidget(self._balance_card)

        # -- Stock section --
        self._section_stock_header = QLabel("📈  STOCK")
        self._section_stock_header.setObjectName("sectionHeader")
        central_layout.addWidget(self._section_stock_header)

        # Scroll area for stock cards
        self._stock_scroll = QScrollArea()
        self._stock_scroll.setObjectName("stockScrollArea")
        self._stock_scroll.setWidgetResizable(True)
        self._stock_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._stock_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._stock_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._stock_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._stock_scroll_content = QWidget()
        self._stock_scroll_content.setObjectName("stockScrollContent")
        self._stock_scroll_content_layout = QVBoxLayout(self._stock_scroll_content)
        self._stock_scroll_content_layout.setContentsMargins(8, 0, 8, 4)
        self._stock_scroll_content_layout.setSpacing(6)
        self._stock_scroll.setWidget(self._stock_scroll_content)

        central_layout.addWidget(self._stock_scroll, 1)  # stretch factor = 1

        # -- Status bar --
        self._status_bar = self._make_status_bar()
        self._status_bar.setObjectName("statusBar")
        central_layout.addWidget(self._status_bar)

    def _make_title_bar(self) -> QWidget:
        """Create the custom title bar with status dot, label, and buttons."""
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 4, 0)
        layout.setSpacing(6)

        # Status dot
        self._status_dot = QLabel("●")
        self._status_dot.setObjectName("statusDot")
        self._status_dot.setStyleSheet(f"color: {GRAY}; font-size: 12px;")
        layout.addWidget(self._status_dot)

        # Title
        self._title_label = QLabel("DeepSeek Usage")
        self._title_label.setObjectName("titleLabel")
        layout.addWidget(self._title_label)

        layout.addStretch()

        # Minimize button
        self._minimize_btn = QLabel("—")
        self._minimize_btn.setObjectName("minimizeBtn")
        self._minimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._minimize_btn.mousePressEvent = lambda e: self.hide()
        layout.addWidget(self._minimize_btn)

        # Close button
        self._close_btn = QLabel("✕")
        self._close_btn.setObjectName("closeBtn")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.mousePressEvent = lambda e: self.hide()
        layout.addWidget(self._close_btn)

        return bar

    def _make_info_row(self, label: str, value: str) -> QHBoxLayout:
        """Create a label: value row for info cards."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 1, 0, 1)
        row.setSpacing(8)

        lbl = QLabel(label)
        lbl.setObjectName("infoLabel")
        lbl.setMinimumWidth(75)
        row.addWidget(lbl)

        val = QLabel(value)
        val.setObjectName("infoValue")
        row.addWidget(val, 1)

        # Store the value label for later updates
        row._value_label = val  # type: ignore
        return row

    def _make_status_bar(self) -> QWidget:
        """Create the bottom status bar."""
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        self._last_refresh_label = QLabel("Last refresh: --")
        self._last_refresh_label.setObjectName("lastRefreshLabel")
        layout.addWidget(self._last_refresh_label)

        layout.addStretch()

        self._status_label = QLabel("No API Key")
        self._status_label.setObjectName("statusLabel")
        self._status_label.setStyleSheet(f"color: {GRAY};")
        layout.addWidget(self._status_label)

        return bar

    def _apply_styles(self):
        """Apply the QSS stylesheet."""
        self.setStyleSheet(MAIN_STYLE)

    # -- Timer --

    def _setup_timer(self):
        """Set up the 30-second auto-refresh timer."""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)
        self._timer.start(self.config.refresh_interval * 1000)

        # Refresh countdown label
        self._countdown = 0

    def _on_timer_tick(self):
        """Called every N seconds — refresh both balance and stock."""
        self.do_refresh()
        self.do_stock_refresh()

    def update_timer_interval(self, seconds: int):
        """Change the refresh interval."""
        self.config.refresh_interval = seconds
        self._timer.setInterval(seconds * 1000)

    # -- Auto-hide (dock to edge) --

    def _setup_auto_hide(self):
        """Set up the 10-second inactivity timer for auto-docking to screen edge."""
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setInterval(10000)  # 10 seconds
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._dock_to_edge)

        # Start tracking mouse movement
        self.setMouseTracking(True)
        self._auto_hide_timer.start()

    def _reset_auto_hide_timer(self):
        """Reset the inactivity countdown. Called on every mouse move."""
        if self._auto_hide_enabled and not self._is_docked:
            self._auto_hide_timer.start()

    def _dock_to_edge(self):
        """Slide the window to the nearest screen edge, leaving 5px visible."""
        if self._is_docked or self._dock_animating:
            return

        self._is_docked = True
        self._normal_pos = self.pos()

        # Find nearest screen edge
        screen = QApplication.screenAt(self._normal_pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return

        geom = screen.availableGeometry()
        cx = self._normal_pos.x() + self.width() // 2
        cy = self._normal_pos.y() + self.height() // 2

        # Distance to each edge
        dist_left = cx - geom.left()
        dist_right = geom.right() - cx
        dist_top = cy - geom.top()
        dist_bottom = geom.bottom() - cy

        edge = min(
            (dist_left, "left"),
            (dist_right, "right"),
            (dist_top, "top"),
            (dist_bottom, "bottom"),
            key=lambda x: x[0],
        )[1]

        # Calculate target off-screen position (5px visible)
        if edge == "right":
            target = QPoint(geom.right() - 5, self._normal_pos.y())
        elif edge == "left":
            target = QPoint(geom.left() - self.width() + 5, self._normal_pos.y())
        elif edge == "bottom":
            target = QPoint(self._normal_pos.x(), geom.bottom() - 5)
        else:  # top
            target = QPoint(self._normal_pos.x(), geom.top() - self.height() + 5)

        self._dock_edge = edge
        self._animate_to_position(self._normal_pos, target)

    def _restore_from_edge(self):
        """Slide the window back from the docked edge."""
        if not self._is_docked or self._dock_animating:
            return
        if self._normal_pos is None:
            return

        self._is_docked = False
        current = self.pos()
        self._animate_to_position(current, self._normal_pos)
        self._dock_edge = None

    def _animate_to_position(self, start: QPoint, end: QPoint):
        """Smoothly animate the window from start to end position."""
        self._dock_animating = True

        anim = QVariantAnimation(self)
        anim.setDuration(300)  # ms
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def on_value_changed(val):
            self.move(val)

        anim.valueChanged.connect(on_value_changed)

        def on_finished():
            self._dock_animating = False
            # If just docked, start edge polling for mouse hover
            if self._is_docked:
                self._start_edge_poll()

        anim.finished.connect(on_finished)
        anim.start()

    def _start_edge_poll(self):
        """Poll mouse position to detect when it hovers over the docked edge strip."""
        self._edge_poll_timer = QTimer(self)
        self._edge_poll_timer.setInterval(200)  # Check every 200ms
        self._edge_poll_timer.timeout.connect(self._check_edge_hover)
        self._edge_poll_timer.start()

    def _check_edge_hover(self):
        """Check if the mouse is within the visible edge area."""
        if not self._is_docked:
            if hasattr(self, "_edge_poll_timer"):
                self._edge_poll_timer.stop()
            return

        from PySide6.QtGui import QCursor

        cursor_pos = QCursor.pos()
        widget_rect = self.geometry()

        # Expand the detection zone by 15px to make it easier to hit
        detection = widget_rect.adjusted(-15, -15, 15, 15)

        if detection.contains(cursor_pos):
            self._restore_from_edge()
            if hasattr(self, "_edge_poll_timer"):
                self._edge_poll_timer.stop()

    # -- Refresh logic --

    def do_refresh(self):
        """Trigger an API refresh cycle."""
        if self._refreshing:
            return
        if not self.client.api_key:
            self.set_status("No API Key", GRAY)
            return

        self._refreshing = True
        self._status_dot.setStyleSheet(f"color: {ACCENT_BLUE}; font-size: 12px;")

        # Reset received data
        self._pending_balance: BalanceInfo | None = None
        self._pending_usage: UsageData | None = None

        # Start worker (clean up old connections first)
        if hasattr(self, '_worker') and self._worker is not None:
            try:
                self._worker.finished.disconnect()
            except Exception:
                pass
        self._worker = RefreshWorker(self.client)
        self._worker.balance_ready.connect(self._on_balance_ready)
        self._worker.usage_ready.connect(self._on_usage_ready)
        self._worker.balance_error.connect(self._on_balance_error)
        self._worker.usage_error.connect(self._on_usage_error)
        self._worker.finished.connect(self._on_refresh_finished)
        self._worker.start()

    def _on_balance_ready(self, balance: BalanceInfo):
        """Handle successful balance fetch."""
        self._balance = balance
        self._update_balance_display(balance)

    def _on_usage_ready(self, usage: UsageData):
        """Handle successful usage fetch."""
        self._usage = usage
        self._update_usage_display(usage)

    def _on_balance_error(self, error_msg: str):
        """Handle balance fetch error."""
        logger.warning("Balance error: %s", error_msg)
        if "401" in error_msg or "Invalid" in error_msg:
            self.set_status("Invalid API Key", RED)
        elif "timed out" in error_msg.lower():
            self.set_status("Network Timeout", ORANGE)
        else:
            self.set_status(error_msg[:40], RED if "401" in error_msg else ORANGE)

    def _on_usage_error(self, error_msg: str):
        """Handle usage fetch error — expected since DeepSeek lacks a public endpoint."""
        logger.debug("Usage fetch failed (expected): %s", error_msg)

    def _on_refresh_finished(self):
        """Called when the refresh worker completes."""
        self._refreshing = False
        self._last_refresh_label.setText(
            f"Last refresh: {datetime.now().strftime('%H:%M:%S')}"
        )

        # Determine overall status
        if self._balance is not None:
            total = self._balance.total_balance
            color = health_color(total)
            label = health_label(total)
            self.set_status(label, color)
        else:
            self.set_status("Offline", GRAY)

        worker = self.sender()
        if worker is not None:
            try:
                worker.deleteLater()
            except RuntimeError:
                pass  # C++ object may already be deleted

    # -- Display updates --

    def _update_balance_display(self, balance: BalanceInfo):
        """Update the balance card labels including today's spent."""
        currency_symbol = "¥" if balance.currency == "CNY" else "$"
        self._set_row_value(self._lbl_total, f"{currency_symbol} {balance.total_balance:,.2f}")
        self._set_row_value(self._lbl_topped_up, f"{currency_symbol} {balance.topped_up_balance:,.2f}")
        self._set_row_value(self._lbl_granted, f"{currency_symbol} {balance.granted_balance:,.2f}")

        # -- Calculate today's spent --
        today = datetime.now().strftime("%Y-%m-%d")
        day_start = self.config.day_start_balance
        if day_start is None:
            # First refresh of the day — record current balance as baseline
            self.config.day_start_balance = balance.total_balance
            today_spent = 0.0
        else:
            # Compare current balance to start-of-day baseline
            today_spent = max(0.0, day_start - balance.total_balance)

        self._set_row_value(
            self._lbl_today_spent,
            f"{currency_symbol} {today_spent:,.2f}",
        )

        # Update card border color based on balance health
        color = health_color(balance.total_balance)
        self._balance_card.setStyleSheet(
            f"#infoCard {{ background-color: {CARD_BG}; "
            f"border: 1px solid {color}; border-radius: 6px; "
            f"padding: 8px 12px; margin: 4px 12px; }}"
        )

    # -- Stock refresh --

    # -- Multi-stock refresh --

    def update_stock_codes(self, codes: list[str]):
        """Replace the entire stock card list with new codes."""
        # Stop all running workers
        for code, worker in list(self._stock_workers.items()):
            if worker.isRunning():
                worker.quit()
                worker.wait(1000)
            try:
                worker.finished.disconnect()
                worker.data_ready.disconnect()
                worker.error_occurred.disconnect()
            except (TypeError, RuntimeError):
                pass
            worker.deleteLater()
        self._stock_workers.clear()

        # Remove all existing cards
        for card in list(self._stock_cards.values()):
            self._stock_scroll_content_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._stock_cards.clear()

        # Clear remaining layout items (stretches etc.)
        while self._stock_scroll_content_layout.count():
            item = self._stock_scroll_content_layout.takeAt(0)
            # Discard any remaining items

        # Store new codes
        self._stock_codes = codes

        # Show/hide stock section
        has_stocks = bool(codes)
        self._section_stock_header.setVisible(has_stocks)
        self._stock_scroll.setVisible(has_stocks)

        if not has_stocks:
            return

        # Create a card for each code
        for code in codes:
            card = StockCardWidget(code)
            self._stock_scroll_content_layout.addWidget(card)
            self._stock_cards[code] = card

        # Push cards to top, leave space below
        self._stock_scroll_content_layout.addStretch()

        # Trigger immediate refresh
        self.do_stock_refresh()

    def do_stock_refresh(self):
        """Spawn a StockWorker for every configured stock code in parallel."""
        if not self._stock_codes:
            return

        for code in self._stock_codes:
            # Skip if a worker for this code is already running
            if code in self._stock_workers and self._stock_workers[code].isRunning():
                continue

            worker = StockWorker(code)
            worker.data_ready.connect(self._on_stock_data)
            worker.error_occurred.connect(self._on_stock_error)
            worker.finished.connect(self._on_stock_finished)
            self._stock_workers[code] = worker
            worker.start()

    def _on_stock_data(self, data: StockData):
        """Route incoming stock data to the correct card widget."""
        worker = self.sender()
        if worker is None or not isinstance(worker, StockWorker):
            return
        code = worker.stock_code
        card = self._stock_cards.get(code)
        if card is None:
            logger.debug("Stock data for unknown code: %s", code)
            return
        card.update_data(data)

    def _on_stock_error(self, error_msg: str):
        """Route a stock fetch error to the correct card."""
        worker = self.sender()
        if worker is None or not isinstance(worker, StockWorker):
            return
        code = worker.stock_code
        card = self._stock_cards.get(code)
        if card is not None:
            card.set_error(error_msg)

    def _on_stock_finished(self):
        """Clean up a completed stock worker."""
        worker = self.sender()
        if worker is None or not isinstance(worker, StockWorker):
            return
        code = worker.stock_code
        self._stock_workers.pop(code, None)
        try:
            worker.deleteLater()
        except RuntimeError:
            pass  # C++ object may already be deleted

    def _update_usage_display(self, usage: UsageData):
        """Update the usage card labels."""
        self._set_row_value(self._lbl_api_calls, f"{usage.api_calls:,}")
        self._set_row_value(self._lbl_total_tokens, self._format_tokens(usage.total_tokens))
        self._set_row_value(self._lbl_prompt_tokens, self._format_tokens(usage.prompt_tokens))
        self._set_row_value(self._lbl_completion_tokens, self._format_tokens(usage.completion_tokens))

    def set_status(self, text: str, color: str):
        """Update the status label and dot color."""
        self._status = text
        self._status_color = color
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 12px;")

    @staticmethod
    def _set_row_value(row: QHBoxLayout, text: str):
        """Set the value text in an info row."""
        if hasattr(row, "_value_label"):
            row._value_label.setText(text)  # type: ignore

    @staticmethod
    def _format_tokens(n: int) -> str:
        """Format token count with K/M suffix."""
        if n >= 1_000_000:
            return f"{n / 1_000_000:,.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:,.1f}K"
        return str(n)

    # -- Mouse events for dragging --

    def enterEvent(self, event: QEnterEvent):
        """Restore from docked edge when mouse enters the visible strip."""
        if self._is_docked and not self._dock_animating:
            self._restore_from_edge()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Start auto-hide countdown when mouse leaves the widget."""
        if not self._is_docked and self._auto_hide_enabled:
            self._auto_hide_timer.start()
        super().leaveEvent(event)

    # -- Mouse events (drag, resize, cursor updates) --

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            # 1) Edge resize
            edge = self._get_resize_edge(event.position())
            if edge is not None:
                self._resize_edge = edge
                self._resize_start_geom = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()
                self._drag_offset = None
                return

            # 2) Title bar drag
            if event.position().y() <= TITLE_BAR_HEIGHT:
                self._drag_offset = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
            else:
                self._drag_offset = None

    def mouseMoveEvent(self, event: QMouseEvent):
        # -- Manual resize in progress --
        if self._resize_edge is not None and self._resize_start_geom is not None:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            from PySide6.QtCore import QRect
            geom = QRect(self._resize_start_geom)
            e = self._resize_edge

            if "left" in e:
                geom.setLeft(min(geom.left() + delta.x(), geom.right() - MIN_WINDOW_WIDTH))
            if "right" in e:
                geom.setRight(max(geom.right() + delta.x(), geom.left() + MIN_WINDOW_WIDTH))
            if "top" in e:
                geom.setTop(min(geom.top() + delta.y(), geom.bottom() - MIN_WINDOW_HEIGHT))
            if "bottom" in e:
                geom.setBottom(max(geom.bottom() + delta.y(), geom.top() + MIN_WINDOW_HEIGHT))

            self.setGeometry(geom)
            return

        # -- Window drag --
        if event.buttons() == Qt.LeftButton and self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

        # -- Update cursor for edge proximity --
        edge = self._get_resize_edge(event.position())
        self.setCursor(self._cursor_for_edge(edge))

        # Reset auto-hide timer on any mouse movement
        self._reset_auto_hide_timer()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._resize_edge is not None:
            self._resize_edge = None
            self._resize_start_geom = None
            self._resize_start_pos = None
            # Persist new size
            self.config.window_size = self.size()
            return

        self._drag_offset = None
        # Save position on release (from drag)
        self.config.window_position = self.pos()

    # -- Context menu --

    def contextMenuEvent(self, event):
        """Right-click context menu."""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
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

        refresh_action = QAction("🔄  Refresh Now", menu)
        refresh_action.triggered.connect(self.do_refresh)
        menu.addAction(refresh_action)

        menu.addSeparator()

        settings_action = QAction("⚙  Settings...", menu)
        settings_action.triggered.connect(lambda: self.settings_requested.emit())
        menu.addAction(settings_action)

        menu.addSeparator()

        hide_action = QAction("👁  Hide Window", menu)
        hide_action.triggered.connect(self.hide)
        menu.addAction(hide_action)

        exit_action = QAction("✕  Exit", menu)
        exit_action.triggered.connect(QApplication.quit)
        menu.addAction(exit_action)

        menu.exec(event.globalPos())

    # -- Override close event → hide to tray --

    def closeEvent(self, event):
        """Hide to tray instead of quitting."""
        self.config.save_window_geometry(self)
        self.hide()
        event.ignore()

    def quit_app(self):
        """Actually quit the application."""
        self.config.save_window_geometry(self)
        QApplication.quit()
