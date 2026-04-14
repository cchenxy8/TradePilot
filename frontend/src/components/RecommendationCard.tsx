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

function getSnapshotRows(snapshot: Record<string, unknown> | null): Array<[string, string]> {
  if (!snapshot) return [];
  return Object.entries(snapshot)
    .filter(([, value]) => value !== null && value !== undefined && typeof value !== "object")
    .slice(0, 4)
    .map(([key, value]) => [key.replaceAll("_", " "), String(value)]);
}

export function RecommendationCard({ recommendation, busy = false, compact = false, onDecision }: RecommendationCardProps) {
  const canDecide = recommendation.decision_status === "pending" && onDecision;
  const snapshotRows = getSnapshotRows(recommendation.market_snapshot);

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
          <span>Mock price</span>
          <strong>{formatCurrency(recommendation.mock_price)}</strong>
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
          <h4>Market context</h4>
          <div className="snapshot-grid">
            {snapshotRows.map(([key, value]) => (
              <div key={key}>
                <span>{key}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
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
