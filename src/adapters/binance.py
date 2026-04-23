"""Read-only Binance adapters used for market context."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from urllib.parse import parse_qsl, urlencode, urlparse
from typing import Any

import requests

from src.adapters.liquidation_logic import classify_binance_liq_side, signed_net_liq_usd


def fetch_btc_mark_price(logger: logging.Logger | None = None) -> float | None:
    logger = logger or logging.getLogger(__name__)
    base_url = os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com").rstrip("/")
    url = f"{base_url}/fapi/v1/premiumIndex"
    try:
        resp = requests.get(url, params={"symbol": "BTCUSDT"}, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        return float(payload.get("markPrice"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch BTC mark price: %s", exc)
        return None


def fetch_net_liquidation_usd(window_limit: int = 100, logger: logging.Logger | None = None) -> float:
    """Fetch force-order data and return signed net liquidation pressure (USD).

    Side semantics aligned with liquidation module logic:
    - BUY  -> short_liquidated  -> positive pressure
    - SELL -> long_liquidated   -> negative pressure
    """
    logger = logger or logging.getLogger(__name__)
    endpoint = os.getenv(
        "US_LIQUIDATION_ENDPOINT",
        "https://fapi.binance.com/fapi/v1/forceOrders?symbol=BTCUSDT&limit=100",
    )
    api_key = os.getenv("BINANCE_FUTURES_API_KEY") or os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_FUTURES_API_SECRET") or os.getenv("BINANCE_API_SECRET")

    headers: dict[str, str] = {}
    parsed = urlparse(endpoint)
    is_binance_force_orders = parsed.netloc.endswith("binance.com") and (
        parsed.path.endswith("/forceOrders") or parsed.path.endswith("/allForceOrders")
    )
    query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))

    if is_binance_force_orders:
        if not api_key or not api_secret:
            logger.warning(
                "Binance allForceOrders endpoint requires API key/secret; returning neutral liquidation value"
            )
            return 0.0

        headers["X-MBX-APIKEY"] = api_key
        request_path = "/fapi/v1/forceOrders" if parsed.path.endswith("/allForceOrders") else parsed.path
        if parsed.path.endswith("/allForceOrders"):
            logger.warning("Endpoint /allForceOrders is deprecated/invalid for futures. Switching to /forceOrders.")
        query_pairs.setdefault("symbol", "BTCUSDT")
        query_pairs.setdefault("limit", str(window_limit))

        def _signed_query(params: dict[str, str]) -> dict[str, str]:
            signed = dict(params)
            signed["timestamp"] = str(int(time.time() * 1000))
            signed.setdefault("recvWindow", os.getenv("BINANCE_RECV_WINDOW", "10000"))
            query_string = urlencode(signed)
            signature = hmac.new(api_secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()
            signed["signature"] = signature
            return signed

        # Primary endpoint: futures USER_DATA forceOrders
        signed_primary = _signed_query(query_pairs)
        primary_url = f"{parsed.scheme}://{parsed.netloc}{request_path}"

        try:
            resp = requests.get(primary_url, params=signed_primary, headers=headers, timeout=10)
            if resp.status_code >= 400:
                body_preview = resp.text[:300].replace("\n", " ")
                logger.warning(
                    "Primary liquidation endpoint failed status=%s path=%s body=%s",
                    resp.status_code,
                    request_path,
                    body_preview,
                )
                if resp.status_code == 401:
                    logger.warning(
                        "Binance auth failure on forceOrders. Check Futures API permission, key IP whitelist, and key/secret pairing."
                    )

            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                logger.warning("Unexpected liquidation response type: %s", type(data).__name__)
                return 0.0

            rows: list[dict[str, Any]] = [r for r in data if isinstance(r, dict)][:window_limit]
            net = 0.0
            for row in rows:
                side = str(row.get("side", "")).upper()
                qty = float(row.get("origQty", 0.0) or 0.0)
                price = float(row.get("price", 0.0) or 0.0)
                usd = qty * price
                side_kind = classify_binance_liq_side(side)
                if side_kind:
                    net += signed_net_liq_usd(side_kind, usd)
            return float(net)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch signed liquidation data: %s", exc)
            return 0.0

    try:
        resp = requests.get(endpoint, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            logger.warning("Unexpected liquidation response type: %s", type(data).__name__)
            return 0.0

        rows: list[dict[str, Any]] = [r for r in data if isinstance(r, dict)][:window_limit]
        net = 0.0
        for row in rows:
            side = str(row.get("side", "")).upper()
            qty = float(row.get("origQty", 0.0) or 0.0)
            price = float(row.get("price", 0.0) or 0.0)
            usd = qty * price
            side_kind = classify_binance_liq_side(side)
            if side_kind:
                net += signed_net_liq_usd(side_kind, usd)
        return float(net)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch liquidation data from %s: %s", parsed.path or endpoint, exc)
        return 0.0
