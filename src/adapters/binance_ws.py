"""Binance Futures liquidation market stream adapter (public WebSocket)."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from typing import Any

from src.adapters.liquidation_logic import (
    is_significant_liq_event,
    normalize_force_order_payload,
    signed_net_liq_usd,
)

try:
    import websocket  # type: ignore
except Exception:  # noqa: BLE001
    websocket = None


class BinanceLiquidationStream:
    """Background WebSocket client for force-order liquidation events."""

    def __init__(
        self,
        stream_scope: str = "btcusdt",
        min_event_usd: float = 50_000.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.stream_scope = stream_scope.strip().lower()
        self.min_event_usd = float(min_event_usd)

        self._events: deque[tuple[float, float]] = deque()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False

    def _stream_url(self) -> str:
        if self.stream_scope == "all":
            return "wss://fstream.binance.com/market/ws/!forceOrder@arr"
        return f"wss://fstream.binance.com/market/ws/{self.stream_scope}@forceOrder"

    def _apply_event(self, payload: dict[str, Any]) -> None:
        normalized = normalize_force_order_payload(payload)
        if normalized is None:
            return

        if not is_significant_liq_event(normalized.usd_size, self.min_event_usd):
            return

        signed_usd = signed_net_liq_usd(normalized.side_kind, normalized.usd_size)
        if signed_usd == 0.0:
            return

        now = time.time()
        with self._lock:
            self._events.append((now, signed_usd))

        self.logger.debug(
            "WS liquidation event accepted symbol=%s side_kind=%s usd=%.2f signed_usd=%.2f",
            normalized.symbol,
            normalized.side_kind,
            normalized.usd_size,
            signed_usd,
        )

    def _on_message(self, _ws: Any, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            self.logger.warning("WS liquidation message decode failed")
            return

        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    self._apply_event(item)
            return

        if isinstance(payload, dict):
            self._apply_event(payload)

    def _on_error(self, _ws: Any, error: Any) -> None:
        self.logger.warning("WS liquidation stream error: %s", error)

    def _on_close(self, _ws: Any, status_code: Any, msg: Any) -> None:
        self.logger.warning("WS liquidation stream closed status=%s msg=%s", status_code, msg)

    def _run_forever(self) -> None:
        if websocket is None:
            self.logger.warning("websocket-client not installed; WS liquidation stream disabled")
            return

        url = self._stream_url()
        self.logger.info("Starting Binance liquidation WS: %s", url)

        while not self._stop_event.is_set():
            try:
                ws_app = websocket.WebSocketApp(
                    url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                ws_app.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("WS liquidation stream run failure: %s", exc)

            if not self._stop_event.is_set():
                time.sleep(2)

    def start(self) -> bool:
        if self._started:
            return True
        if websocket is None:
            return False

        self._thread = threading.Thread(target=self._run_forever, name="binance-liq-ws", daemon=True)
        self._thread.start()
        self._started = True
        return True

    def stop(self) -> None:
        self._stop_event.set()

    def get_recent_net_liq(self, window_seconds: float = 20.0, max_age_seconds: float = 30.0) -> float | None:
        now = time.time()
        with self._lock:
            while self._events and (now - self._events[0][0]) > max(window_seconds, max_age_seconds) * 2:
                self._events.popleft()

            recent = [v for ts, v in self._events if (now - ts) <= window_seconds]
            has_fresh = any((now - ts) <= max_age_seconds for ts, _ in self._events)

        if not has_fresh:
            return None
        return float(sum(recent)) if recent else 0.0
