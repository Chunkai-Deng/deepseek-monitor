"""Standalone stock card widget — displays a single stock's data with indicators."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from config_manager import save_stock_snapshot
from sparkline_widget import SparklineWidget
from stock_worker import StockData
from styles import GRAY, GREEN, RED


class StockCardWidget(QFrame):
    """A single stock's price, sparkline, and technical indicators."""

    def __init__(self, stock_code: str, parent=None):
        super().__init__(parent)
        self._stock_code = stock_code
        self.setObjectName("stockCard")
        self._setup_ui()

    @property
    def stock_code(self) -> str:
        return self._stock_code

    # -- UI construction --

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Name + code row
        name_row = QHBoxLayout()
        self._name_label = QLabel("...")
        self._name_label.setObjectName("stockNameLabel")
        name_row.addWidget(self._name_label)
        self._code_label = QLabel(f"({self._stock_code})")
        self._code_label.setObjectName("stockCodeLabel")
        name_row.addWidget(self._code_label)
        name_row.addStretch()
        layout.addLayout(name_row)

        # Price + change row
        price_row = QHBoxLayout()
        price_row.setSpacing(8)
        self._price_label = QLabel("¥ ---")
        self._price_label.setObjectName("stockPriceLabel")
        price_row.addWidget(self._price_label)
        self._change_label = QLabel("--")
        self._change_label.setObjectName("stockChangeLabel")
        price_row.addWidget(self._change_label)
        price_row.addStretch()
        layout.addLayout(price_row)

        # Sparkline chart
        self._sparkline = SparklineWidget()
        layout.addWidget(self._sparkline)

        # MA indicators row
        ma_row = QHBoxLayout()
        ma_row.setSpacing(10)
        self._lbl_ma5 = self._make_indicator_pair("MA5")
        self._lbl_ma10 = self._make_indicator_pair("MA10")
        self._lbl_ma20 = self._make_indicator_pair("MA20")
        ma_row.addLayout(self._lbl_ma5)
        ma_row.addLayout(self._lbl_ma10)
        ma_row.addLayout(self._lbl_ma20)
        ma_row.addStretch()
        layout.addLayout(ma_row)

        # Bollinger Bands row
        bb_row = QHBoxLayout()
        bb_row.setSpacing(10)
        self._lbl_bb_up = self._make_indicator_pair("BB上轨")
        self._lbl_bb_lo = self._make_indicator_pair("BB下轨")
        self._lbl_bb_w = self._make_indicator_pair("带宽")
        bb_row.addLayout(self._lbl_bb_up)
        bb_row.addLayout(self._lbl_bb_lo)
        bb_row.addLayout(self._lbl_bb_w)
        bb_row.addStretch()
        layout.addLayout(bb_row)

        # MACD + RSI row
        mr_row = QHBoxLayout()
        mr_row.setSpacing(10)
        self._lbl_macd = self._make_indicator_pair("MACD")
        self._lbl_rsi = self._make_indicator_pair("RSI")
        mr_row.addLayout(self._lbl_macd)
        mr_row.addLayout(self._lbl_rsi)
        mr_row.addStretch()
        layout.addLayout(mr_row)

        # KDJ row
        kdj_row = QHBoxLayout()
        kdj_row.setSpacing(10)
        self._lbl_k = self._make_indicator_pair("K")
        self._lbl_d = self._make_indicator_pair("D")
        self._lbl_j = self._make_indicator_pair("J")
        kdj_row.addLayout(self._lbl_k)
        kdj_row.addLayout(self._lbl_d)
        kdj_row.addLayout(self._lbl_j)
        kdj_row.addStretch()
        layout.addLayout(kdj_row)

        # Support / Resistance row
        sr_row = QHBoxLayout()
        sr_row.setSpacing(10)
        self._lbl_support = self._make_indicator_pair("支撑")
        self._lbl_resist = self._make_indicator_pair("压力")
        sr_row.addLayout(self._lbl_support)
        sr_row.addLayout(self._lbl_resist)
        sr_row.addStretch()
        layout.addLayout(sr_row)

        # Error label (hidden by default)
        self._error_label = QLabel("")
        self._error_label.setObjectName("stockErrorLabel")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # Analysis / prediction label
        self._analysis_label = QLabel("")
        self._analysis_label.setObjectName("stockAnalysisLabel")
        self._analysis_label.setWordWrap(True)
        layout.addWidget(self._analysis_label)

    # -- Data updates --

    def update_data(self, data: StockData):
        self._error_label.setVisible(False)

        # Name + code
        self._name_label.setText(data.name or data.code)
        self._code_label.setText(f"({data.code})" if data.name else "")

        # Price
        self._price_label.setText(f"¥ {data.price:,.2f}")

        # Change
        if data.change_pct >= 0:
            change_text = f"↑ +{data.change_pct:.2f}%  +{data.change_amt:.2f}"
            change_color = RED
        else:
            change_text = f"↓ {data.change_pct:.2f}%  {data.change_amt:.2f}"
            change_color = GREEN
        self._change_label.setText(change_text)
        self._change_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {change_color};"
        )

        # Sparkline
        if data.closes:
            self._sparkline.set_data(data.closes, data.ma5, data.ma10)

        # MA
        self._set_indicator(self._lbl_ma5, data.ma5_val, fmt=".2f")
        self._set_indicator(self._lbl_ma10, data.ma10_val, fmt=".2f")
        self._set_indicator(self._lbl_ma20, data.ma20_val, fmt=".2f")

        # Bollinger
        self._set_indicator(self._lbl_bb_up, data.bb_upper, fmt=".2f")
        self._set_indicator(self._lbl_bb_lo, data.bb_lower, fmt=".2f")
        if data.bb_width_pct is not None:
            self._set_indicator_color(self._lbl_bb_w, f"{data.bb_width_pct:.1f}%", GRAY)
        else:
            self._set_indicator(self._lbl_bb_w, None)

        # MACD
        if data.macd is not None:
            macd_text = f"{data.macd:.2f}"
            macd_color = RED if data.macd > 0 else GREEN
            if data.macd > data.macd_signal if data.macd_signal else 0:
                macd_text += " ↑"
            else:
                macd_text += " ↓"
            self._set_indicator_color(self._lbl_macd, macd_text, macd_color)

        # RSI
        if data.rsi is not None:
            rsi_val = data.rsi
            if rsi_val > 70:
                rsi_text = f"{rsi_val:.1f} 超买"
                rsi_color = GREEN
            elif rsi_val < 30:
                rsi_text = f"{rsi_val:.1f} 超卖"
                rsi_color = RED
            else:
                rsi_text = f"{rsi_val:.1f} 中性"
                rsi_color = GRAY
            self._set_indicator_color(self._lbl_rsi, rsi_text, rsi_color)

        # KDJ
        if data.k is not None and data.d is not None and data.j is not None:
            self._set_indicator(self._lbl_k, data.k, fmt=".1f")
            self._set_indicator(self._lbl_d, data.d, fmt=".1f")
            j_val = data.j
            if j_val > 100:
                self._set_indicator_color(self._lbl_j, f"{j_val:.1f} 高位", GREEN)
            elif j_val < 0:
                self._set_indicator_color(self._lbl_j, f"{j_val:.1f} 低位", RED)
            else:
                self._set_indicator(self._lbl_j, j_val, fmt=".1f")

        # Support / Resistance
        self._set_indicator(self._lbl_support, data.support, fmt=".2f")
        self._set_indicator(self._lbl_resist, data.resistance, fmt=".2f")

        # Analysis
        text, color, score = self._analyze(data)
        self._analysis_label.setText(text)
        self._analysis_label.setStyleSheet(
            f"font-size: 10px; color: {color}; "
            "background-color: rgba(255,255,255,0.04); "
            "border-radius: 4px; padding: 4px 6px; margin-top: 2px;"
        )

        # Persist snapshot
        save_stock_snapshot(
            code=data.code, name=data.name, price=data.price,
            change_pct=data.change_pct,
            ma5_val=data.ma5_val, ma10_val=data.ma10_val, ma20_val=data.ma20_val,
            macd=data.macd, macd_signal=data.macd_signal,
            rsi=data.rsi,
            bb_upper=data.bb_upper, bb_lower=data.bb_lower,
            k=data.k, d=data.d, j=data.j,
            support=data.support, resistance=data.resistance,
            vol_ratio=data.vol_ratio, vol_trend=data.vol_trend,
            weekly_trend=data.weekly_trend,
            prediction=text, score=score,
        )

    def set_error(self, error_msg: str):
        self._error_label.setText(f"⚠ {error_msg}")
        self._error_label.setVisible(True)

    # -- Analysis (plain language) --

    @staticmethod
    def _analyze(data: StockData) -> tuple[str, str, int]:
        """Score all indicators and return (text, color, score)."""
        score = 0
        notes: list[str] = []

        # ---- MA ----
        if data.price and data.ma20_val:
            if data.price > data.ma20_val:
                score += 1
                notes.append("股价站在均线上方，中线趋势向好")
            else:
                score -= 1
                notes.append("股价跌到均线下方，中线走势偏弱")

        if data.ma5_val and data.ma10_val:
            if data.ma5_val > data.ma10_val:
                score += 1
                notes.append("短期均线向上，短线有支撑")
            else:
                score -= 1
                notes.append("短期均线向下，短线承压")

        # ---- MACD ----
        if data.macd is not None and data.macd_signal is not None:
            if data.macd > data.macd_signal:
                score += 1
                notes.append("MACD金叉，多头占优")
            else:
                score -= 1
                notes.append("MACD死叉，空头力量偏强")

        # ---- RSI ----
        if data.rsi is not None:
            if data.rsi < 30:
                score += 1
                notes.append("跌过头了，随时可能反弹")
            elif data.rsi > 70:
                score -= 1
                notes.append("涨太快了，小心短期回调")
            else:
                notes.append("市场情绪正常，没有极端信号")

        # ---- Bollinger ----
        if data.price and data.bb_upper and data.bb_lower:
            if data.price >= data.bb_upper * 0.99:
                score -= 1
                notes.append("价格顶着布林上轨，上方空间有限")
            elif data.price <= data.bb_lower * 1.01:
                score += 1
                notes.append("价格贴着布林下轨，有反弹空间")
            elif data.bb_width_pct is not None and data.bb_width_pct < 5:
                notes.append("布林带收窄，快要变盘了")

        # ---- Volume ----
        if data.vol_trend == "放量":
            notes.append("成交量放大，资金在动")
            if data.change_pct >= 0:
                score += 1
                notes.append("放量上涨，量价配合不错")
            else:
                score -= 1
                notes.append("放量下跌，出货迹象要留意")
        elif data.vol_trend == "缩量":
            notes.append("成交缩量，市场参与度不高")

        # ---- KDJ ----
        if data.j is not None:
            if data.j > 100:
                score -= 1
                notes.append("KDJ高位钝化，追高要谨慎")
            elif data.j < 0:
                score += 1
                notes.append("KDJ在低位区，超跌反弹可期")

        # ---- Weekly trend ----
        if data.weekly_trend == "上涨":
            score += 1
            notes.append("周线也在涨，中线趋势没坏")
        elif data.weekly_trend == "下跌":
            score -= 1
            notes.append("周线是跌的，日线反弹要打折扣")

        # ---- Support / Resistance ----
        if data.price and data.support and data.resistance:
            dist_to_support = (data.price - data.support) / data.support * 100
            dist_to_resist = (data.resistance - data.price) / data.price * 100
            if dist_to_support < 3:
                notes.append(f"离支撑位很近（{dist_to_support:.1f}%），下跌空间不大")
            if dist_to_resist < 3:
                notes.append(f"离压力位不远（{dist_to_resist:.1f}%），突破才能看高")

        # ---- Overall ----
        if score >= 4:
            overall, color = "走势较强，可持有或逢低加仓 ↑", RED
        elif score >= 1:
            overall, color = "震荡偏多，可以继续拿着看看 ↑", RED
        elif score <= -4:
            overall, color = "走势较弱，建议观望或减仓 ↓", GREEN
        elif score <= -1:
            overall, color = "震荡偏弱，等等再说 ↓", GREEN
        else:
            overall, color = "方向不明朗，多看少动 ↔", GRAY

        detail = "；".join(notes) if notes else "数据不够，再等一等"
        return f"{overall}\n{detail}", color, score

    # -- Indicator helpers --

    @staticmethod
    def _make_indicator_pair(label: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)

        lbl = QLabel(label)
        lbl.setObjectName("stockIndicatorLabel")
        row.addWidget(lbl)

        val = QLabel("--")
        val.setObjectName("stockIndicatorValue")
        row.addWidget(val)
        row._value_label = val
        return row

    @staticmethod
    def _set_indicator(row: QHBoxLayout, value: float | None, fmt: str = ".2f"):
        if hasattr(row, "_value_label"):
            if value is not None:
                row._value_label.setText(f"{value:{fmt}}")
            else:
                row._value_label.setText("--")

    @staticmethod
    def _set_indicator_color(row: QHBoxLayout, text: str, color: str):
        if hasattr(row, "_value_label"):
            row._value_label.setText(text)
            row._value_label.setStyleSheet(
                f"font-size: 10px; font-weight: bold; color: {color};"
            )
