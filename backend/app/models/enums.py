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

