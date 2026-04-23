"""Decision engine: current_state -> lookup -> win_rate -> decision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DecisionResult:
    action: str
    reason: str
    confidence: str
    win_rate: float | None
    samples: int
    suggested_size_scale: float


def _confidence_from_samples(samples: int) -> str:
    if samples < 30:
        return "unreliable"
    if samples < 50:
        return "weak"
    if samples >= 100:
        return "reliable"
    return "moderate"


def decide_from_state(
    aggregate_payload: dict[str, Any],
    state: tuple[int, str, str],
    min_win_rate: float = 0.58,
) -> DecisionResult:
    cells = aggregate_payload.get("cells", {})
    cell = cells.get(state)
    if not cell:
        return DecisionResult(
            action="NO_TRADE",
            reason="state_missing",
            confidence="unreliable",
            win_rate=None,
            samples=0,
            suggested_size_scale=0.0,
        )

    samples = int(cell.get("samples", 0))
    win_rate = float(cell.get("win_rate", 0.0))
    confidence = _confidence_from_samples(samples)

    if samples < 30:
        return DecisionResult(
            action="NO_TRADE",
            reason="low_samples_lt_30",
            confidence=confidence,
            win_rate=win_rate,
            samples=samples,
            suggested_size_scale=0.0,
        )

    if win_rate < min_win_rate:
        return DecisionResult(
            action="NO_TRADE",
            reason="win_rate_below_threshold",
            confidence=confidence,
            win_rate=win_rate,
            samples=samples,
            suggested_size_scale=0.0,
        )

    size_scale = 0.5 if confidence in {"weak", "moderate"} else 1.0
    return DecisionResult(
        action="ENTER",
        reason="state_qualified",
        confidence=confidence,
        win_rate=win_rate,
        samples=samples,
        suggested_size_scale=size_scale,
    )
