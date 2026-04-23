# BTC 5m Heatmap Bot — Prompt Rules (Fix Mode)

Use these rules as a strict prompt baseline when generating, fixing, or refactoring the bot.

## 1) Primary Objective
- Build and maintain a **reliable BTC 5m heatmap decision pipeline**.
- Prioritize **correctness, determinism, and debuggability** over clever abstractions.
- Every change must support: `current_state -> lookup -> win_rate -> decision`.

## 2) Data + State Rules (Non-Negotiable)
- State key is always:
  - `(time_left_s, pnl_z_bucket, net_liq_bucket)`
- Use 20-second time buckets in this order:
  - `300, 280, 260, 240, 220, 200, 180, 160, 140, 120, 100, 80, 60, 40, 20, 0`
- Use pnl z-buckets in this order (if present):
  - `lt_neg_2, neg_2_to_neg_1, neg_1_to_neg_0_3, neg_0_3_to_0_3, pos_0_3_to_1, pos_1_to_2, gt_2`
- Use liquidation buckets in this order (if present):
  - `strong_minus, weak_minus, neutral, weak_plus, strong_plus`

## 3) Rolling Window Rules
- Aggregations must use **only the last 200 JSONL lines**.
- If file has <200 valid rows, use all valid rows.
- Do not read the entire file if avoidable.
- Skip malformed lines with warning logs; never crash for one bad line.

## 4) Required Log Row Contract
Each JSONL observation row should include:
- `ts`
- `market`
- `round_id`
- `time_left_s`
- `pnl_z_bucket`
- `net_liq_bucket`
- `entry_side`
- `entry_price`
- `current_price`
- `final_price`
- `target_label`
- `win`
- `final_pnl_pct`

If fields are missing, skip row safely and emit a warning.

## 5) Aggregation Rules
For each state, compute:
- `samples`
- `wins`
- `losses = samples - wins`
- `win_rate = wins / samples`
- `avg_final_pnl_pct = mean(final_pnl_pct)`

Guard all divide operations. Never allow divide-by-zero.

## 6) Heatmap Output Rules
- Render one 2D table per `net_liq_bucket`.
- Rows: `time_left_s`.
- Columns: `pnl_z_bucket`.
- Cell format: `win_rate% (samples)` and optional `avg pnl` on second line.
- Missing state must render as `—`.

## 7) Confidence / Sample Quality Rules
- `samples < 30`: treat as unreliable (ignore or strongly mute in signal logic).
- `samples < 50`: weak confidence.
- `samples >= 100`: reliable.
- UI should visibly mark low-sample states.

## 8) Dashboard Rules
- Keep dashboard framework-free: HTML + CSS + vanilla JS.
- Must show:
  - title
  - last refresh timestamp
  - rolling window size
  - one table per liquidation bucket
- Auto-refresh every 10 minutes (`600s`).

## 9) Error-Handling Rules
Must gracefully handle:
- missing log file
- empty log file
- malformed JSON lines
- missing fields
- unknown bucket values
- divide-by-zero risks

On failure, render human-readable status; never hard-crash the dashboard path.

## 10) Code Quality Rules (Prompt Behavior)
- Keep functions short and explicit.
- Prefer simple helpers over deep class hierarchies.
- Use deterministic ordering everywhere.
- Add comments only where logic is non-obvious.
- Avoid over-engineering and avoid new frameworks.
- Keep code production-clean and easy to modify.

## 11) Bot Decision Guardrails
- Bot should only consider entries when state has enough sample confidence.
- Use win-rate thresholds for entry filtering.
- Position sizing should scale with confidence, not raw conviction.
- If state is missing/low-confidence, default to no-trade or reduced-risk behavior.

### Event-Triggered Retrain Guardrail
- When liquidation spikes are detected, allow immediate retrain/refresh before decision lookup.
- Trigger logic must be deterministic (absolute threshold and/or delta threshold + cooldown).
- Event retrain must still use only the rolling last 200 valid JSONL rows.
- Event-triggered retrain must not bypass confidence/sample-quality checks.

## 12) Done Criteria for Any Fix
A fix is complete only if:
- rolling 200-line behavior is preserved,
- state bucketing + ordering remains deterministic,
- aggregation math is correct,
- low-quality data handling is explicit,
- dashboard still renders under bad input conditions.

## 13) Tracking / Alignment Rule (Always)
- Always read these files before fix/refactor work to confirm alignment and stay on track:
  - `.clinerules/rules.md`
  - `excution.txt`
  - `idia.txt`
