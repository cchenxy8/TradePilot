POTENTIAL_SCORE_THRESHOLDS = {
    "high": 0.68,
    "medium": 0.42,
}

POTENTIAL_STAGE_SCORE_CAPS = {
    "late_momentum": 0.48,
}

POTENTIAL_SCORE_LIMITS = {
    "min": 0.0,
    "max": 0.95,
}

POTENTIAL_SCORE_BASE = 0.18

POTENTIAL_SCORE_BONUSES = {
    "price_reclaimed_ma20": 0.22,
    "price_near_ma20_reclaim": 0.12,
    "ma20_above_ma50": 0.14,
    "ma20_close_to_ma50": 0.10,
    "rsi_recovering": 0.16,
    "rsi_constructive": 0.12,
    "volume_improving": 0.14,
    "volume_near_average": 0.08,
    "momentum_improving": 0.12,
    "relative_strength_proxy": 0.08,
}

POTENTIAL_SCORE_PENALTIES = {
    "price_far_below_ma20": 0.12,
    "ma20_far_below_ma50": 0.10,
    "rsi_overheated": 0.14,
    "rsi_weak": 0.10,
    "volume_light": 0.10,
    "momentum_negative": 0.08,
    "late_momentum": 0.18,
}

POTENTIAL_RULE_BOUNDS = {
    "price_reclaim_max_above_ma20_pct": 3.0,
    "price_late_extension_above_ma20_pct": 7.0,
    "price_near_reclaim_min_pct": -2.0,
    "price_far_below_ma20_pct": -5.0,
    "ma20_close_to_ma50_min_pct": -2.0,
    "ma20_far_below_ma50_pct": -5.0,
    "rsi_recovering_min": 45.0,
    "rsi_recovering_max": 58.0,
    "rsi_constructive_max": 68.0,
    "rsi_overheated": 76.0,
    "rsi_late_momentum": 72.0,
    "rsi_weak": 40.0,
    "volume_improving_ratio": 1.0,
    "volume_near_average_ratio": 0.85,
    "volume_light_ratio": 0.65,
    "momentum_improving_min_pct": 0.2,
    "momentum_strong_max_pct": 4.0,
}
