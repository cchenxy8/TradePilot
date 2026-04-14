import { useEffect, useMemo, useState } from "react";
import { decideRecommendation, generateSwingRecommendations, listRecommendations } from "../api/client";
import type { BucketType, Recommendation, RecommendationDecisionRequest, RecommendationDecisionStatus } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { LoadingState } from "../components/LoadingState";
import { RecommendationCard } from "../components/RecommendationCard";

const decisionOptions: Array<RecommendationDecisionStatus | "all"> = [
  "all",
  "pending",
  "approved",
  "rejected",
  "deferred"
];

export function Recommendations() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [bucket, setBucket] = useState<BucketType | "all">("all");
  const [decisionStatus, setDecisionStatus] = useState<RecommendationDecisionStatus | "all">("pending");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
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
        <button onClick={handleGenerate}>Generate swing ideas</button>
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
