"""Mini K-line sparkline chart drawn with QPainter."""

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush
from PySide6.QtWidgets import QWidget

from styles import CARD_BG, GREEN, RED, TEXT_SECONDARY, ACCENT_BLUE


class SparklineWidget(QWidget):
    """A compact line chart showing closing prices with MA overlays.

    Size: approximately 260x70 pixels.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(250, 65)
        self.setMaximumHeight(75)
        self._closes: list[float] = []
        self._ma5: list[float] = []
        self._ma10: list[float] = []

    def set_data(
        self,
        closes: list[float],
        ma5: list[float] | None = None,
        ma10: list[float] | None = None,
    ):
        """Update the chart data and redraw."""
        self._closes = closes
        self._ma5 = ma5 or []
        self._ma10 = ma10 or []
        self.update()

    def paintEvent(self, event):
        if not self._closes or len(self._closes) < 2:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin_h = 2
        margin_v = 4

        # -- Determine color (Chinese convention: red = up, green = down) --
        first = self._closes[0]
        last = self._closes[-1]
        if last >= first:
            line_color = QColor(RED)
            fill_top_color = QColor(244, 67, 54, 40)
            fill_bot_color = QColor(244, 67, 54, 5)
        else:
            line_color = QColor(GREEN)
            fill_top_color = QColor(76, 175, 80, 40)
            fill_bot_color = QColor(76, 175, 80, 5)

        # -- Value range --
        all_values = list(self._closes)
        if self._ma5:
            all_values.extend([v for v in self._ma5 if v > 0])
        if self._ma10:
            all_values.extend([v for v in self._ma10 if v > 0])

        vmin = min(all_values)
        vmax = max(all_values)
        vrange = vmax - vmin
        if vrange == 0:
            vrange = 1

        # -- Helper: map value → y coordinate --
        def to_y(v: float) -> float:
            ratio = (v - vmin) / vrange
            return margin_v + (h - 2 * margin_v) * (1.0 - ratio)

        def to_x(i: int) -> float:
            ratio = i / (len(self._closes) - 1) if len(self._closes) > 1 else 0
            return margin_h + (w - 2 * margin_h) * ratio

        n = len(self._closes)

        # -- Draw gradient fill under the line --
        path = QPainterPath()
        path.moveTo(to_x(0), h - margin_v)
        for i in range(n):
            path.lineTo(QPointF(to_x(i), to_y(self._closes[i])))
        path.lineTo(to_x(n - 1), h - margin_v)
        path.closeSubpath()

        # Gradient fill
        gradient_rect = QRectF(0, margin_v, w, h - margin_v)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill_top_color)
        painter.drawPath(path)

        # -- Draw closing price line --
        pen = QPen(line_color)
        pen.setWidth(1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(n - 1):
            x1 = to_x(i)
            y1 = to_y(self._closes[i])
            x2 = to_x(i + 1)
            y2 = to_y(self._closes[i + 1])
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # -- Draw MA5 line (dashed, blue) --
        if self._ma5 and len(self._ma5) == n:
            ma_color = QColor(ACCENT_BLUE)
            ma_color.setAlpha(180)
            pen = QPen(ma_color)
            pen.setWidth(1.0)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            for i in range(n - 1):
                v1, v2 = self._ma5[i], self._ma5[i + 1]
                if v1 > 0 and v2 > 0:
                    painter.drawLine(
                        QPointF(to_x(i), to_y(v1)),
                        QPointF(to_x(i + 1), to_y(v2)),
                    )

        # -- Draw MA10 line (dotted, orange) --
        if self._ma10 and len(self._ma10) == n:
            ma_color = QColor(255, 152, 0)
            ma_color.setAlpha(160)
            pen = QPen(ma_color)
            pen.setWidth(1.0)
            pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(pen)
            for i in range(n - 1):
                v1, v2 = self._ma10[i], self._ma10[i + 1]
                if v1 > 0 and v2 > 0:
                    painter.drawLine(
                        QPointF(to_x(i), to_y(v1)),
                        QPointF(to_x(i + 1), to_y(v2)),
                    )

        painter.end()
