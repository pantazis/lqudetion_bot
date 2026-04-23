"""Read and validate rolling heatmap observation logs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.core.constants import NET_LIQ_BUCKETS, PNL_Z_BUCKETS, REQUIRED_OBSERVATION_FIELDS, TIME_BUCKETS


def _tail_non_empty_lines(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []

    with path.open("rb") as f:
        f.seek(0, 2)
        end = f.tell()
        block_size = 4096
        data = b""
        lines: list[bytes] = []
        cursor = end

        while cursor > 0 and len(lines) <= n * 2:
            read_size = min(block_size, cursor)
            cursor -= read_size
            f.seek(cursor)
            data = f.read(read_size) + data
            lines = data.splitlines()

        text_lines = [line.decode("utf-8", errors="replace").strip() for line in lines]
        non_empty = [line for line in text_lines if line]
        return non_empty[-n:]


def _is_valid_row(row: dict[str, Any], logger: logging.Logger) -> bool:
    missing = [field for field in REQUIRED_OBSERVATION_FIELDS if field not in row]
    if missing:
        logger.warning("Skipping row with missing fields: %s", missing)
        return False

    if row.get("time_left_s") not in TIME_BUCKETS:
        logger.warning("Skipping row with unknown time_left_s=%s", row.get("time_left_s"))
        return False

    if row.get("pnl_z_bucket") not in PNL_Z_BUCKETS:
        logger.warning("Skipping row with unknown pnl_z_bucket=%s", row.get("pnl_z_bucket"))
        return False

    if row.get("net_liq_bucket") not in NET_LIQ_BUCKETS:
        logger.warning("Skipping row with unknown net_liq_bucket=%s", row.get("net_liq_bucket"))
        return False

    return True


def read_last_n_jsonl(path: str | Path, n: int = 200, logger: logging.Logger | None = None) -> list[dict[str, Any]]:
    """Read last N valid JSONL rows with safe parsing and validation."""
    logger = logger or logging.getLogger(__name__)
    file_path = Path(path)

    if not file_path.exists():
        logger.warning("Observation log file missing: %s", file_path)
        return []

    raw_lines = _tail_non_empty_lines(file_path, n=n)
    valid_rows: list[dict[str, Any]] = []
    for line in raw_lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping malformed JSONL line")
            continue

        if not isinstance(row, dict):
            logger.warning("Skipping non-object JSON row")
            continue

        if _is_valid_row(row, logger):
            valid_rows.append(row)

    return valid_rows
