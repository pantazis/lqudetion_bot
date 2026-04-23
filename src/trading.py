"""Main runtime loop for BTC 5m heatmap decision bot."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone
from typing import Any

from src.adapters.binance import fetch_btc_mark_price, fetch_net_liquidation_usd
from src.adapters.binance_ws import BinanceLiquidationStream
from src.adapters.polymarket import place_order_stub
from src.btc5m.heatmap.aggregate import aggregate_rows
from src.btc5m.heatmap.build_dashboard import build_dashboard
from src.btc5m.heatmap.observe import append_observation_row
from src.btc5m.heatmap.read_logs import read_last_n_jsonl
from src.core.config import load_config
from src.core.decision import decide_from_state
from src.core.env import load_dotenv
from src.core.state import bucket_net_liq, bucket_pnl_z, bucket_time_left_5m, z_score


def _should_trigger_liq_retrain(
    current_net_liq: float,
    previous_net_liq: float | None,
    now_epoch_s: float,
    last_trigger_epoch_s: float,
    abs_threshold: float,
    delta_threshold: float,
    cooldown_seconds: float,
) -> tuple[bool, str]:
    if now_epoch_s - last_trigger_epoch_s < cooldown_seconds:
        return False, "cooldown"

    if abs(current_net_liq) >= abs_threshold:
        return True, "abs_threshold"

    if previous_net_liq is None:
        return False, "no_previous_baseline"

    delta = abs(current_net_liq - previous_net_liq)
    if delta >= delta_threshold:
        return True, "delta_threshold"

    return False, "below_threshold"


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _entry_side_from_liq_bucket(net_liq_bucket: str) -> str:
    if net_liq_bucket in {"strong_minus", "weak_minus"}:
        return "SHORT"
    return "LONG"


def _resolve_net_liq(config: dict[str, Any], runtime_state: dict[str, Any], logger: logging.Logger) -> float:
    signal_cfg = config.get("signal", {})
    liq_source = str(signal_cfg.get("liq_source", "websocket")).strip().lower()

    if liq_source in {"websocket", "ws"}:
        ws_stream = runtime_state.get("liq_ws_stream")
        if ws_stream is None:
            stream_scope = str(signal_cfg.get("liq_ws_stream_scope", "btcusdt"))
            min_event_usd = float(signal_cfg.get("min_liq_event_usd", 50_000))
            ws_stream = BinanceLiquidationStream(
                stream_scope=stream_scope,
                min_event_usd=min_event_usd,
                logger=logger,
            )
            if ws_stream.start():
                logger.info(
                    "Liquidation source websocket enabled scope=%s min_event_usd=%.2f",
                    stream_scope,
                    min_event_usd,
                )
                runtime_state["liq_ws_stream"] = ws_stream
            else:
                logger.warning("websocket-client missing; falling back to REST liquidation source")
                runtime_state["liq_ws_stream"] = None
                return fetch_net_liquidation_usd(logger=logger)

        if ws_stream is not None:
            ws_window_seconds = float(signal_cfg.get("liq_ws_window_seconds", 20))
            ws_max_age_seconds = float(signal_cfg.get("liq_ws_max_age_seconds", 30))
            net_liq_ws = ws_stream.get_recent_net_liq(
                window_seconds=ws_window_seconds,
                max_age_seconds=ws_max_age_seconds,
            )
            if net_liq_ws is not None:
                return net_liq_ws

            logger.warning("No fresh WS liquidation events; falling back to REST for this cycle")

    return fetch_net_liquidation_usd(logger=logger)


def run_once(config: dict[str, Any], logger: logging.Logger, runtime_state: dict[str, Any] | None = None) -> None:
    if runtime_state is None:
        runtime_state = {}
    log_path = "logs/heatmap_observations.jsonl"

    rows = read_last_n_jsonl(log_path, n=200, logger=logger)
    agg = aggregate_rows(rows)

    mark_price = fetch_btc_mark_price(logger=logger)
    if mark_price is None:
        logger.warning("Skipping cycle: BTC mark price unavailable")
        build_dashboard(log_path=log_path, output_path="dashboard/heatmap_dashboard.html", logger=logger)
        return

    net_liq = _resolve_net_liq(config, runtime_state, logger)
    weak_threshold = float(config.get("signal", {}).get("entry_threshold_min", 25_000))
    strong_threshold = float(config.get("signal", {}).get("entry_threshold_max", 100_000))
    net_liq_bucket = bucket_net_liq(net_liq, weak_threshold=weak_threshold, strong_threshold=strong_threshold)

    retrain_abs_threshold = float(config.get("signal", {}).get("retrain_abs_usd", 25_000))
    retrain_delta_threshold = float(config.get("signal", {}).get("retrain_delta_usd", 15_000))
    retrain_cooldown_seconds = float(config.get("signal", {}).get("retrain_cooldown_seconds", 10))
    now_epoch_s = time.time()

    previous_net_liq = runtime_state.get("previous_net_liq")
    last_trigger_epoch_s = float(runtime_state.get("last_liq_retrain_trigger_epoch_s", 0.0))
    triggered, trigger_reason = _should_trigger_liq_retrain(
        current_net_liq=net_liq,
        previous_net_liq=previous_net_liq,
        now_epoch_s=now_epoch_s,
        last_trigger_epoch_s=last_trigger_epoch_s,
        abs_threshold=retrain_abs_threshold,
        delta_threshold=retrain_delta_threshold,
        cooldown_seconds=retrain_cooldown_seconds,
    )

    runtime_state["previous_net_liq"] = net_liq
    if triggered:
        runtime_state["last_liq_retrain_trigger_epoch_s"] = now_epoch_s
        logger.info(
            "Liquidation retrain trigger fired: reason=%s net_liq=%.2f previous_net_liq=%s",
            trigger_reason,
            net_liq,
            previous_net_liq,
        )
        rows = read_last_n_jsonl(log_path, n=200, logger=logger)
        agg = aggregate_rows(rows)
        logger.info("Immediate retrain refresh complete: rows_loaded=%s", len(rows))
    else:
        logger.debug(
            "No immediate liquidation retrain: reason=%s net_liq=%.2f previous_net_liq=%s",
            trigger_reason,
            net_liq,
            previous_net_liq,
        )

    history_prices = [float(r.get("current_price", mark_price)) for r in rows if "current_price" in r]
    pnl_z = z_score(mark_price, history_prices)
    pnl_bucket = bucket_pnl_z(pnl_z)
    time_left = bucket_time_left_5m()
    state = (time_left, pnl_bucket, net_liq_bucket)

    min_win_rate = float(config.get("signal", {}).get("min_win_rate", 0.58))
    decision = decide_from_state(agg, state, min_win_rate=min_win_rate)
    logger.info(
        "Decision state=%s action=%s reason=%s confidence=%s win_rate=%s samples=%s",
        state,
        decision.action,
        decision.reason,
        decision.confidence,
        decision.win_rate,
        decision.samples,
    )

    dry_run_cfg = _bool(config.get("operational", {}).get("dry_run", True), default=True)
    training_mode = _bool(config.get("operational", {}).get("training_mode", True), default=True)
    dry_run = dry_run_cfg or training_mode

    base_bet = float(config.get("polymarket", {}).get("bet_size", 10))
    size = base_bet * decision.suggested_size_scale
    if decision.action == "ENTER" and size > 0:
        side = _entry_side_from_liq_bucket(net_liq_bucket)
        order_result = place_order_stub(side=side, size_usd=size, dry_run=dry_run, logger=logger)
        logger.info("Order result: %s", order_result)

    now = datetime.now(timezone.utc)
    observation = {
        "ts": now.isoformat(),
        "market": "BTC_5M",
        "round_id": now.replace(second=0, microsecond=0).isoformat(),
        "time_left_s": time_left,
        "pnl_z_bucket": pnl_bucket,
        "net_liq_bucket": net_liq_bucket,
        "entry_side": _entry_side_from_liq_bucket(net_liq_bucket),
        "entry_price": mark_price,
        "current_price": mark_price,
        "final_price": mark_price,
        "target_label": 0,
        "win": 0,
        "final_pnl_pct": 0.0,
    }
    append_observation_row(log_path, observation, logger=logger)
    build_dashboard(log_path=log_path, output_path="dashboard/heatmap_dashboard.html", logger=logger)


def main() -> None:
    parser = argparse.ArgumentParser(description="BTC 5m heatmap trading bot")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=20)
    args = parser.parse_args()

    load_dotenv(".env")
    config = load_config(args.config)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    logger = logging.getLogger("btc5m_bot")

    if args.once:
        run_once(config, logger, runtime_state={})
        return

    runtime_state: dict[str, Any] = {}
    while True:
        run_once(config, logger, runtime_state=runtime_state)
        time.sleep(max(5, args.interval_seconds))


if __name__ == "__main__":
    main()
