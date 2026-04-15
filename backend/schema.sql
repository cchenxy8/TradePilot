CREATE TYPE bucket_type AS ENUM ('core', 'swing', 'event');
CREATE TYPE recommendation_decision_status AS ENUM ('pending', 'approved', 'rejected', 'deferred');
CREATE TYPE recommendation_action AS ENUM ('buy', 'sell', 'watch', 'avoid');
CREATE TYPE setup_type AS ENUM ('long_term_watch', 'swing_entry', 'swing_add', 'event_setup');
CREATE TYPE compliance_status AS ENUM ('allowed', 'needs_review', 'blocked');
CREATE TYPE watchlist_status AS ENUM ('watching', 'candidate', 'approved', 'archived');

CREATE TABLE watchlist_items (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(16) NOT NULL,
    bucket bucket_type NOT NULL,
    status watchlist_status NOT NULL DEFAULT 'watching',
    thesis TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE market_snapshots (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(16) NOT NULL,
    watchlist_item_id BIGINT REFERENCES watchlist_items(id) ON DELETE SET NULL,
    latest_price NUMERIC(12, 2),
    mock_price NUMERIC(12, 2),
    volume BIGINT NOT NULL,
    avg_volume_20d BIGINT NOT NULL,
    moving_average_20 NUMERIC(12, 2) NOT NULL,
    ma50 NUMERIC(12, 2) NOT NULL,
    daily_change_pct DOUBLE PRECISION NOT NULL,
    rsi_14 DOUBLE PRECISION NOT NULL,
    earnings_date DATE,
    news_summary TEXT,
    data_provider VARCHAR(50) NOT NULL DEFAULT 'unknown',
    data_source_type VARCHAR(30) NOT NULL DEFAULT 'unknown',
    data_delay_note TEXT,
    field_sources JSONB,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    snapshot_payload JSONB,
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE recommendations (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(16) NOT NULL,
    bucket bucket_type NOT NULL,
    title VARCHAR(255) NOT NULL,
    rationale TEXT NOT NULL,
    source VARCHAR(100),
    recommendation_action recommendation_action NOT NULL,
    setup_type setup_type NOT NULL,
    why_now TEXT NOT NULL,
    risk_notes TEXT NOT NULL,
    confidence_score DOUBLE PRECISION NOT NULL,
    compliance_status compliance_status NOT NULL DEFAULT 'needs_review',
    decision_status recommendation_decision_status NOT NULL DEFAULT 'pending',
    watchlist_item_id BIGINT REFERENCES watchlist_items(id) ON DELETE SET NULL,
    market_snapshot_id BIGINT REFERENCES market_snapshots(id) ON DELETE SET NULL,
    latest_price NUMERIC(12, 2),
    mock_price NUMERIC(12, 2),
    market_snapshot JSONB,
    rule_results JSONB,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ,
    decision_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE journal_entries (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    symbol VARCHAR(16),
    bucket bucket_type,
    recommendation_id BIGINT REFERENCES recommendations(id) ON DELETE SET NULL,
    planned_entry NUMERIC(12, 2),
    planned_exit NUMERIC(12, 2),
    stop_loss NUMERIC(12, 2),
    position_size_pct DOUBLE PRECISION,
    outcome_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id BIGINT,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_watchlist_items_symbol ON watchlist_items(symbol);
CREATE INDEX ix_watchlist_items_bucket ON watchlist_items(bucket);
CREATE INDEX ix_watchlist_items_status ON watchlist_items(status);
CREATE INDEX ix_market_snapshots_symbol ON market_snapshots(symbol);
CREATE INDEX ix_recommendations_symbol ON recommendations(symbol);
CREATE INDEX ix_recommendations_bucket ON recommendations(bucket);
CREATE INDEX ix_recommendations_decision_status ON recommendations(decision_status);
CREATE INDEX ix_recommendations_recommendation_action ON recommendations(recommendation_action);
CREATE INDEX ix_recommendations_setup_type ON recommendations(setup_type);
CREATE INDEX ix_journal_entries_symbol ON journal_entries(symbol);
CREATE INDEX ix_journal_entries_bucket ON journal_entries(bucket);
CREATE INDEX ix_audit_logs_event_type ON audit_logs(event_type);
