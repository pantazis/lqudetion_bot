"""Polymarket adapter (read-friendly + safe dry-run order stub)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass


@dataclass
class PolymarketCredentials:
    api_key: str
    api_secret: str
    passphrase: str
    private_key: str
    base_url: str


def load_polymarket_credentials() -> PolymarketCredentials:
    return PolymarketCredentials(
        api_key=os.getenv("POLYMARKET_CLOB_API_KEY") or os.getenv("POLYMARKET_API_KEY", ""),
        api_secret=os.getenv("POLYMARKET_CLOB_API_SECRET") or os.getenv("POLYMARKET_API_SECRET", ""),
        passphrase=os.getenv("POLYMARKET_CLOB_PASSPHRASE") or os.getenv("POLYMARKET_PASSPHRASE", ""),
        private_key=os.getenv("POLYMARKET_PRIVATE_KEY", ""),
        base_url=os.getenv("POLYMARKET_BASE_URL", "https://clob.polymarket.com"),
    )


def place_order_stub(
    side: str,
    size_usd: float,
    dry_run: bool,
    logger: logging.Logger | None = None,
) -> dict[str, str | float | bool]:
    logger = logger or logging.getLogger(__name__)
    if dry_run:
        logger.info("DRY_RUN: skipping live Polymarket order side=%s size=%s", side, size_usd)
        return {"ok": True, "dry_run": True, "side": side, "size_usd": size_usd}

    creds = load_polymarket_credentials()
    if not creds.api_key or not creds.api_secret or not creds.passphrase:
        logger.warning("Missing Polymarket credentials; cannot place live order")
        return {"ok": False, "dry_run": False, "error": "missing_credentials"}

    logger.info("LIVE trading hook placeholder reached for Polymarket side=%s size=%s", side, size_usd)
    return {"ok": False, "dry_run": False, "error": "live_order_not_implemented"}
