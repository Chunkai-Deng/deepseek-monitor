"""QThread worker for fetching A-share stock data and calculating indicators.

Data sources:
- Real-time quote: Sina finance (hq.sinajs.cn)
- K-line history: Sina finance (money.finance.sina.com.cn)
- Indicators calculated locally with pandas
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

# Create a dedicated session
_pool = None


def _get_session():
    import requests
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    return s


from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

# -- Prefix logic --
_SH_PREFIXES = ("6",)
_SZ_PREFIXES = ("0", "3")


def _code_prefix(code: str) -> str:
    """Return 'sh' or 'sz' for a given 6-digit A-share code."""
    c = code.strip()
    if c.startswith(_SH_PREFIXES):
        return "sh"
    if c.startswith(_SZ_PREFIXES):
        return "sz"
    return "sh"


@dataclass
class StockData:
    """Parsed stock data ready for display."""

    code: str
    name: str
    price: float
    change_pct: float
    change_amt: float
    currency: str = "¥"

    # Sparkline data (last 30 days)
    closes: list[float] | None = None
    ma5: list[float] | None = None
    ma10: list[float] | None = None

    # MA
    ma5_val: float | None = None
    ma10_val: float | None = None
    ma20_val: float | None = None

    # MACD
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None

    # RSI
    rsi: float | None = None

    # Bollinger Bands (MA20 ± 2σ)
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    bb_width_pct: float | None = None   # bandwidth relative to middle

    # Support / resistance (from 60-day high/low)
    resistance: float | None = None
    support: float | None = None

    # Volume confirmation
    vol_ratio: float | None = None       # latest vol / 20-day avg
    vol_trend: str = ""                   # "放量", "缩量", or ""

    # KDJ
    k: float | None = None
    d: float | None = None
    j: float | None = None

    # ADX (trend strength)
    adx: float | None = None
    plus_di: float | None = None
    minus_di: float | None = None

    # Divergence detection
    divergence: str = ""   # "顶背离", "底背离", ""

    # Weekly trend
    weekly_change_pct: float | None = None
    weekly_trend: str = ""                # "上涨"/"下跌"

    # Error
    error: str | None = None


class StockWorker(QThread):
    """Fetches A-share data via Sina APIs and computes technical indicators."""

    data_ready = Signal(StockData)
    error_occurred = Signal(str)

    def __init__(self, stock_code: str, parent=None):
        super().__init__(parent)
        self.stock_code = stock_code.strip()
        for prefix in ("sh.", "sz.", "SH.", "SZ."):
            if self.stock_code.startswith(prefix):
                self.stock_code = self.stock_code[len(prefix):]
        for suffix in (".SH", ".SZ", ".sh", ".sz"):
            if self.stock_code.endswith(suffix):
                self.stock_code = self.stock_code[:-len(suffix)]

    def run(self):
        try:
            data = self._fetch()
            if data.error:
                self.error_occurred.emit(data.error)
            else:
                self.data_ready.emit(data)
        except Exception as e:
            logger.error("Stock worker exception: %s", e)
            self.error_occurred.emit(str(e))

    def _fetch(self) -> StockData:
        prefix = _code_prefix(self.stock_code)
        symbol = f"{prefix}{self.stock_code}"
        sess = _get_session()

        # -- Step 1: Real-time quote --
        name, price, change_pct, change_amt = self._fetch_quote(sess, symbol)
        if price == 0.0 and not name:
            err = f"Stock {self.stock_code} not found"
            return StockData(code=self.stock_code, name="", price=0, change_pct=0, change_amt=0, error=err)

        # -- Step 2: Daily K-line + indicators --
        daily = self._fetch_kline_indicators(sess, symbol, scale=240, datalen=90)
        if daily is None:
            return StockData(code=self.stock_code, name=name, price=price,
                             change_pct=change_pct, change_amt=change_amt)

        # -- Step 3: Weekly K-line for trend comparison --
        weekly = self._fetch_weekly_trend(sess, symbol)

        # Merge everything
        result = StockData(
            code=self.stock_code, name=name, price=price,
            change_pct=change_pct, change_amt=change_amt,
        )
        # Copy all daily indicator fields
        for fname, fval in daily.items():
            setattr(result, fname, fval)
        # Copy weekly fields
        for fname, fval in weekly.items():
            setattr(result, fname, fval)
        return result

    # ----------------------------------------------------------
    #  Quote
    # ----------------------------------------------------------

    def _fetch_quote(self, sess, symbol: str):
        name = ""
        price = 0.0
        change_pct = 0.0
        change_amt = 0.0
        try:
            r = sess.get(
                f"https://hq.sinajs.cn/list={symbol}",
                timeout=10,
                headers={"Referer": "https://finance.sina.com.cn"},
            )
            if r.status_code == 200 and r.content:
                raw_bytes = r.content
                text = raw_bytes.decode("gbk", errors="replace")
                raw = text.split('"')[1] if '"' in text else ""
                if raw:
                    fields = raw.split(",")
                    if len(fields) > 3:
                        name = fields[0]
                        price = float(fields[3]) if fields[3] else 0.0
                        prev_close = float(fields[2]) if fields[2] else price
                        if prev_close > 0:
                            change_pct = (price - prev_close) / prev_close * 100.0
                            change_amt = price - prev_close
        except Exception as e:
            logger.debug("Sina quote failed: %s", e)
        return name, price, change_pct, change_amt

    # ----------------------------------------------------------
    #  Daily indicators
    # ----------------------------------------------------------

    def _fetch_kline_indicators(self, sess, symbol: str, scale: int, datalen: int) -> dict | None:
        """Fetch K-line and compute all daily indicators."""
        try:
            r = sess.get(
                "https://money.finance.sina.com.cn/quotes_service/api/"
                "json_v2.php/CN_MarketData.getKLineData",
                params={"symbol": symbol, "scale": scale, "ma": "no", "datalen": datalen},
                timeout=10,
            )
            if r.status_code != 200 or not r.text:
                return None

            raw_data = r.json()
            if not raw_data or len(raw_data) < 30:
                return None

            df = pd.DataFrame(raw_data)
            df = df.rename(columns={
                "day": "date", "open": "open", "close": "close",
                "high": "high", "low": "low", "volume": "volume",
            })
            for col in ["open", "close", "high", "low", "volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            close = df["close"].dropna()
            high = df["high"].dropna()
            low = df["low"].dropna()
            volume = df["volume"].dropna()

            if len(close) < 26:
                return None

            # -- Sparkline data --
            closes_list = close.tail(30).tolist()

            # -- MA --
            ma5_s = close.rolling(5).mean()
            ma10_s = close.rolling(10).mean()
            ma20_s = close.rolling(20).mean()
            ma5_list = ma5_s.tail(30).tolist()
            ma10_list = ma10_s.tail(30).tolist()

            # -- MACD --
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_s = ema12 - ema26
            sig_s = macd_s.ewm(span=9, adjust=False).mean()

            # -- RSI --
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta).clip(lower=0).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi_s = 100.0 - (100.0 / (1.0 + rs))

            # -- Bollinger Bands (MA20 ± 2σ) --
            bb_sigma = close.rolling(20).std()
            bb_upper_s = ma20_s + 2 * bb_sigma
            bb_lower_s = ma20_s - 2 * bb_sigma

            # -- KDJ (9,3,3) --
            low9 = low.rolling(9).min()
            high9 = high.rolling(9).max()
            rsv = (close - low9) / (high9 - low9).replace(0, np.nan) * 100.0
            # Iterative smoothing for K/D
            k_vals = [50.0] * 8  # initial seed
            d_vals = [50.0] * 8
            for i in range(8, len(rsv)):
                r = rsv.iloc[i]
                if pd.isna(r):
                    k_vals.append(k_vals[-1])
                    d_vals.append(d_vals[-1])
                else:
                    k_vals.append(2/3 * k_vals[-1] + 1/3 * r)
                    d_vals.append(2/3 * d_vals[-1] + 1/3 * k_vals[-1])
            j_vals = [3*k - 2*d for k, d in zip(k_vals, d_vals)]

            # -- Volume ratio --
            vol_avg20 = volume.rolling(20).mean()
            vol_ratio_s = volume / vol_avg20.replace(0, np.nan)

            # -- Support / resistance (60-day) --
            support_val = float(low.tail(60).min()) if len(low) >= 20 else float(low.min())
            resistance_val = float(high.tail(60).max()) if len(high) >= 20 else float(high.max())

            # Helper
            def _last(s):
                v = s.dropna().iloc[-1] if not s.dropna().empty else np.nan
                return float(v) if not pd.isna(v) else None

            ma5_list = [float(v) if not pd.isna(v) else 0.0 for v in ma5_list]
            ma10_list = [float(v) if not pd.isna(v) else 0.0 for v in ma10_list]

            # Volume trend
            vr = _last(vol_ratio_s) or 1.0
            vol_trend = "放量" if vr > 1.2 else ("缩量" if vr < 0.8 else "")

            # Bollinger width
            bb_m = _last(ma20_s)
            bb_u = _last(bb_upper_s)
            bb_l = _last(bb_lower_s)
            bb_w = ((bb_u - bb_l) / bb_m * 100.0) if bb_m and bb_u and bb_l else None

            # KDJ last values
            k_val = k_vals[-1] if k_vals else None
            d_val = d_vals[-1] if d_vals else None
            j_val = j_vals[-1] if j_vals else None

            # -- ADX (14) --
            adx_val, plus_di, minus_di = self._compute_adx(high, low, close)

            # -- Divergence --
            div_text = self._detect_divergence(close, rsi_s, macd_s)

            return {
                "closes": closes_list,
                "ma5": ma5_list,
                "ma10": ma10_list,
                "ma5_val": _last(ma5_s),
                "ma10_val": _last(ma10_s),
                "ma20_val": _last(ma20_s),
                "macd": _last(macd_s),
                "macd_signal": _last(sig_s),
                "macd_hist": _last(macd_s - sig_s),
                "rsi": _last(rsi_s),
                "bb_upper": bb_u,
                "bb_middle": bb_m,
                "bb_lower": bb_l,
                "bb_width_pct": bb_w,
                "support": support_val,
                "resistance": resistance_val,
                "vol_ratio": vr,
                "vol_trend": vol_trend,
                "k": k_val,
                "d": d_val,
                "j": j_val,
                "adx": adx_val,
                "plus_di": plus_di,
                "minus_di": minus_di,
                "divergence": div_text,
            }

        except Exception as e:
            logger.debug("Sina K-line fetch failed: %s", e)
            return None

    # ----------------------------------------------------------
    #  Weekly trend
    # ----------------------------------------------------------

    def _fetch_weekly_trend(self, sess, symbol: str) -> dict:
        """Fetch weekly K-line to determine medium-term trend."""
        try:
            r = sess.get(
                "https://money.finance.sina.com.cn/quotes_service/api/"
                "json_v2.php/CN_MarketData.getKLineData",
                params={"symbol": symbol, "scale": 1200, "ma": "no", "datalen": 30},
                timeout=10,
            )
            if r.status_code == 200 and r.text:
                raw_data = r.json()
                if raw_data and len(raw_data) >= 4:
                    df = pd.DataFrame(raw_data)
                    df = df.rename(columns={
                        "day": "date", "open": "open", "close": "close",
                        "high": "high", "low": "low", "volume": "volume",
                    })
                    df["close"] = pd.to_numeric(df["close"], errors="coerce")
                    wk_close = df["close"].dropna()
                    if len(wk_close) >= 4:
                        prev = wk_close.iloc[-2]
                        curr = wk_close.iloc[-1]
                        change = (curr - prev) / prev * 100.0 if prev > 0 else 0.0
                        trend = "上涨" if change > 0 else "下跌"
                        return {
                            "weekly_change_pct": change,
                            "weekly_trend": trend,
                        }
        except Exception:
            logger.debug("Weekly K-line fetch failed", exc_info=True)
        return {"weekly_change_pct": None, "weekly_trend": ""}

    # ----------------------------------------------------------
    #  ADX (Average Directional Index)
    # ----------------------------------------------------------

    @staticmethod
    def _compute_adx(high, low, close, period: int = 14):
        """Compute ADX, +DI, -DI using Wilder's smoothing."""
        try:
            h = high.values if hasattr(high, 'values') else high
            l = low.values if hasattr(low, 'values') else low
            c = close.values if hasattr(close, 'values') else close
        except Exception:
            return None, None, None

        if len(h) < period + 2:
            return None, None, None

        # True Range
        tr = np.maximum(
            h[1:] - l[1:],
            np.maximum(
                np.abs(h[1:] - c[:-1]),
                np.abs(l[1:] - c[:-1]),
            ),
        )

        # Directional Movement
        up_move = h[1:] - h[:-1]
        down_move = l[:-1] - l[1:]
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        # Wilder's smoothing (equivalent to EMA with alpha = 1/period)
        alpha = 1.0 / period
        atr = np.zeros_like(tr); atr[0] = tr[0]
        pdi_raw = np.zeros_like(tr); pdi_raw[0] = plus_dm[0]
        mdi_raw = np.zeros_like(tr); mdi_raw[0] = minus_dm[0]

        for i in range(1, len(tr)):
            atr[i] = atr[i-1] * (1 - alpha) + tr[i] * alpha
            pdi_raw[i] = pdi_raw[i-1] * (1 - alpha) + plus_dm[i] * alpha
            mdi_raw[i] = mdi_raw[i-1] * (1 - alpha) + minus_dm[i] * alpha

        plus_di = np.where(atr > 0, 100 * pdi_raw / atr, 0.0)
        minus_di = np.where(atr > 0, 100 * mdi_raw / atr, 0.0)
        denom = plus_di + minus_di
        dx = np.zeros_like(plus_di)
        mask = denom > 0
        dx[mask] = 100 * np.abs(plus_di[mask] - minus_di[mask]) / denom[mask]

        # Smooth DX to get ADX
        adx = np.zeros_like(dx); adx[0] = dx[0]
        for i in range(1, len(dx)):
            adx[i] = adx[i-1] * (1 - alpha) + dx[i] * alpha

        last_adx = float(adx[-1]) if not np.isnan(adx[-1]) else None
        last_pdi = float(plus_di[-1]) if not np.isnan(plus_di[-1]) else None
        last_mdi = float(minus_di[-1]) if not np.isnan(minus_di[-1]) else None
        return last_adx, last_pdi, last_mdi

    # ----------------------------------------------------------
    #  Divergence detection
    # ----------------------------------------------------------

    @staticmethod
    def _detect_divergence(close, rsi_s, macd_s, window: int = 5):
        """Detect RSI/MACD divergence against price."""
        try:
            c = close.values if hasattr(close, 'values') else close
            r = rsi_s.values if hasattr(rsi_s, 'values') else rsi_s
            m = macd_s.values if hasattr(macd_s, 'values') else macd_s
        except Exception:
            return ""

        valid = np.isfinite(c) & np.isfinite(r) & np.isfinite(m)
        c, r, m = c[valid], r[valid], m[valid]
        if len(c) < 20:
            return ""

        # Find local peaks in the last 30 bars
        tail = min(30, len(c))
        c_tail = c[-tail:]
        r_tail = r[-tail:]
        m_tail = m[-tail:]

        peaks, troughs = _find_swings(c_tail, window)
        _, r_peaks = _find_swings(r_tail, window)
        r_troughs = []
        # RSI troughs: invert and find peaks
        r_inv = -r_tail
        _, r_troughs = _find_swings(r_inv, window)

        _, m_peaks = _find_swings(m_tail, window)
        m_inv = -m_tail
        _, m_troughs = _find_swings(m_inv, window)

        # Top divergence: price higher high, RSI/MACD lower high
        if len(peaks) >= 2:
            i1, i2 = peaks[-2], peaks[-1]
            if c_tail[i2] > c_tail[i1]:
                rsi_div = any(abs(p - i2) <= 2 for p in r_peaks) and \
                    any(abs(p - i1) <= 2 for p in r_peaks) and \
                    r_tail[i2] < r_tail[i1]
                macd_div = any(abs(p - i2) <= 2 for p in m_peaks) and \
                    any(abs(p - i1) <= 2 for p in m_peaks) and \
                    m_tail[i2] < m_tail[i1]
                if rsi_div or macd_div:
                    return "顶背离"

        # Bottom divergence: price lower low, RSI/MACD higher low
        if len(troughs) >= 2:
            i1, i2 = troughs[-2], troughs[-1]
            if c_tail[i2] < c_tail[i1]:
                rsi_div = any(abs(t - i2) <= 2 for t in r_troughs) and \
                    any(abs(t - i1) <= 2 for t in r_troughs) and \
                    r_tail[i2] > r_tail[i1]
                macd_div = any(abs(t - i2) <= 2 for t in m_troughs) and \
                    any(abs(t - i1) <= 2 for t in m_troughs) and \
                    m_tail[i2] > m_tail[i1]
                if rsi_div or macd_div:
                    return "底背离"

        return ""


def _find_swings(data, window: int = 5):
    """Find local peaks and troughs in a 1-d array."""
    peaks = []
    troughs = []
    for i in range(window, len(data) - window):
        left = data[i - window:i]
        right = data[i + 1:i + window + 1]
        if data[i] >= max(left) and data[i] > max(right):
            peaks.append(i)
        if data[i] <= min(left) and data[i] < min(right):
            troughs.append(i)
    return peaks, troughs
