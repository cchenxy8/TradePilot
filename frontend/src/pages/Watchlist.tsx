import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createWatchlistItem,
  listMarketSnapshots,
  listRecommendations,
  listWatchlistItems,
  updateWatchlistItem
} from "../api/client";
import type { BucketType, MarketSnapshot, Recommendation, WatchlistItem, WatchlistStatus } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { LoadingState } from "../components/LoadingState";
import { labelAction, labelBucket, labelSetup, labelWatchlistStatus } from "../utils/labels";

const statusOptions: Array<WatchlistStatus | "all"> = ["all", "watching", "candidate", "approved", "archived"];
const workflowStatusOptions: WatchlistStatus[] = ["watching", "candidate", "approved", "archived"];
const bucketOptions: BucketType[] = ["core", "swing", "event"];

type WatchlistDraft = {
  bucket: BucketType;
  status: WatchlistStatus;
  thesis: string;
  next_step: string;
  trigger_condition: string;
  is_active: boolean;
};

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
  const [nextStep, setNextStep] = useState("");
  const [triggerCondition, setTriggerCondition] = useState("");
  const [drafts, setDrafts] = useState<Record<number, WatchlistDraft>>({});
  const [savingId, setSavingId] = useState<number | null>(null);
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

  useEffect(() => {
    setDrafts(
      Object.fromEntries(
        items.map((item) => [
          item.id,
          {
            bucket: item.bucket,
            status: item.status,
            thesis: item.thesis ?? "",
            next_step: item.next_step ?? "",
            trigger_condition: item.trigger_condition ?? "",
            is_active: item.is_active
          }
        ])
      )
    );
  }, [items]);

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
        thesis: thesis.trim() || null,
        next_step: nextStep.trim() || null,
        trigger_condition: triggerCondition.trim() || null
      });
      setSymbol("");
      setThesis("");
      setNextStep("");
      setTriggerCondition("");
      await load();
      setMessage("Watchlist item added.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to add watchlist item.");
    }
  }

  function updateDraft<K extends keyof WatchlistDraft>(itemId: number, field: K, value: WatchlistDraft[K]) {
    setDrafts((current) => ({
      ...current,
      [itemId]: {
        ...(current[itemId] ?? {
          bucket: "swing",
          status: "watching",
          thesis: "",
          next_step: "",
          trigger_condition: "",
          is_active: true
        }),
        [field]: value
      }
    }));
  }

  function hasDraftChanges(item: WatchlistItem, draft: WatchlistDraft | undefined): boolean {
    if (!draft) return false;
    return (
      draft.bucket !== item.bucket ||
      draft.status !== item.status ||
      draft.thesis !== (item.thesis ?? "") ||
      draft.next_step !== (item.next_step ?? "") ||
      draft.trigger_condition !== (item.trigger_condition ?? "") ||
      draft.is_active !== item.is_active
    );
  }

  async function handleSave(item: WatchlistItem) {
    const draft = drafts[item.id];
    if (!draft) return;

    setSavingId(item.id);
    setMessage(null);
    try {
      await updateWatchlistItem(item.id, {
        bucket: draft.bucket,
        status: draft.status,
        thesis: draft.thesis.trim() || null,
        next_step: draft.next_step.trim() || null,
        trigger_condition: draft.trigger_condition.trim() || null,
        is_active: draft.is_active
      });
      await load();
      setMessage(`${item.symbol} workflow updated.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to update watchlist item.");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Watchlist</p>
          <h2>Research workspace</h2>
          <p className="page-subtitle">Track the reason, status, next move, and trigger for every name under review.</p>
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
            {bucketOptions.map((option) => (
              <option value={option} key={option}>
                {labelBucket(option)}
              </option>
            ))}
          </select>
        </label>
        <label className="wide-field">
          Why watching
          <input value={thesis} onChange={(event) => setThesis(event.target.value)} placeholder="Clean breakout watch" />
        </label>
        <label className="wide-field">
          Next step
          <input value={nextStep} onChange={(event) => setNextStep(event.target.value)} placeholder="Review after close" />
        </label>
        <label className="wide-field">
          Trigger
          <input
            value={triggerCondition}
            onChange={(event) => setTriggerCondition(event.target.value)}
            placeholder="Hold above 20-day average on volume"
          />
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
          const draft = drafts[item.id];
          const changed = hasDraftChanges(item, draft);

          return (
            <article className="watchlist-card" key={item.id}>
              <div className="card-heading">
                <div>
                  <p className="meta-line">{labelBucket(item.bucket)}</p>
                  <h3>{item.symbol}</h3>
                </div>
                <span className={`status-pill ${item.status}`}>{labelWatchlistStatus(item.status)}</span>
              </div>
              <div className="watchlist-controls">
                <label>
                  Bucket
                  <select
                    value={draft?.bucket ?? item.bucket}
                    onChange={(event) => updateDraft(item.id, "bucket", event.target.value as BucketType)}
                  >
                    {bucketOptions.map((option) => (
                      <option value={option} key={option}>
                        {labelBucket(option)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Status
                  <select
                    value={draft?.status ?? item.status}
                    onChange={(event) => updateDraft(item.id, "status", event.target.value as WatchlistStatus)}
                  >
                    {workflowStatusOptions.map((option) => (
                      <option value={option} key={option}>
                        {labelWatchlistStatus(option)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="active-toggle">
                  <input
                    type="checkbox"
                    checked={draft?.is_active ?? item.is_active}
                    onChange={(event) => updateDraft(item.id, "is_active", event.target.checked)}
                  />
                  Active
                </label>
              </div>
              <section className="research-workflow">
                <label>
                  Why watching
                  <textarea
                    value={draft?.thesis ?? ""}
                    onChange={(event) => updateDraft(item.id, "thesis", event.target.value)}
                    placeholder="No reason captured yet."
                  />
                </label>
                <div className="workflow-pair">
                  <label>
                    Next step
                    <textarea
                      value={draft?.next_step ?? ""}
                      onChange={(event) => updateDraft(item.id, "next_step", event.target.value)}
                      placeholder="No next step yet."
                    />
                  </label>
                  <label>
                    Trigger
                    <textarea
                      value={draft?.trigger_condition ?? ""}
                      onChange={(event) => updateDraft(item.id, "trigger_condition", event.target.value)}
                      placeholder="No trigger defined yet."
                    />
                  </label>
                </div>
                <div className="workflow-actions">
                  <span>{changed ? "Unsaved changes" : `Updated ${new Date(item.updated_at).toLocaleDateString()}`}</span>
                  <button type="button" onClick={() => void handleSave(item)} disabled={!changed || savingId === item.id}>
                    {savingId === item.id ? "Saving..." : "Save workflow"}
                  </button>
                </div>
              </section>
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
