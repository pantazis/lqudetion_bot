"""Build heatmap dashboard HTML from rolling JSONL observations."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.btc5m.heatmap.aggregate import aggregate_rows
from src.btc5m.heatmap.read_logs import read_last_n_jsonl
from src.btc5m.heatmap.render_html import render_dashboard_html


def build_dashboard(
    log_path: str | Path = "logs/heatmap_observations.jsonl",
    output_path: str | Path = "dashboard/heatmap_dashboard.html",
    logger: logging.Logger | None = None,
) -> None:
    logger = logger or logging.getLogger(__name__)
    status = ""

    try:
        rows = read_last_n_jsonl(log_path, n=200, logger=logger)
        payload = aggregate_rows(rows)
        if not rows:
            status = "No valid rows loaded. Dashboard rendered with empty state."
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to build heatmap payload: %s", exc)
        payload = {"rows_loaded": 0, "tables": {}}
        status = f"Heatmap build error: {exc}"

    html = render_dashboard_html(payload, status_message=status)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    logger.info("Dashboard written: %s", output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build BTC 5m heatmap dashboard")
    parser.add_argument("--log-path", default="logs/heatmap_observations.jsonl")
    parser.add_argument("--output-path", default="dashboard/heatmap_dashboard.html")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    build_dashboard(log_path=args.log_path, output_path=args.output_path)


if __name__ == "__main__":
    main()
