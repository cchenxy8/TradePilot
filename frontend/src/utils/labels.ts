import type {
  BucketType,
  ComplianceStatus,
  RecommendationAction,
  RecommendationDecisionStatus,
  SetupType,
  WatchlistStatus
} from "../api/types";

const bucketLabels: Record<BucketType, string> = {
  core: "Core",
  swing: "Swing",
  event: "Event"
};

const actionLabels: Record<RecommendationAction, string> = {
  buy: "Buy",
  sell: "Sell",
  watch: "Watch",
  avoid: "Avoid"
};

const setupLabels: Record<SetupType, string> = {
  long_term_watch: "Long-term · Watch",
  swing_entry: "Swing · Entry",
  swing_add: "Swing · Add",
  event_setup: "Event · Setup"
};

const complianceLabels: Record<ComplianceStatus, string> = {
  allowed: "Allowed",
  needs_review: "Needs review",
  blocked: "Blocked"
};

const decisionLabels: Record<RecommendationDecisionStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  deferred: "Deferred"
};

const watchlistStatusLabels: Record<WatchlistStatus, string> = {
  watching: "Watching",
  candidate: "Candidate",
  approved: "Approved",
  archived: "Archived"
};

export function labelBucket(value: BucketType): string {
  return bucketLabels[value];
}

export function labelAction(value: RecommendationAction): string {
  return actionLabels[value];
}

export function labelSetup(value: SetupType): string {
  return setupLabels[value];
}

export function labelCompliance(value: ComplianceStatus): string {
  return complianceLabels[value];
}

export function labelDecision(value: RecommendationDecisionStatus): string {
  return decisionLabels[value];
}

export function labelWatchlistStatus(value: WatchlistStatus): string {
  return watchlistStatusLabels[value];
}

export function labelFilter(value: string): string {
  if (value === "all") return "All";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
