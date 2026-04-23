"""State construction helpers for BTC 5m decision lookup."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from src.core.constants import TIME_BUCKETS


def bucket_time_left_5m(now_utc: datetime | None = None) -> int:
    now_utc = now_utc or datetime.now(timezone.utc)
    elapsed = (now_utc.minute % 5) * 60 + now_utc.second
    remaining = max(0, 300 - elapsed)
    for bucket in TIME_BUCKETS:
        if remaining >= bucket:
            return bucket
    return 0


def bucket_pnl_z(z_score: float) -> str:
    if z_score < -2.0:
        return "lt_neg_2"
    if z_score < -1.0:
        return "neg_2_to_neg_1"
    if z_score < -0.3:
        return "neg_1_to_neg_0_3"
    if z_score < 0.3:
        return "neg_0_3_to_0_3"
    if z_score < 1.0:
        return "pos_0_3_to_1"
    if z_score < 2.0:
        return "pos_1_to_2"
    return "gt_2"


def bucket_net_liq(net_liq: float, weak_threshold: float, strong_threshold: float) -> str:
    if net_liq <= -strong_threshold:
        return "strong_minus"
    if net_liq <= -weak_threshold:
        return "weak_minus"
    if net_liq >= strong_threshold:
        return "strong_plus"
    if net_liq >= weak_threshold:
        return "weak_plus"
    return "neutral"


def z_score(value: float, history: Iterable[float]) -> float:
    values = [float(v) for v in history]
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = variance ** 0.5
    if std == 0:
        return 0.0
    return (value - mean) / std
