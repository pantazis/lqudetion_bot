"""Aggregate rolling observation rows into deterministic heatmap tables."""

from __future__ import annotations

from typing import Any

from src.core.constants import NET_LIQ_BUCKETS, PNL_Z_BUCKETS, TIME_BUCKETS


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stats: dict[tuple[int, str, str], dict[str, float]] = {}

    for row in rows:
        key = (int(row["time_left_s"]), row["pnl_z_bucket"], row["net_liq_bucket"])
        bucket = stats.setdefault(key, {"samples": 0.0, "wins": 0.0, "pnl_sum": 0.0})
        bucket["samples"] += 1.0
        bucket["wins"] += 1.0 if int(row.get("win", 0)) == 1 else 0.0
        bucket["pnl_sum"] += _safe_float(row.get("final_pnl_pct", 0.0))

    cells: dict[tuple[int, str, str], dict[str, Any]] = {}
    for key, raw in stats.items():
        samples = int(raw["samples"])
        wins = int(raw["wins"])
        losses = samples - wins
        win_rate = (wins / samples) if samples > 0 else 0.0
        avg_final_pnl_pct = (raw["pnl_sum"] / samples) if samples > 0 else 0.0
        cells[key] = {
            "samples": samples,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "avg_final_pnl_pct": avg_final_pnl_pct,
        }

    tables: dict[str, dict[str, dict[str, Any]]] = {}
    for liq_bucket in NET_LIQ_BUCKETS:
        table: dict[str, dict[str, Any]] = {}
        for time_left in TIME_BUCKETS:
            for pnl_bucket in PNL_Z_BUCKETS:
                key = (time_left, pnl_bucket, liq_bucket)
                if key in cells:
                    table[f"{time_left}__{pnl_bucket}"] = cells[key]
        tables[liq_bucket] = table

    return {
        "rows_loaded": len(rows),
        "tables": tables,
        "cells": cells,
    }
