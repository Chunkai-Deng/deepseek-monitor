"""Configuration persistence: JSON file for settings, .env file for API key.

Storage location (resolved at import time):
  1. Exe/script directory — portable mode (if writable)
  2. %APPDATA%\DeepSeekMonitor — fallback (if exe dir is read-only, e.g. Program Files)

Files:
  - config.json  — window geometry, refresh interval, stock codes, day-start balance
  - .env         — DEEPSEEK_API_KEY (single line)

On first launch, existing data is migrated from the old backends
(QSettings registry + Windows Credential Manager) if present.
"""

import json
import logging
import os
import sys
from datetime import datetime

from PySide6.QtCore import QPoint, QSize

logger = logging.getLogger(__name__)

# -- Resolve the app directory (works for both dev and PyInstaller exe) --
if getattr(sys, "frozen", False):
    _EXE_DIR = os.path.dirname(sys.executable)
else:
    _EXE_DIR = os.path.dirname(os.path.abspath(__file__))


def _is_writable_dir(path: str) -> bool:
    """Check whether we can write files in *path*."""
    probe = os.path.join(path, ".writetest")
    try:
        with open(probe, "w") as f:
            f.write("x")
        os.remove(probe)
        return True
    except OSError:
        return False


def _resolve_config_dir() -> str:
    """Pick the best directory for config files.

    Priority:
      1. Exe/script directory (portable use — config travels with the exe)
      2. %APPDATA%\DeepSeekMonitor (installed use — exe in read-only location)
      3. Exe/script directory anyway (last resort)
    """
    if _is_writable_dir(_EXE_DIR):
        return _EXE_DIR

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        fallback = os.path.join(appdata, "DeepSeekMonitor")
        os.makedirs(fallback, exist_ok=True)
        if _is_writable_dir(fallback):
            logger.info("Config dir fallback: %s", fallback)
            return fallback

    return _EXE_DIR  # last resort


APP_DIR = _resolve_config_dir()
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
ENV_PATH = os.path.join(APP_DIR, ".env")


def _read_env() -> dict[str, str]:
    """Parse .env file into a flat dict. Lines: KEY=VALUE (no quoting needed)."""
    result: dict[str, str] = {}
    if not os.path.exists(ENV_PATH):
        return result
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    result[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        logger.debug("Could not read .env file", exc_info=True)
    return result


def _write_env(key: str, value: str) -> None:
    """Write (or update) a single KEY=VALUE in the .env file."""
    env = _read_env()
    env[key] = value
    lines = [f"{k}={v}" for k, v in env.items()]
    try:
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        logger.warning("Could not write .env file")


def _delete_env(key: str) -> None:
    """Remove a key from the .env file."""
    env = _read_env()
    env.pop(key, None)
    lines = [f"{k}={v}" for k, v in env.items()]
    try:
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            if lines:
                f.write("\n".join(lines) + "\n")
            else:
                f.write("")  # empty file
    except OSError:
        logger.warning("Could not write .env file")


def _read_config() -> dict:
    """Read the full config.json dict, or return empty dict if missing."""
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.debug("Could not parse config.json — starting fresh", exc_info=True)
        return {}


def _write_config(data: dict) -> None:
    """Atomically write config.json."""
    tmp = CONFIG_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)
    except OSError:
        logger.warning("Could not write config.json")


# -- Migration helpers (one-shot) --

def _migrate_from_qsettings(config: dict) -> dict:
    """Pull old settings from Windows registry (QSettings)."""
    try:
        from PySide6.QtCore import QSettings

        old = QSettings("DeepSeekMonitor", "FloatingWidget")

        # Window position
        if old.contains("window/x") and old.contains("window/y"):
            config.setdefault("window", {})
            config["window"]["x"] = int(old.value("window/x"))
            config["window"]["y"] = int(old.value("window/y"))
        # Window size
        w = old.value("window/w")
        h = old.value("window/h")
        if w and h:
            config.setdefault("window", {})
            config["window"]["width"] = int(w)
            config["window"]["height"] = int(h)

        # Refresh interval
        ri = old.value("refresh_interval_seconds")
        if ri is not None:
            config["refresh_interval"] = int(ri)

        # Stock codes
        sc = old.value("stock/codes")
        if sc:
            config["stock_codes"] = str(sc)

        # Day-start balance
        saved_date = old.value("day_start/date")
        today = datetime.now().strftime("%Y-%m-%d")
        if saved_date == today:
            bal = old.value("day_start/balance")
            if bal is not None:
                config["day_start"] = {"date": saved_date, "balance": float(bal)}

        logger.info("Migrated settings from QSettings (registry)")
    except Exception:
        logger.debug("QSettings migration skipped", exc_info=True)
    return config


def _migrate_api_key_from_keyring() -> None:
    """Pull API key from Windows Credential Manager and write to .env."""
    if _read_env().get("DEEPSEEK_API_KEY"):
        return  # .env already has a key — don't overwrite
    try:
        import keyring

        old_key = keyring.get_password("deepseek-usage-monitor", "api_key")
        if old_key:
            _write_env("DEEPSEEK_API_KEY", old_key)
            logger.info("Migrated API key from Credential Manager to .env")
    except Exception:
        # Also try the base64 fallback in QSettings
        try:
            from PySide6.QtCore import QSettings
            import base64

            old_settings = QSettings("DeepSeekMonitor", "FloatingWidget")
            encoded = old_settings.value("api_key_encoded")
            if encoded:
                old_key = base64.b64decode(encoded).decode()
                _write_env("DEEPSEEK_API_KEY", old_key)
                logger.info("Migrated API key from QSettings fallback to .env")
        except Exception:
            logger.debug("Keyring/QSettings migration skipped", exc_info=True)


# ============================================================
#  Public API — identical to the old ConfigManager interface
# ============================================================

class ConfigManager:
    """Manages persistent configuration stored in the app directory.

    - API key  → .env  (DEEPSEEK_API_KEY=...)
    - Settings → config.json
    """

    def __init__(self):
        # One-shot migration on first load
        self._migrate_if_needed()

    # ----------------------------------------------------------
    #  Migration
    # ----------------------------------------------------------

    @staticmethod
    def _migrate_if_needed() -> None:
        """Run migration if config.json doesn't exist yet."""
        if os.path.exists(CONFIG_PATH):
            return

        config = _read_config()
        if config:
            return  # already has content (race-safe)

        config = _migrate_from_qsettings({})
        if config:
            _write_config(config)

        _migrate_api_key_from_keyring()

    # ----------------------------------------------------------
    #  API Key (.env)
    # ----------------------------------------------------------

    @staticmethod
    def save_api_key(key: str) -> None:
        _write_env("DEEPSEEK_API_KEY", key)

    @staticmethod
    def load_api_key() -> str | None:
        return _read_env().get("DEEPSEEK_API_KEY")

    @staticmethod
    def delete_api_key() -> None:
        _delete_env("DEEPSEEK_API_KEY")

    # ----------------------------------------------------------
    #  Window preferences (config.json)
    # ----------------------------------------------------------

    @property
    def window_position(self) -> QPoint | None:
        w = _read_config().get("window", {})
        if "x" in w and "y" in w:
            return QPoint(int(w["x"]), int(w["y"]))
        return None

    @window_position.setter
    def window_position(self, pos: QPoint) -> None:
        cfg = _read_config()
        cfg.setdefault("window", {})
        cfg["window"]["x"] = pos.x()
        cfg["window"]["y"] = pos.y()
        _write_config(cfg)

    @property
    def window_size(self) -> QSize | None:
        w = _read_config().get("window", {})
        if "width" in w and "height" in w:
            return QSize(int(w["width"]), int(w["height"]))
        return None

    @window_size.setter
    def window_size(self, size: QSize) -> None:
        cfg = _read_config()
        cfg.setdefault("window", {})
        cfg["window"]["width"] = size.width()
        cfg["window"]["height"] = size.height()
        _write_config(cfg)

    def save_window_geometry(self, widget) -> None:
        """Convenience: save both position and size from a QWidget."""
        self.window_position = widget.pos()
        self.window_size = widget.size()

    def restore_window_geometry(self, widget) -> None:
        """Convenience: restore position and size to a QWidget."""
        pos = self.window_position
        size = self.window_size
        if pos is not None:
            widget.move(pos)
        if size is not None:
            widget.resize(size)

    # ----------------------------------------------------------
    #  Refresh interval
    # ----------------------------------------------------------

    @property
    def refresh_interval(self) -> int:
        val = _read_config().get("refresh_interval")
        return int(val) if val else 30

    @refresh_interval.setter
    def refresh_interval(self, seconds: int) -> None:
        cfg = _read_config()
        cfg["refresh_interval"] = seconds
        _write_config(cfg)

    # ----------------------------------------------------------
    #  Day-start balance (for "today spent")
    # ----------------------------------------------------------

    @property
    def day_start_balance(self) -> float | None:
        ds = _read_config().get("day_start", {})
        today = datetime.now().strftime("%Y-%m-%d")
        if ds.get("date") == today:
            try:
                return float(ds["balance"])
            except (TypeError, ValueError, KeyError):
                return None
        return None

    @day_start_balance.setter
    def day_start_balance(self, balance: float) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        cfg = _read_config()
        cfg["day_start"] = {"date": today, "balance": balance}
        _write_config(cfg)

    # ----------------------------------------------------------
    #  Stock codes
    # ----------------------------------------------------------

    @property
    def stock_codes(self) -> str:
        return str(_read_config().get("stock_codes", ""))

    @stock_codes.setter
    def stock_codes(self, codes: str) -> None:
        cfg = _read_config()
        cfg["stock_codes"] = codes.strip()
        _write_config(cfg)


# ============================================================
#  Stock history logger (JSON Lines — one record per line)
# ============================================================

STOCK_HISTORY_PATH = os.path.join(APP_DIR, "stock_history.jsonl")


def save_stock_snapshot(
    *,
    code: str,
    name: str,
    price: float,
    change_pct: float,
    ma5_val: float | None,
    ma10_val: float | None,
    ma20_val: float | None,
    macd: float | None,
    macd_signal: float | None,
    rsi: float | None,
    bb_upper: float | None,
    bb_lower: float | None,
    k: float | None,
    d: float | None,
    j: float | None,
    support: float | None,
    resistance: float | None,
    vol_ratio: float | None,
    vol_trend: str,
    weekly_trend: str,
    prediction: str,
    score: int,
) -> None:
    """Append one stock snapshot line to the history file."""
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "code": code,
        "name": name,
        "price": price,
        "change_pct": round(change_pct, 2),
    }
    # Only include indicators that have values
    for key, val in [
        ("ma5", ma5_val), ("ma10", ma10_val), ("ma20", ma20_val),
        ("macd", macd), ("macd_signal", macd_signal),
        ("rsi", rsi),
        ("bb_upper", bb_upper), ("bb_lower", bb_lower),
        ("k", k), ("d", d), ("j", j),
        ("support", support), ("resistance", resistance),
        ("vol_ratio", vol_ratio),
    ]:
        if val is not None:
            record[key] = round(val, 2) if isinstance(val, float) else val
    record["vol_trend"] = vol_trend
    record["weekly_trend"] = weekly_trend
    record["prediction"] = prediction
    record["score"] = score

    try:
        with open(STOCK_HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        logger.debug("Could not write stock history", exc_info=True)
