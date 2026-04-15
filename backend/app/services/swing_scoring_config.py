SWING_SCORE_THRESHOLDS = {
    "buy": 0.72,
    "watch": 0.45,
    "avoid": 0.25,
}

SWING_SCORE_LIMITS = {
    "min": 0.05,
    "max": 0.94,
}

SWING_SCORE_BASE = 0.42

SWING_SCORE_BONUSES = {
    "price_above_ma20": 0.18,
    "price_above_ma20_extended": 0.05,
    "ma20_above_ma50": 0.17,
    "ma20_slightly_above_ma50": 0.07,
    "rsi_preferred_min": 0.10,
    "rsi_preferred_max": 0.18,
    "volume_above_average_base": 0.10,
    "volume_above_average_max": 0.14,
    "volume_near_confirmation": 0.04,
    "daily_change_constructive": 0.08,
    "daily_change_slightly_positive": 0.02,
}

SWING_SCORE_PENALTIES = {
    "price_slightly_below_ma20": 0.14,
    "price_materially_below_ma20": 0.26,
    "ma20_below_ma50": 0.20,
    "rsi_slightly_extended": 0.05,
    "rsi_extended": 0.18,
    "rsi_overheated": 0.22,
    "rsi_soft": 0.06,
    "rsi_weak": 0.22,
    "volume_weak": 0.16,
    "volume_light": 0.24,
    "daily_change_stretched": 0.08,
    "daily_change_negative_base": 0.06,
    "daily_change_negative_max": 0.14,
    "earnings_within_7_days": 0.25,
    "earnings_within_14_days": 0.14,
}

SWING_RULE_BOUNDS = {
    "price_materially_below_ma20_pct": -2,
    "price_extended_above_ma20_pct": 8,
    "ma20_meaningfully_above_ma50_pct": 1,
    "rsi_preferred_min": 50,
    "rsi_preferred_max": 65,
    "rsi_slightly_extended_max": 70,
    "rsi_extended_max": 75,
    "rsi_auto_avoid_min": 80,
    "rsi_soft_min": 45,
    "volume_confirmed_ratio": 1.25,
    "volume_near_confirmed_ratio": 1,
    "volume_weak_ratio": 0.75,
    "daily_change_constructive_min_pct": 0.3,
    "daily_change_constructive_max_pct": 3,
    "earnings_high_risk_days": 7,
    "earnings_caution_days": 14,
    "minimum_buy_signals": 4,
    "maximum_buy_penalties": 2,
}
