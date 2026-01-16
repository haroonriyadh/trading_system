"""
Type definitions for inter-module communication.
Uses TypedDict for FP-style type safety without classes.
"""
from typing import TypedDict, Literal
from datetime import datetime


# =============================================================================
# Candle Types
# =============================================================================

class CandleDTO(TypedDict):
    """Candlestick data structure."""
    symbol: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float


# =============================================================================
# High/Low Indicator Types
# =============================================================================

class HighLowDTO(TypedDict):
    """High/Low point data structure."""
    symbol: str
    open_time: datetime
    price: float
    type: Literal[0, 1]  # 0=Low, 1=High
    side: Literal["High", "Low"]


# =============================================================================
# Trade Signal Types
# =============================================================================

class TradeSignalDTO(TypedDict):
    """Trade signal from strategy engine."""
    symbol: str
    side: Literal["Long", "Short"]
    entry_price: float
    stop_loss: float
    take_profit: float
    pattern: str
    timestamp: datetime


# =============================================================================
# Order Types
# =============================================================================

class OrderDTO(TypedDict):
    """Order data for execution engine."""
    symbol: str
    side: Literal["Long", "Short"]
    entry_price: float
    stop_loss: float
    open_time: datetime


class OrderBlockDTO(TypedDict):
    """Order Block data structure."""
    symbol: str
    open_time: datetime
    side: Literal["Long", "Short"]
    entry_price: float
    stop_loss: float
    mitigated: Literal[0, 1]


# =============================================================================
# Event Types (Redis Pub/Sub)
# =============================================================================

class CandleCloseEvent(TypedDict):
    """Emitted when a candle closes."""
    symbol: str
    timestamp: datetime


class HighLowUpdateEvent(TypedDict):
    """Emitted when High/Low indicator updates."""
    symbol: str
    type: Literal["new", "update"]
    side: Literal["High", "Low"]


class TradeSignalEvent(TypedDict):
    """Emitted when strategy detects a pattern."""
    symbol: str
    side: Literal["Long", "Short", "Bull", "Bear"]
    entry: float
    stop_loss: float
    take_profit: float
    pattern: str
    timestamp: int
