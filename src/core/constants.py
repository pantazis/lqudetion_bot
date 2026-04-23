"""Deterministic bucket definitions for BTC 5m heatmap logic."""

TIME_BUCKETS = [300, 280, 260, 240, 220, 200, 180, 160, 140, 120, 100, 80, 60, 40, 20, 0]

PNL_Z_BUCKETS = [
    "lt_neg_2",
    "neg_2_to_neg_1",
    "neg_1_to_neg_0_3",
    "neg_0_3_to_0_3",
    "pos_0_3_to_1",
    "pos_1_to_2",
    "gt_2",
]

NET_LIQ_BUCKETS = [
    "strong_minus",
    "weak_minus",
    "neutral",
    "weak_plus",
    "strong_plus",
]

REQUIRED_OBSERVATION_FIELDS = [
    "ts",
    "market",
    "round_id",
    "time_left_s",
    "pnl_z_bucket",
    "net_liq_bucket",
    "entry_side",
    "entry_price",
    "current_price",
    "final_price",
    "target_label",
    "win",
    "final_pnl_pct",
]
