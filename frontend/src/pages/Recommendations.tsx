import { useEffect, useMemo, useState } from "react";
import { decideRecommendation, generateSwingRecommendations, listRecommendations, scanPotentialCandidates } from "../api/client";
import type {
  BucketType,
  PotentialCandidate,
  Recommendation,
  RecommendationDecisionRequest,
  RecommendationDecisionStatus
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { LoadingState } from "../components/LoadingState";
import { RecommendationCard } from "../components/RecommendationCard";
import { labelBucket } from "../utils/labels";

const decisionOptions: Array<RecommendationDecisionStatus | "all"> = [
  "all",
  "pending",
  "approved",
  "rejected",
  "deferred"
];

export function Recommendations() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [potentialCandidates, setPotentialCandidates] = useState<PotentialCandidate[]>([]);
  const [bucket, setBucket] = useState<BucketType | "all">("all");
  const [decisionStatus, setDecisionStatus] = useState<RecommendationDecisionStatus | "all">("pending");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [potentialLoading, setPotentialLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setMessage(null);
    try {
      const items = await listRecommendations({
        bucket: bucket === "all" ? undefined : bucket,
        decision_status: decisionStatus === "all" ? undefined : decisionStatus
      });
      setRecommendations(items);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load recommendations.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [bucket, decisionStatus]);

  async function loadPotential() {
    setPotentialLoading(true);
    setMessage(null);
    try {
      const result = await scanPotentialCandidates({
        bucket: bucket === "all" ? undefined : bucket,
        limit: 12
      });
      setPotentialCandidates(result.candidates);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to scan potential candidates.");
    } finally {
      setPotentialLoading(false);
    }
  }

  useEffect(() => {
    void loadPotential();
  }, [bucket]);

  const sortedRecommendations = useMemo(
    () =>
      [...recommendations].sort((a, b) => {
        const pendingWeight = Number(b.decision_status === "pending") - Number(a.decision_status === "pending");
        return pendingWeight || b.confidence_score - a.confidence_score;
      }),
    [recommendations]
  );
  const pendingCount = recommendations.filter((recommendation) => recommendation.decision_status === "pending").length;
  const allowedCount = recommendations.filter((recommendation) => recommendation.compliance_status === "allowed").length;
  const emergingCandidates = potentialCandidates.filter((candidate) => candidate.setup_stage === "emerging_potential");
  const lateMomentumCandidates = potentialCandidates.filter((candidate) => candidate.setup_stage === "late_momentum");

  async function handleDecision(id: number, decision: RecommendationDecisionRequest["decision"]) {
    setBusyId(id);
    try {
      await decideRecommendation(id, {
        decision,
        reason: `Marked ${decision} from frontend MVP.`,
        decided_at: new Date().toISOString()
      });
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to update recommendation.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleGenerate() {
    setMessage("Generating swing recommendations...");
    try {
      await generateSwingRecommendations();
      await load();
      setMessage("Swing queue updated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to generate recommendations.");
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Recommendations</p>
          <h2>Manual decision queue</h2>
        </div>
        <div className="button-row">
          <button onClick={loadPotential} disabled={potentialLoading}>
            {potentialLoading ? "Scanning..." : "Scan potential"}
          </button>
          <button onClick={handleGenerate}>Generate swing ideas</button>
        </div>
      </div>

      <FilterBar
        bucket={bucket}
        status={decisionStatus}
        statusOptions={decisionOptions}
        onBucketChange={setBucket}
        onStatusChange={(value) => setDecisionStatus(value as RecommendationDecisionStatus | "all")}
      />

      {message ? <p className="notice">{message}</p> : null}
      {loading ? <LoadingState label="Loading decision queue..." /> : null}

      <div className="decision-dashboard">
        <div>
          <span>Visible ideas</span>
          <strong>{recommendations.length}</strong>
        </div>
        <div>
          <span>Pending decisions</span>
          <strong>{pendingCount}</strong>
        </div>
        <div>
          <span>Compliance allowed</span>
          <strong>{allowedCount}</strong>
        </div>
      </div>

      <section className="potential-discovery">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Potential discovery</p>
            <h3>Emerging setups, not buy signals</h3>
          </div>
          <p>
            This scan reviews the active watchlist universe, including names outside the current recommendation queue.
            Late momentum is separated so already-hot moves do not crowd out earlier setups.
          </p>
        </div>

        {potentialLoading ? <LoadingState label="Scanning active watchlist for developing setups..." /> : null}

        {!potentialLoading && potentialCandidates.length === 0 ? (
          <EmptyState title="No potential candidates found" detail="Add active watchlist symbols or refresh market data, then scan again." />
        ) : null}

        {emergingCandidates.length > 0 ? (
          <>
            <h4 className="subsection-title">Emerging potential</h4>
            <div className="potential-grid">
              {emergingCandidates.map((candidate) => (
                <PotentialCandidateCard key={`${candidate.symbol}-emerging`} candidate={candidate} />
              ))}
            </div>
          </>
        ) : null}

        {lateMomentumCandidates.length > 0 ? (
          <>
            <h4 className="subsection-title">Late momentum watchlist</h4>
            <div className="potential-grid">
              {lateMomentumCandidates.map((candidate) => (
                <PotentialCandidateCard key={`${candidate.symbol}-late`} candidate={candidate} />
              ))}
            </div>
          </>
        ) : null}
      </section>

      {!loading && sortedRecommendations.length === 0 ? (
        <EmptyState title="No recommendations found" detail="Adjust filters or generate a fresh swing queue." />
      ) : null}

      <div className="card-grid decision-card-grid">
        {sortedRecommendations.map((recommendation) => (
          <RecommendationCard
            key={recommendation.id}
            recommendation={recommendation}
            busy={busyId === recommendation.id}
            onDecision={handleDecision}
          />
        ))}
      </div>
    </section>
  );
}

function formatPercentScore(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function formatMetric(value: number | null, suffix = ""): string {
  if (value === null) return "n/a";
  return `${value.toFixed(2)}${suffix}`;
}

function labelFlag(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function PotentialCandidateCard({ candidate }: { candidate: PotentialCandidate }) {
  const isLate = candidate.setup_stage === "late_momentum";
  return (
    <article className={`potential-card ${candidate.setup_stage}`}>
      <div className="card-heading">
        <div>
          <p className="meta-line">
            {labelBucket(candidate.bucket)} / {candidate.stage_label}
          </p>
          <h3>{candidate.symbol}</h3>
        </div>
        <span className={`status-pill ${candidate.potential_flag}`}>{labelFlag(candidate.potential_flag)}</span>
      </div>
      <div className="potential-heading">
        <div>
          <span>{isLate ? "Late momentum score" : "Potential score"}</span>
          <strong>{formatPercentScore(candidate.potential_score)}</strong>
        </div>
        <div>
          <span>Snapshot</span>
          <strong>{formatCurrency(candidate.market_snapshot.snapshot_price)}</strong>
        </div>
      </div>
      <p>{candidate.rationale}</p>
      <div className="market-mini-grid">
        <span>Price vs MA20 <strong>{formatMetric(candidate.metrics.price_vs_ma20_pct, "%")}</strong></span>
        <span>MA20 vs MA50 <strong>{formatMetric(candidate.metrics.ma20_vs_ma50_pct, "%")}</strong></span>
        <span>RSI <strong>{formatMetric(candidate.metrics.rsi_14)}</strong></span>
        <span>Volume <strong>{formatMetric(candidate.metrics.volume_ratio, "x")}</strong></span>
      </div>
      <small>{candidate.warning}</small>
    </article>
  );
}
