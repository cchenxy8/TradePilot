import { FormEvent, useEffect, useMemo, useState } from "react";
import { createWatchlistItem, listRecommendations, listWatchlistItems } from "../api/client";
import type { BucketType, Recommendation, WatchlistItem, WatchlistStatus } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { LoadingState } from "../components/LoadingState";
import { labelAction, labelBucket, labelSetup, labelWatchlistStatus } from "../utils/labels";

const statusOptions: Array<WatchlistStatus | "all"> = ["all", "watching", "candidate", "approved", "archived"];

export function Watchlist() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
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
      const [data, recommendationData] = await Promise.all([
        listWatchlistItems({
          bucket: bucket === "all" ? undefined : bucket
        }),
        listRecommendations()
      ]);
      setItems(data);
      setRecommendations(recommendationData);
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

  function getLinkedRecommendation(item: WatchlistItem): Recommendation | undefined {
    return (
      recommendationsByWatchlist.get(item.id) ??
      recommendations.find((recommendation) => recommendation.symbol.toUpperCase() === item.symbol.toUpperCase())
    );
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
