import { FormEvent, useEffect, useMemo, useState } from "react";
import { createWatchlistItem, listMarketSnapshots, listRecommendations, listWatchlistItems } from "../api/client";
import type { BucketType, MarketSnapshot, Recommendation, WatchlistItem, WatchlistStatus } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { LoadingState } from "../components/LoadingState";
import { labelAction, labelBucket, labelSetup, labelWatchlistStatus } from "../utils/labels";

const statusOptions: Array<WatchlistStatus | "all"> = ["all", "watching", "candidate", "approved", "archived"];

function formatCurrency(value: number | null): string {
  if (value === null) return "n/a";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1
  }).format(value);
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString();
}

function getSnapshotSourceLabel(snapshot: MarketSnapshot): string {
  if (snapshot.data_source_type === "seeded" || snapshot.data_provider === "seed-data") {
    return "Seeded demo data";
  }
  if (snapshot.data_provider === "yahoo") return "Yahoo-backed market data";
  return "Provider-backed market data";
}

function getSnapshotFreshnessLabel(snapshot: MarketSnapshot): string {
  if (snapshot.data_source_type === "provider_delayed") return "May be delayed";
  if (snapshot.data_source_type === "seeded") return "Demo values";
  return "Research mode";
}

export function Watchlist() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [marketSnapshots, setMarketSnapshots] = useState<MarketSnapshot[]>([]);
  const [bucket, setBucket] = useState<BucketType | "all">("all");
  const [status, setStatus] = useState<WatchlistStatus | "all">("all");
  const [symbol, setSymbol] = useState("");
  const [newBucket, setNewBucket] = useState<BucketType>("swing");
  const [thesis, setThesis] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setMessage(null);
    try {
      const [data, recommendationData, snapshotData] = await Promise.all([
        listWatchlistItems({
          bucket: bucket === "all" ? undefined : bucket
        }),
        listRecommendations(),
        listMarketSnapshots()
      ]);
      setItems(data);
      setRecommendations(recommendationData);
      setMarketSnapshots(snapshotData);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load watchlist.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [bucket]);

  const filteredItems = useMemo(
    () => items.filter((item) => status === "all" || item.status === status),
    [items, status]
  );
  const recommendationsByWatchlist = useMemo(() => {
    const map = new Map<number, Recommendation>();
    for (const recommendation of recommendations) {
      if (recommendation.watchlist_item_id && !map.has(recommendation.watchlist_item_id)) {
        map.set(recommendation.watchlist_item_id, recommendation);
      }
    }
    return map;
  }, [recommendations]);
  const snapshotsByWatchlistId = useMemo(() => {
    const map = new Map<number, MarketSnapshot>();
    for (const snapshot of marketSnapshots) {
      if (snapshot.watchlist_item_id !== null && !map.has(snapshot.watchlist_item_id)) {
        map.set(snapshot.watchlist_item_id, snapshot);
      }
    }
    return map;
  }, [marketSnapshots]);
  const snapshotsBySymbol = useMemo(() => {
    const map = new Map<string, MarketSnapshot>();
    for (const snapshot of marketSnapshots) {
      const key = snapshot.symbol.toUpperCase();
      if (!map.has(key)) map.set(key, snapshot);
    }
    return map;
  }, [marketSnapshots]);

  function getLinkedRecommendation(item: WatchlistItem): Recommendation | undefined {
    return (
      recommendationsByWatchlist.get(item.id) ??
      recommendations.find((recommendation) => recommendation.symbol.toUpperCase() === item.symbol.toUpperCase())
    );
  }

  function getLatestSnapshot(item: WatchlistItem): MarketSnapshot | undefined {
    return snapshotsByWatchlistId.get(item.id) ?? snapshotsBySymbol.get(item.symbol.toUpperCase());
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    try {
      await createWatchlistItem({
        symbol: symbol.trim().toUpperCase(),
        bucket: newBucket,
        status: "watching",
        thesis: thesis.trim() || null
      });
      setSymbol("");
      setThesis("");
      await load();
      setMessage("Watchlist item added.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to add watchlist item.");
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Watchlist</p>
          <h2>Names under review</h2>
        </div>
      </div>

      <form className="inline-form" onSubmit={handleSubmit}>
        <label>
          Symbol
          <input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="MSFT" required />
        </label>
        <label>
          Bucket
          <select value={newBucket} onChange={(event) => setNewBucket(event.target.value as BucketType)}>
            <option value="core">Core</option>
            <option value="swing">Swing</option>
            <option value="event">Event</option>
          </select>
        </label>
        <label className="wide-field">
          Thesis
          <input value={thesis} onChange={(event) => setThesis(event.target.value)} placeholder="Clean breakout watch" />
        </label>
        <button type="submit">Add</button>
      </form>

      <FilterBar
        bucket={bucket}
        status={status}
        statusOptions={statusOptions}
        onBucketChange={setBucket}
        onStatusChange={(value) => setStatus(value as WatchlistStatus | "all")}
      />

      {message ? <p className="notice">{message}</p> : null}
      {loading ? <LoadingState label="Loading watchlist context..." /> : null}

      {!loading && filteredItems.length === 0 ? (
        <EmptyState title="No watchlist items" detail="Add a symbol or loosen the active filters." />
      ) : null}

      <div className="watchlist-grid">
        {filteredItems.map((item) => {
          const linkedRecommendation = getLinkedRecommendation(item);
          const latestSnapshot = getLatestSnapshot(item);

          return (
            <article className="watchlist-card" key={item.id}>
              <div className="card-heading">
                <div>
                  <p className="meta-line">{labelBucket(item.bucket)}</p>
                  <h3>{item.symbol}</h3>
                </div>
                <span className={`status-pill ${item.status}`}>{labelWatchlistStatus(item.status)}</span>
              </div>
              <p>{item.thesis ?? "No thesis yet."}</p>
              <div className="field-grid">
                <div>
                  <span>Active</span>
                  <strong>{item.is_active ? "yes" : "no"}</strong>
                </div>
                <div>
                  <span>Updated</span>
                  <strong>{new Date(item.updated_at).toLocaleDateString()}</strong>
                </div>
              </div>
              {latestSnapshot ? (
                <section className="linked-recommendation">
                  <div className="market-context-heading">
                    <h4>Market snapshot</h4>
                    <div className="source-badges">
                      <span>{getSnapshotSourceLabel(latestSnapshot)}</span>
                      <span>{getSnapshotFreshnessLabel(latestSnapshot)}</span>
                    </div>
                  </div>
                  <div className="market-mini-grid">
                    <span>Price {formatCurrency(latestSnapshot.latest_price ?? latestSnapshot.mock_price)}</span>
                    <span>Change {formatPercent(latestSnapshot.daily_change_pct)}</span>
                    <span>Volume {formatCompactNumber(latestSnapshot.volume)}</span>
                    <span>Earnings {latestSnapshot.earnings_date ? new Date(latestSnapshot.earnings_date).toLocaleDateString() : "n/a"}</span>
                    <span>Source {latestSnapshot.data_provider}</span>
                    <span>Type {latestSnapshot.data_source_type}</span>
                    <span>Refreshed {formatDateTime(latestSnapshot.refreshed_at)}</span>
                  </div>
                  {latestSnapshot.data_delay_note ? <small>{latestSnapshot.data_delay_note}</small> : null}
                </section>
              ) : null}
              {linkedRecommendation ? (
                <section className="linked-recommendation">
                  <h4>Linked recommendation</h4>
                  <p>
                    {labelAction(linkedRecommendation.recommendation_action)} / {labelSetup(linkedRecommendation.setup_type)} /{" "}
                    {Math.round(linkedRecommendation.confidence_score * 100)}% confidence
                  </p>
                  <small>{linkedRecommendation.why_now}</small>
                </section>
              ) : (
                <section className="linked-recommendation muted-panel">
                  <h4>Linked recommendation</h4>
                  <p>No recommendation linked yet.</p>
                </section>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
