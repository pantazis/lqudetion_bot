# BTC 5m Heatmap Trading Bot (Starter)

This project now includes a full first-pass end-to-end bot flow:

- `.env` loading
- config loading with `${ENV_VAR}` substitution
- liquidation + mark-price market adapters
- rolling 200-line JSONL reader
- deterministic heatmap aggregation
- decision engine (`current_state -> lookup -> win_rate -> decision`)
- observation logging
- standalone HTML dashboard generation
- Binance liquidation WebSocket market stream (`/market/ws/...`) with REST fallback

## Run

Install locally:

```bash
pip install -e .
```

Run one cycle:

```bash
python -m src.trading --config config.yaml --once
```

Run continuous loop (default 20s cycle):

```bash
python -m src.trading --config config.yaml --interval-seconds 20
```

Build dashboard only:

```bash
python -m src.btc5m.heatmap.build_dashboard --log-path logs/heatmap_observations.jsonl --output-path dashboard/heatmap_dashboard.html
```

## Output Files

- observations: `logs/heatmap_observations.jsonl`
- dashboard: `dashboard/heatmap_dashboard.html`

## Notes

- The Polymarket adapter is intentionally safe: live order placement is still a stub unless fully implemented.
- In dry-run/training mode, order execution is simulated and logged.
- For fastest liquidation updates, use websocket source in `config.yaml`:
  - `signal.liq_source: websocket`
  - `signal.liq_ws_stream_scope: btcusdt` (or `all`)
  - `signal.min_liq_event_usd: 50000`
