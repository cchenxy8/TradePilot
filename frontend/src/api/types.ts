export type BucketType = "core" | "swing" | "event";
export type RecommendationDecisionStatus = "pending" | "approved" | "rejected" | "deferred";
export type RecommendationAction = "buy" | "sell" | "watch" | "avoid";
export type SetupType = "long_term_watch" | "swing_entry" | "swing_add" | "event_setup";
export type ComplianceStatus = "allowed" | "needs_review" | "blocked";
export type WatchlistStatus = "watching" | "candidate" | "approved" | "archived";
export type PositionSourceType = "manual_entry" | "csv_import" | "broker_readonly";
export type PositionAction = "hold" | "add" | "trim" | "exit" | "review";

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
  latest_price: number | null;
  mock_price: number | null;
  market_snapshot: Record<string, unknown> | null;
  rule_results: {
    passed_signals: string[];
    failed_signals: string[];
    penalties: string[];
    avoid_reasons?: string[];
    final_score: number;
    required_rules_passed: boolean;
    rsi_zone?: string;
    score_thresholds?: {
      buy: number;
      watch: number;
      avoid: number;
    };
    metrics: Record<string, number | null>;
  } | null;
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

export interface MarketSnapshot {
  id: number;
  symbol: string;
  watchlist_item_id: number | null;
  latest_price: number | null;
  mock_price: number | null;
  volume: number;
  avg_volume_20d: number;
  moving_average_20: number;
  ma50: number;
  daily_change_pct: number;
  rsi_14: number;
  earnings_date: string | null;
  news_summary: string | null;
  data_provider: string;
  data_source_type: string;
  data_delay_note: string | null;
  field_sources: Record<string, string> | null;
  is_current: boolean;
  snapshot_payload: Record<string, unknown> | null;
  refreshed_at: string;
  captured_at: string;
  created_at: string;
  updated_at: string;
}

export interface PortfolioPosition {
  id: number;
  account_id: string | null;
  source_type: PositionSourceType;
  external_position_id: string | null;
  last_synced_at: string | null;
  symbol: string;
  shares: number;
  average_cost: number | null;
  current_price: number | null;
  unrealized_pnl: number | null;
  portfolio_weight: number | null;
  thesis: string | null;
  notes: string | null;
  recommended_action: PositionAction;
  created_at: string;
  updated_at: string;
}

export interface PortfolioPositionCreate {
  account_id?: string | null;
  source_type?: PositionSourceType;
  external_position_id?: string | null;
  last_synced_at?: string | null;
  symbol: string;
  shares: number;
  average_cost?: number | null;
  current_price?: number | null;
  unrealized_pnl?: number | null;
  portfolio_weight?: number | null;
  thesis?: string | null;
  notes?: string | null;
  recommended_action?: PositionAction;
}

export interface PositionCsvImportRequest {
  csv_text: string;
  account_id?: string | null;
  source_type?: PositionSourceType;
  last_synced_at?: string | null;
}

export interface PositionCsvImportResult {
  imported_count: number;
  skipped_count: number;
  positions: PortfolioPosition[];
  errors: string[];
}

export interface BrokerReadonlySyncRequest {
  account_id: string;
  positions: PortfolioPositionCreate[];
  last_synced_at?: string | null;
}

export interface RecommendationDecisionRequest {
  decision: Exclude<RecommendationDecisionStatus, "pending">;
  reason?: string | null;
  decided_at?: string | null;
}
