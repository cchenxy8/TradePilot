import enum


class BucketType(str, enum.Enum):
    CORE = "core"
    SWING = "swing"
    EVENT = "event"


class RecommendationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class RecommendationType(str, enum.Enum):
    WATCHLIST_FOLLOW_UP = "watchlist_follow_up"
    SWING_ENTRY = "swing_entry"
    SWING_ADD = "swing_add"
    EVENT_SETUP = "event_setup"


class ComplianceStatus(str, enum.Enum):
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    READY_FOR_REVIEW = "ready_for_review"
    RESTRICTED = "restricted"
