"""
Contracts module for inter-module communication.
Provides TypedDict types, channel names, and serializers.
"""

# Types
from .types import (
    CandleDTO,
    HighLowDTO,
    TradeSignalDTO,
    OrderDTO,
    OrderBlockDTO,
    CandleCloseEvent,
    HighLowUpdateEvent,
    TradeSignalEvent,
)

# Channels
from .channels import (
    candle_close_channel,
    realtime_channel,
    hl_updated_channel,
    trade_signal_channel,
    nearest_ob_channel,
    open_long_channel,
    open_short_channel,
)

# Serializers
from .serializers import (
    serialize,
    deserialize,
    to_candle,
    to_signal,
    to_order,
    to_highlow,
    to_hl_event,
    to_trade_signal_event,
)


__all__ = [
    # Types
    "CandleDTO",
    "HighLowDTO",
    "TradeSignalDTO",
    "OrderDTO",
    "OrderBlockDTO",
    "CandleCloseEvent",
    "HighLowUpdateEvent",
    "TradeSignalEvent",
    # Channels
    "candle_close_channel",
    "realtime_channel",
    "hl_updated_channel",
    "trade_signal_channel",
    "nearest_ob_channel",
    "open_long_channel",
    "open_short_channel",
    # Serializers
    "serialize",
    "deserialize",
    "to_candle",
    "to_signal",
    "to_order",
    "to_highlow",
    "to_hl_event",
    "to_trade_signal_event",
]
