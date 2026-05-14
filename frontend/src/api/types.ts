export type BucketType = "core" | "swing" | "event";
export type RecommendationDecisionStatus = "pending" | "approved" | "rejected" | "deferred";
export type RecommendationAction = "buy" | "sell" | "watch" | "avoid";
export type SetupType = "long_term_watch" | "swing_entry" | "swing_add" | "event_setup";
export type ComplianceStatus = "allowed" | "needs_review" | "blocked";
export type WatchlistStatus = "watching" | "candidate" | "approved" | "archived";
export type PositionSourceType = "manual_entry" | "csv_import" | "broker_readonly";
export type PositionAction = "hold" | "add" | "trim" | "exit" | "review";
export type PotentialFlag = "high" | "medium" | "low";
export type PotentialSetupStage = "emerging_potential" | "late_momentum";

export interface WatchlistItem {
  id: number;
  symbol: string;
  bucket: BucketType;
  status: WatchlistStatus;
  thesis: string | null;
  next_step: string | null;
  trigger_condition: string | null;
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
    potential_signal?: {
      potential_score: number;
      potential_flag: PotentialFlag;
      setup_stage: PotentialSetupStage;
      stage_label: string;
      rationale: string;
      developing_signals: string[];
      cautions: string[];
      label: string;
      warning: string;
      metrics: Record<string, number | null>;
      score_thresholds: {
        high: number;
        medium: number;
      };
    };
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
  next_step?: string | null;
  trigger_condition?: string | null;
  is_active?: boolean;
}

export interface WatchlistItemUpdate {
  bucket?: BucketType;
  status?: WatchlistStatus;
  thesis?: string | null;
  next_step?: string | null;
  trigger_condition?: string | null;
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

export interface PotentialCandidate {
  symbol: string;
  bucket: BucketType;
  watchlist_item_id: number;
  thesis: string | null;
  potential_score: number;
  potential_flag: PotentialFlag;
  setup_stage: PotentialSetupStage;
  stage_label: string;
  rationale: string;
  developing_signals: string[];
  cautions: string[];
  warning: string;
  metrics: Record<string, number | null>;
  market_snapshot: {
    snapshot_price: number;
    data_provider: string;
    data_source_type: string;
    refreshed_at: string;
    is_provider_backed: boolean;
  };
}

export interface PotentialScanResult {
  universe: string;
  note: string;
  candidates: PotentialCandidate[];
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
  assessment_rationale: string | null;
  assessment_summary: string | null;
  pnl_pct: number | null;
  market_snapshot: {
    snapshot_price: number | null;
    position_price?: number | null;
    moving_average_20: number;
    ma50: number;
    trend_positive: boolean;
    price_vs_ma20_pct?: number | null;
    ma20_vs_ma50_pct?: number | null;
    rsi_14: number;
    volume_ratio: number | null;
    daily_change_pct: number;
    daily_change_for_decision?: number | null;
    daily_change_is_suspect?: boolean;
    data_provider: string;
    data_source_type: string;
    refreshed_at: string;
    snapshot_age_hours?: number;
    is_current?: boolean;
    field_sources?: Record<string, string> | null;
    data_quality_warnings?: string[];
    position_snapshot_price_mismatch_pct?: number | null;
    holding_type?: "fund_or_index" | "individual_stock";
    momentum_stage?: "late_momentum" | "intact_or_emerging";
  } | null;
  read_only_note: string;
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
  column_mapping?: Record<string, string | null>;
}

export interface PositionCsvImportResult {
  imported_count: number;
  skipped_count: number;
  positions: PortfolioPosition[];
  errors: string[];
}

export interface PositionCsvPreviewRequest {
  csv_text: string;
  column_mapping?: Record<string, string | null>;
}

export interface PositionCsvPreviewRow {
  row_number: number;
  values: Record<string, string | number | null>;
  errors: string[];
}

export interface PositionCsvPreviewResult {
  headers: string[];
  suggested_mapping: Record<string, string | null>;
  rows: PositionCsvPreviewRow[];
  valid_count: number;
  error_count: number;
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
