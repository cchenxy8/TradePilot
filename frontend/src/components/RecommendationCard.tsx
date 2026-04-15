import type { Recommendation, RecommendationDecisionRequest } from "../api/types";
import { labelAction, labelBucket, labelCompliance, labelDecision, labelSetup } from "../utils/labels";

interface RecommendationCardProps {
  recommendation: Recommendation;
  busy?: boolean;
  compact?: boolean;
  onDecision?: (id: number, decision: RecommendationDecisionRequest["decision"]) => void;
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatCurrency(value: number | null): string {
  if (value === null) return "n/a";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function formatCompactNumber(value: unknown): string {
  if (typeof value !== "number") return "n/a";
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1
  }).format(value);
}

function formatChange(value: unknown): string {
  if (typeof value !== "number") return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatDate(value: unknown): string {
  if (typeof value !== "string" || value.length === 0) return "n/a";
  return new Date(value).toLocaleDateString();
}

function formatDateTime(value: unknown): string {
  if (typeof value !== "string" || value.length === 0) return "n/a";
  return new Date(value).toLocaleString();
}

function getSnapshotRows(snapshot: Record<string, unknown> | null): Array<[string, string]> {
  if (!snapshot) return [];
  return [
    ["Daily change", formatChange(snapshot.daily_change_pct)],
    ["Volume", formatCompactNumber(snapshot.volume)],
    ["RSI 14", typeof snapshot.rsi_14 === "number" ? snapshot.rsi_14.toFixed(1) : "n/a"],
    ["Earnings", formatDate(snapshot.earnings_date)]
  ];
}

function getDelayNote(snapshot: Record<string, unknown> | null): string | null {
  if (!snapshot || typeof snapshot.delay_note !== "string") return null;
  return snapshot.delay_note;
}

function getSourceLabel(snapshot: Record<string, unknown> | null): string {
  if (!snapshot) return "Market data";
  if (snapshot.provider === "seed-data" || snapshot.source_type === "seeded") return "Seeded demo data";
  if (snapshot.provider === "yahoo") return "Yahoo-backed market data";
  return "Provider-backed market data";
}

function getFreshnessLabel(snapshot: Record<string, unknown> | null): string {
  if (!snapshot) return "Refresh status unavailable";
  if (snapshot.source_type === "provider_delayed") return "May be delayed";
  if (snapshot.source_type === "seeded") return "Demo values";
  return "Research mode";
}

function getRefreshedLabel(snapshot: Record<string, unknown> | null): string | null {
  if (!snapshot || typeof snapshot.refreshed_at !== "string") return null;
  return `Last refreshed ${formatDateTime(snapshot.refreshed_at)}`;
}

export function RecommendationCard({ recommendation, busy = false, compact = false, onDecision }: RecommendationCardProps) {
  const canDecide = recommendation.decision_status === "pending" && onDecision;
  const snapshotRows = getSnapshotRows(recommendation.market_snapshot);
  const delayNote = getDelayNote(recommendation.market_snapshot);
  const refreshedLabel = getRefreshedLabel(recommendation.market_snapshot);

  return (
    <article className={`recommendation-card ${compact ? "compact-card" : ""}`}>
      <div className="card-heading">
        <div>
          <p className="meta-line">
            {labelBucket(recommendation.bucket)} / {labelSetup(recommendation.setup_type)}
          </p>
          <h3>{recommendation.symbol}</h3>
        </div>
        <div className="card-badges">
          <span className={`action-badge ${recommendation.recommendation_action}`}>
            {labelAction(recommendation.recommendation_action)}
          </span>
          <span className={`status-pill ${recommendation.decision_status}`}>
            {labelDecision(recommendation.decision_status)}
          </span>
        </div>
      </div>

      <div className="decision-strip">
        <div className="confidence-metric">
          <span>Confidence</span>
          <strong>{formatPercent(recommendation.confidence_score)}</strong>
        </div>
        <div className={`compliance-metric ${recommendation.compliance_status}`}>
          <span>Compliance</span>
          <strong>{labelCompliance(recommendation.compliance_status)}</strong>
        </div>
        <div>
          <span>Snapshot price</span>
          <strong>{formatCurrency(recommendation.latest_price ?? recommendation.mock_price)}</strong>
        </div>
      </div>

      <section className="card-copy">
        <h4>Why now</h4>
        <p>{recommendation.why_now}</p>
      </section>

      <section className="card-copy risk-copy">
        <h4>Risk notes</h4>
        <p>{recommendation.risk_notes}</p>
      </section>

      {!compact && snapshotRows.length > 0 ? (
        <section className="market-context">
          <div className="market-context-heading">
            <h4>Market context</h4>
            <div className="source-badges">
              <span>{getSourceLabel(recommendation.market_snapshot)}</span>
              <span>{getFreshnessLabel(recommendation.market_snapshot)}</span>
            </div>
          </div>
          <div className="snapshot-grid">
            {snapshotRows.map(([key, value]) => (
              <div key={key}>
                <span>{key}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          {refreshedLabel ? <p className="source-note">{refreshedLabel}</p> : null}
          {delayNote ? <p className="source-note">{delayNote}</p> : null}
        </section>
      ) : null}

      {canDecide ? (
        <div className="decision-actions" aria-label={`Decision actions for ${recommendation.symbol}`}>
          <button className="approve-action" disabled={busy} onClick={() => onDecision(recommendation.id, "approved")}>
            Approve
          </button>
          <button disabled={busy} className="defer-action" onClick={() => onDecision(recommendation.id, "deferred")}>
            Defer
          </button>
          <button disabled={busy} className="reject-action" onClick={() => onDecision(recommendation.id, "rejected")}>
            Reject
          </button>
        </div>
      ) : null}
    </article>
  );
}
