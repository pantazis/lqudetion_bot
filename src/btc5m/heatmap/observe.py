"""Observation row writing utilities for heatmap JSONL logs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.core.constants import REQUIRED_OBSERVATION_FIELDS


def append_observation_row(
    path: str | Path,
    row: dict[str, Any],
    logger: logging.Logger | None = None,
) -> bool:
    """Append one observation row if it satisfies required schema."""
    logger = logger or logging.getLogger(__name__)
    missing = [field for field in REQUIRED_OBSERVATION_FIELDS if field not in row]
    if missing:
        logger.warning("Not appending observation row; missing fields: %s", missing)
        return False

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return True
