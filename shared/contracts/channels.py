"""
Redis channel name functions.
Provides consistent channel naming across all modules.
"""


# =============================================================================
# Data Feed Channels
# =============================================================================

def candle_close_channel(symbol: str) -> str:
    """Channel for candle close notifications."""
    return f"{symbol}_Close_Candle"


def realtime_channel(symbol: str) -> str:
    """Channel for real-time price updates."""
    return f"{symbol}_RealTime"


# =============================================================================
# Indicator Channels
# =============================================================================

def hl_updated_channel(symbol: str) -> str:
    """Channel for High/Low indicator updates."""
    return f"{symbol}_HL_Updated"


# =============================================================================
# Strategy Channels
# =============================================================================

def trade_signal_channel(symbol: str) -> str:
    """Channel for trade signal notifications."""
    return f"{symbol}_Trade_Signal"


def nearest_ob_channel(symbol: str, side: str) -> str:
    """Redis key for nearest Order Block."""
    return f"{symbol}_Nearest_Order_Block_{side}"


# =============================================================================
# Execution Channels
# =============================================================================

def open_long_channel(symbol: str) -> str:
    """Queue for Long position orders."""
    return f"{symbol}_Open_Long_Position"


def open_short_channel(symbol: str) -> str:
    """Queue for Short position orders."""
    return f"{symbol}_Open_Short_Position"
