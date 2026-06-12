"""QSS stylesheets and color constants for the floating widget."""

# -- Color Palette --
GREEN = "#4CAF50"
ORANGE = "#FF9800"
RED = "#F44336"
GRAY = "#9E9E9E"
WHITE = "#FFFFFF"
DARK_BG = "#1E1E2E"
CARD_BG = "#2A2A3C"
TITLE_BG = "#16162A"
TEXT_PRIMARY = "#E0E0E0"
TEXT_SECONDARY = "#A0A0B0"
BORDER = "#3A3A4E"
ACCENT_BLUE = "#5B9BD5"

# -- Window dimensions --
MIN_WINDOW_WIDTH = 320
MIN_WINDOW_HEIGHT = 300
DEFAULT_WINDOW_WIDTH = 320
DEFAULT_WINDOW_HEIGHT = 440
TITLE_BAR_HEIGHT = 32
RESIZE_MARGIN = 8

# -- Balance health thresholds --
BALANCE_HEALTHY = 50.0    # > 50 = green
BALANCE_LOW = 10.0        # 10-50 = orange, < 10 = red


def health_color(total_balance: float | None) -> str:
    """Return the status color for a given balance amount."""
    if total_balance is None:
        return GRAY
    if total_balance > BALANCE_HEALTHY:
        return GREEN
    if total_balance > BALANCE_LOW:
        return ORANGE
    return RED


def health_label(total_balance: float | None) -> str:
    """Return a human-readable status label for a given balance amount."""
    if total_balance is None:
        return "Unknown"
    if total_balance > BALANCE_HEALTHY:
        return "Healthy"
    if total_balance > BALANCE_LOW:
        return "Low Balance"
    return "Critical"


# -- Main window stylesheet --
MAIN_STYLE = f"""
/* Main floating window */
#centralWidget {{
    background-color: {DARK_BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

/* Title bar */
#titleBar {{
    background-color: {TITLE_BG};
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 4px 8px;
}}

#titleLabel {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    font-weight: bold;
}}

#statusDot {{
    font-size: 14px;
}}

/* Control buttons in title bar */
QPushButton#minimizeBtn, QPushButton#closeBtn {{
    background: transparent;
    border: none;
    color: {TEXT_SECONDARY};
    font-size: 14px;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 4px;
}}
QPushButton#minimizeBtn:hover, QPushButton#closeBtn:hover {{
    background-color: {BORDER};
}}
QPushButton#closeBtn:hover {{
    background-color: {RED};
    color: white;
}}

/* Section headers */
#sectionHeader {{
    color: {TEXT_SECONDARY};
    font-size: 10px;
    font-weight: bold;
    text-transform: uppercase;
    padding: 6px 12px 2px 12px;
}}

/* Info cards (balance, usage) */
#infoCard {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    margin: 4px 12px;
}}

#infoRow {{
    padding: 2px 0px;
}}

#infoLabel {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
}}

#infoValue {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    font-weight: bold;
}}

#todaySpentLabel {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
}}

#todaySpentValue {{
    color: {ACCENT_BLUE};
    font-size: 12px;
    font-weight: bold;
}}

#balanceDivider {{
    border: none;
    border-top: 1px solid {BORDER};
    margin: 2px 0px;
}}

/* Status bar at bottom */
#statusBar {{
    padding: 4px 12px;
    border-top: 1px solid {BORDER};
}}

#lastRefreshLabel {{
    color: {TEXT_SECONDARY};
    font-size: 10px;
}}

#statusLabel {{
    font-size: 10px;
    font-weight: bold;
}}

/* Stock card */
#stockCard {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    margin: 4px 12px;
}}

#stockNameLabel {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    font-weight: bold;
}}

#stockCodeLabel {{
    color: {TEXT_SECONDARY};
    font-size: 10px;
}}

#stockPriceLabel {{
    color: {TEXT_PRIMARY};
    font-size: 16px;
    font-weight: bold;
}}

#stockChangeLabel {{
    font-size: 12px;
    font-weight: bold;
}}

#stockIndicatorRow {{
    padding: 1px 0px;
}}

#stockIndicatorLabel {{
    color: {TEXT_SECONDARY};
    font-size: 10px;
}}

#stockIndicatorValue {{
    color: {TEXT_PRIMARY};
    font-size: 10px;
    font-weight: bold;
}}

#stockErrorLabel {{
    color: {GRAY};
    font-size: 11px;
    padding: 8px;
}}

#stockAnalysisLabel {{
    color: {GRAY};
    font-size: 10px;
    padding: 4px 2px 2px 2px;
}}

/* Scroll area for stock cards */
#stockScrollArea {{
    background-color: transparent;
    border: none;
}}

#stockScrollContent {{
    background-color: transparent;
}}

QScrollArea QScrollBar:vertical {{
    background-color: {DARK_BG};
    width: 5px;
    margin: 2px 1px;
    border-radius: 2px;
}}

QScrollArea QScrollBar::handle:vertical {{
    background-color: {BORDER};
    min-height: 20px;
    border-radius: 2px;
}}

QScrollArea QScrollBar::add-line:vertical,
QScrollArea QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
}}

QScrollArea QScrollBar::add-page:vertical,
QScrollArea QScrollBar::sub-page:vertical {{
    background: none;
}}
"""
