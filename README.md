# DeepSeek Monitor

A Windows desktop floating widget that shows real-time DeepSeek API usage and A-share stock data with technical analysis.

## Features

### Balance Monitor
- Real-time DeepSeek API balance display (Total / Top-up / Granted)
- Today's spend calculated from day-start balance baseline
- Health status indicator with color coding

### Stock Tracker
- Real-time A-share quotes via Sina Finance API
- Mini K-line sparkline chart with MA overlays
- Technical indicators: MA5/10/20, MACD, RSI, Bollinger Bands, KDJ
- Support & resistance levels, volume confirmation
- Multi-period trend comparison (daily + weekly)
- Plain-language AI prediction with composite scoring

### Window
- Frameless, always-on-top, semi-transparent
- Auto-hide to nearest screen edge after 5 seconds of inactivity
- Resizable with native edge drag
- System tray integration
- Dark theme

## Screenshot

```
┌─────────────────────────────────┐
│  🟢 DeepSeek Usage      [—] [×] │
├─────────────────────────────────┤
│  💰  BALANCE                     │
│  ┌───────────────────────────┐  │
│  │ Total:    ¥ 1,234.56      │  │
│  │ Top-up:   ¥ 1,000.00      │  │
│  │ Granted:  ¥ 234.56        │  │
│  │ ──────────────────────     │  │
│  │ Today Spent: ¥ 2.50       │  │
│  └───────────────────────────┘  │
│  📈  STOCK                       │
│  ┌───────────────────────────┐  │
│  │ 贵州茅台 (600519)          │  │
│  │ ¥ 1291.91 ↑ +0.24%        │  │
│  │ [mini K-line chart]       │  │
│  │ MA5:1273 MA10:1281 MA20:1292│ │
│  │ BB上轨:1335 BB下轨:1248   │  │
│  │ MACD:-24.12↑ RSI:51.3     │  │
│  │ K:38 D:33 J:48            │  │
│  │ 支撑:1250 压力:1498       │  │
│  │ 📊 震荡偏多，可持有 ↑     │  │
│  └───────────────────────────┘  │
│  🔄 Last refresh: 14:32:05      │
│  ⚡ Status: Healthy              │
└─────────────────────────────────┘
```

## Installation

### From Source

```bash
pip install -r requirements.txt
python main.py
```

### Build Standalone EXE

```bash
build.bat
```

Output: `dist/DeepSeekMonitor.exe`

## Configuration

All settings are stored in the app directory:

| File | Purpose |
|---|---|
| `.env` | DeepSeek API key (`DEEPSEEK_API_KEY=sk-...`) |
| `config.json` | Window geometry, refresh interval, stock codes |
| `stock_history.jsonl` | Historical snapshots (auto-generated) |

### Settings

Right-click the widget → **Settings** to configure:

- **API Key**: Your DeepSeek API key (from [platform.deepseek.com](https://platform.deepseek.com))
- **Refresh Interval**: 5–300 seconds
- **Stock Codes**: Comma-separated A-share codes, e.g. `600519,000858,300750`

## Data Sources

| Data | Source |
|---|---|
| DeepSeek balance | `api.deepseek.com/user/balance` |
| A-share real-time quotes | `hq.sinajs.cn` (Sina Finance) |
| K-line history | `money.finance.sina.com.cn` (Sina Finance) |

All technical indicators (MA, MACD, RSI, Bollinger Bands, KDJ) are computed locally with pandas.

## Tech Stack

- **Python 3.10+**
- **PySide6** — Qt for Python
- **requests** — HTTP client
- **pandas / numpy** — indicator calculations
- **PyInstaller** — standalone EXE packaging

## License

MIT
