"""Shared liquidation parsing/filtering helpers adapted from repo module logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedLiquidationEvent:
    """Normalized liquidation event derived from Binance force-order payloads."""

    symbol: str
    side_kind: str
    usd_size: float


def classify_binance_liq_side(binance_side: str) -> str | None:
    """Map Binance side to liquidation-side semantics from the repo module.

    - SELL -> long_liquidated (bearish pressure)
    - BUY  -> short_liquidated (bullish pressure)
    """

    side = str(binance_side).upper().strip()
    if side == "SELL":
        return "long_liquidated"
    if side == "BUY":
        return "short_liquidated"
    return None


def signed_net_liq_usd(side_kind: str, usd_size: float) -> float:
    """Convert normalized side to signed net liquidation value.

    Positive means bullish pressure (shorts liquidated),
    negative means bearish pressure (longs liquidated).
    """

    if side_kind == "short_liquidated":
        return float(usd_size)
    if side_kind == "long_liquidated":
        return -float(usd_size)
    return 0.0


def is_significant_liq_event(usd_size: float, threshold_usd: float) -> bool:
    """Threshold classifier adapted from repo EventFilter logic."""

    return float(usd_size) >= float(threshold_usd)


def normalize_force_order_payload(payload: dict[str, Any]) -> NormalizedLiquidationEvent | None:
    """Normalize Binance forceOrder payload (WebSocket style) into a compact event."""

    order = payload.get("o")
    if not isinstance(order, dict):
        return None

    symbol = str(order.get("s", "")).upper().strip()
    side_kind = classify_binance_liq_side(str(order.get("S", "")))
    if not side_kind:
        return None

    # Prefer filled quantity * average price; fallback to qty * price.
    qty = float(order.get("z", 0.0) or order.get("q", 0.0) or 0.0)
    price = float(order.get("ap", 0.0) or order.get("p", 0.0) or 0.0)
    usd_size = qty * price

    if not symbol or qty <= 0 or price <= 0 or usd_size <= 0:
        return None

    return NormalizedLiquidationEvent(symbol=symbol, side_kind=side_kind, usd_size=usd_size)
