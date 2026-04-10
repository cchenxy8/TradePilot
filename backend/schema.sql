CREATE TYPE bucket_type AS ENUM ('core', 'swing', 'event');
CREATE TYPE recommendation_status AS ENUM ('pending', 'approved', 'rejected', 'deferred');

CREATE TABLE watchlist_items (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(16) NOT NULL,
    bucket bucket_type NOT NULL,
    thesis TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
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
    status recommendation_status NOT NULL DEFAULT 'pending',
    watchlist_item_id BIGINT REFERENCES watchlist_items(id) ON DELETE SET NULL,
    mock_price NUMERIC(12, 2),
    market_snapshot JSONB,
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
    recommendation_id BIGINT REFERENCES recommendations(id) ON DELETE SET NULL,
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
CREATE INDEX ix_recommendations_symbol ON recommendations(symbol);
CREATE INDEX ix_recommendations_bucket ON recommendations(bucket);
CREATE INDEX ix_recommendations_status ON recommendations(status);
CREATE INDEX ix_journal_entries_symbol ON journal_entries(symbol);
CREATE INDEX ix_audit_logs_event_type ON audit_logs(event_type);
