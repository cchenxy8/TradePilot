import { useEffect, useMemo, useState } from "react";
import {
  generateSwingRecommendations,
  listJournalEntries,
  listRecommendations,
  listWatchlistItems,
  seedDemoData
} from "../api/client";
import type { JournalEntry, Recommendation, WatchlistItem } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { MetricCard } from "../components/MetricCard";
import { RecommendationCard } from "../components/RecommendationCard";
import { labelBucket } from "../utils/labels";

interface DashboardProps {
  onNavigate: (page: "watchlist" | "recommendations" | "journal") => void;
}

export function Dashboard({ onNavigate }: DashboardProps) {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setMessage(null);
    try {
      const [watchlistItems, recommendationItems, journalEntries] = await Promise.all([
        listWatchlistItems(),
        listRecommendations(),
        listJournalEntries()
      ]);
      setWatchlist(watchlistItems);
      setRecommendations(recommendationItems);
      setJournal(journalEntries);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load dashboard.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const pending = useMemo(
    () => recommendations.filter((recommendation) => recommendation.decision_status === "pending"),
    [recommendations]
  );
  const approved = recommendations.filter((recommendation) => recommendation.decision_status === "approved").length;
  const rejected = recommendations.filter((recommendation) => recommendation.decision_status === "rejected").length;
  const deferred = recommendations.filter((recommendation) => recommendation.decision_status === "deferred").length;
  const bucketCounts = {
    core: recommendations.filter((recommendation) => recommendation.bucket === "core").length,
    swing: recommendations.filter((recommendation) => recommendation.bucket === "swing").length,
    event: recommendations.filter((recommendation) => recommendation.bucket === "event").length
  };
  const priorityPending = useMemo(
    () =>
      [...pending]
        .sort((a, b) => {
          const complianceWeight = Number(b.compliance_status === "allowed") - Number(a.compliance_status === "allowed");
          return complianceWeight || b.confidence_score - a.confidence_score;
        })
        .slice(0, 4),
    [pending]
  );

  async function handleSeed() {
    setMessage("Seeding demo data...");
    try {
      await seedDemoData();
      await load();
      setMessage("Demo data is ready.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to seed demo data.");
    }
  }

  async function handleGenerate() {
    setMessage("Generating swing queue...");
    try {
      await generateSwingRecommendations();
      await load();
      setMessage("Swing recommendations refreshed.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to generate recommendations.");
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h2>Today&apos;s research flow</h2>
        </div>
        <div className="button-row">
          <button onClick={handleSeed}>Seed demo data</button>
          <button className="secondary" onClick={handleGenerate}>
            Generate swing ideas
          </button>
        </div>
      </div>

      {message ? <p className="notice">{message}</p> : null}

      {loading ? <LoadingState label="Loading dashboard..." /> : null}

      <div className="metrics-grid status-metrics">
        <MetricCard label="Watchlist" value={watchlist.length} hint="tracked names" />
        <MetricCard label="Journal" value={journal.length} hint="planning notes" />
        <MetricCard label="Pending" value={pending.length} hint="need a decision" />
        <MetricCard label="Approved" value={approved} hint="ready for manual follow-up" />
        <MetricCard label="Rejected" value={rejected} hint="ruled out" />
        <MetricCard label="Deferred" value={deferred} hint="later review" />
      </div>

      <div className="section-panel">
        <div className="section-heading">
          <h3>Bucket distribution</h3>
        </div>
        <div className="bucket-grid">
          {Object.entries(bucketCounts).map(([bucketName, count]) => (
            <div key={bucketName} className="bucket-row">
              <span>{labelBucket(bucketName as keyof typeof bucketCounts)}</span>
              <div>
                <span style={{ width: `${recommendations.length ? (count / recommendations.length) * 100 : 0}%` }} />
              </div>
              <strong>{count}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="section-heading">
        <h3>Highest-priority pending recommendations</h3>
        <button className="text-button" onClick={() => onNavigate("recommendations")}>
          Open queue
        </button>
      </div>

      {!loading && priorityPending.length === 0 ? (
        <EmptyState title="No pending recommendations" detail="Generate swing ideas or seed demo data to fill the queue." />
      ) : null}

      <div className="card-grid">
        {priorityPending.map((recommendation) => (
          <RecommendationCard key={recommendation.id} recommendation={recommendation} compact />
        ))}
      </div>
    </section>
  );
}
