import enum


class BucketType(str, enum.Enum):
    CORE = "core"
    SWING = "swing"
    EVENT = "event"


class RecommendationDecisionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class RecommendationAction(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    WATCH = "watch"
    AVOID = "avoid"


class SetupType(str, enum.Enum):
    LONG_TERM_WATCH = "long_term_watch"
    SWING_ENTRY = "swing_entry"
    SWING_ADD = "swing_add"
    EVENT_SETUP = "event_setup"


class ComplianceStatus(str, enum.Enum):
    ALLOWED = "allowed"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


class WatchlistStatus(str, enum.Enum):
    WATCHING = "watching"
    CANDIDATE = "candidate"
    APPROVED = "approved"
    ARCHIVED = "archived"


class PositionSourceType(str, enum.Enum):
    MANUAL_ENTRY = "manual_entry"
    CSV_IMPORT = "csv_import"
    BROKER_READONLY = "broker_readonly"


class PositionAction(str, enum.Enum):
    HOLD = "hold"
    ADD = "add"
    TRIM = "trim"
    EXIT = "exit"
    REVIEW = "review"
