"""
JSON serialization/deserialization functions.
Handles datetime conversion for Redis/MongoDB communication.
"""
import json
from datetime import datetime
from typing import Any, TypeVar, Type

from .types import (
    CandleDTO,
    TradeSignalDTO,
    OrderDTO,
    HighLowDTO,
    HighLowUpdateEvent,
    TradeSignalEvent,
)


T = TypeVar('T')


# =============================================================================
# Core Serialization
# =============================================================================

def serialize(data: dict) -> str:
    """Convert dict to JSON string, converting datetime to isoformat."""
    def convert(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj
    
    converted = {k: convert(v) for k, v in data.items()}
    return json.dumps(converted)


def deserialize(raw: str) -> dict:
    """Parse JSON string to dict."""
    return json.loads(raw)


# =============================================================================
# DTO Converters
# =============================================================================

def to_candle(raw: dict) -> CandleDTO:
    """Convert raw dict to CandleDTO."""
    return CandleDTO(
        symbol=raw.get("symbol", ""),
        open_time=_parse_datetime(raw.get("open_time") or raw.get("Open_time")),
        open=float(raw.get("open") or raw.get("Open", 0)),
        high=float(raw.get("high") or raw.get("High", 0)),
        low=float(raw.get("low") or raw.get("Low", 0)),
        close=float(raw.get("close") or raw.get("Close", 0)),
    )


def to_signal(raw: dict) -> TradeSignalDTO:
    """Convert raw dict to TradeSignalDTO."""
    return TradeSignalDTO(
        symbol=raw.get("symbol", ""),
        side=raw.get("side", "Long"),
        entry_price=float(raw.get("entry_price") or raw.get("entry", 0)),
        stop_loss=float(raw.get("stop_loss", 0)),
        take_profit=float(raw.get("take_profit", 0)),
        pattern=raw.get("pattern", ""),
        timestamp=_parse_datetime(raw.get("timestamp")),
    )


def to_order(raw: dict) -> OrderDTO:
    """Convert raw dict to OrderDTO."""
    return OrderDTO(
        symbol=raw.get("symbol", ""),
        side=raw.get("Side", raw.get("side", "Long")),
        entry_price=float(raw.get("Entry_Price") or raw.get("entry_price", 0)),
        stop_loss=float(raw.get("Stop_Loss") or raw.get("stop_loss", 0)),
        open_time=_parse_datetime(raw.get("Open_time") or raw.get("open_time")),
    )


def to_highlow(raw: dict) -> HighLowDTO:
    """Convert raw dict to HighLowDTO."""
    hl_type = int(raw.get("Type") or raw.get("type", 0))
    return HighLowDTO(
        symbol=raw.get("symbol", ""),
        open_time=_parse_datetime(raw.get("Open_time") or raw.get("open_time")),
        price=float(raw.get("Price") or raw.get("price", 0)),
        type=hl_type,
        side="High" if hl_type == 1 else "Low",
    )


def to_hl_event(raw: dict) -> HighLowUpdateEvent:
    """Convert raw dict to HighLowUpdateEvent."""
    return HighLowUpdateEvent(
        symbol=raw.get("symbol", ""),
        type=raw.get("type", "new"),
        side=raw.get("side", "High"),
    )


def to_trade_signal_event(raw: dict) -> TradeSignalEvent:
    """Convert raw dict to TradeSignalEvent."""
    return TradeSignalEvent(
        symbol=raw.get("symbol", ""),
        side=raw.get("side", "Long"),
        entry=float(raw.get("entry", 0)),
        stop_loss=float(raw.get("stop_loss", 0)),
        take_profit=float(raw.get("take_profit", 0)),
        pattern=raw.get("pattern", ""),
        timestamp=int(raw.get("timestamp", 0)),
    )


# =============================================================================
# Helpers
# =============================================================================

def _parse_datetime(value: Any) -> datetime:
    """Parse datetime from various formats."""
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    if isinstance(value, (int, float)):
        # Assume milliseconds timestamp
        return datetime.fromtimestamp(value / 1000)
    return datetime.now()
