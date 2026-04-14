export type BucketType = "core" | "swing" | "event";
export type RecommendationDecisionStatus = "pending" | "approved" | "rejected" | "deferred";
export type RecommendationAction = "buy" | "sell" | "watch" | "avoid";
export type SetupType = "long_term_watch" | "swing_entry" | "swing_add" | "event_setup";
export type ComplianceStatus = "allowed" | "needs_review" | "blocked";
export type WatchlistStatus = "watching" | "candidate" | "approved" | "archived";

export interface WatchlistItem {
  id: number;
  symbol: string;
  bucket: BucketType;
  status: WatchlistStatus;
  thesis: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Recommendation {
  id: number;
  symbol: string;
  bucket: BucketType;
  title: string;
  rationale: string;
  recommendation_action: RecommendationAction;
  setup_type: SetupType;
  why_now: string;
  risk_notes: string;
  confidence_score: number;
  compliance_status: ComplianceStatus;
  source: string | null;
  decision_status: RecommendationDecisionStatus;
  watchlist_item_id: number | null;
  market_snapshot_id: number | null;
  mock_price: number | null;
  market_snapshot: Record<string, unknown> | null;
  generated_at: string;
  decided_at: string | null;
  decision_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface JournalEntry {
  id: number;
  title: string;
  content: string;
  symbol: string | null;
  bucket: BucketType | null;
  recommendation_id: number | null;
  planned_entry: number | null;
  planned_exit: number | null;
  stop_loss: number | null;
  position_size_pct: number | null;
  outcome_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface WatchlistItemCreate {
  symbol: string;
  bucket: BucketType;
  status?: WatchlistStatus;
  thesis?: string | null;
  is_active?: boolean;
}

export interface JournalEntryCreate {
  title: string;
  content: string;
  symbol?: string | null;
  bucket?: BucketType | null;
  recommendation_id?: number | null;
  planned_entry?: number | null;
  planned_exit?: number | null;
  stop_loss?: number | null;
  position_size_pct?: number | null;
  outcome_note?: string | null;
}

export interface RecommendationDecisionRequest {
  decision: Exclude<RecommendationDecisionStatus, "pending">;
  reason?: string | null;
  decided_at?: string | null;
}
