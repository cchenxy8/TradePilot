import { FormEvent, useEffect, useState } from "react";
import { createJournalEntry, listJournalEntries } from "../api/client";
import type { BucketType, JournalEntry } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { labelBucket } from "../utils/labels";

function optionalNumber(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}

function formatPrice(value: number | null): string {
  if (value === null) return "Not set";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2
  }).format(value);
}

function formatPositionSize(value: number | null): string {
  if (value === null) return "Not set";
  return `${value}%`;
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

function getEntryPreview(entry: JournalEntry): { label: string; text: string } {
  const source = entry.outcome_note?.trim()
    ? { label: "Outcome preview", text: entry.outcome_note }
    : { label: "Plan preview", text: entry.content };
  const normalized = source.text.replace(/\s+/g, " ").trim();
  return {
    label: source.label,
    text: normalized.length > 150 ? `${normalized.slice(0, 150)}...` : normalized
  };
}

export function Journal() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [title, setTitle] = useState("");
  const [symbol, setSymbol] = useState("");
  const [bucket, setBucket] = useState<BucketType | "">("");
  const [content, setContent] = useState("");
  const [plannedEntry, setPlannedEntry] = useState("");
  const [plannedExit, setPlannedExit] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [positionSizePct, setPositionSizePct] = useState("");
  const [outcomeNote, setOutcomeNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setMessage(null);
    try {
      setEntries(await listJournalEntries());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load journal.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    try {
      const savedEntry = await createJournalEntry({
        title,
        content,
        symbol: symbol.trim().toUpperCase() || null,
        bucket: bucket || null,
        planned_entry: optionalNumber(plannedEntry),
        planned_exit: optionalNumber(plannedExit),
        stop_loss: optionalNumber(stopLoss),
        position_size_pct: optionalNumber(positionSizePct),
        outcome_note: outcomeNote.trim() || null
      });
      setEntries((currentEntries) => [savedEntry, ...currentEntries.filter((entry) => entry.id !== savedEntry.id)]);
      setTitle("");
      setSymbol("");
      setBucket("");
      setContent("");
      setPlannedEntry("");
      setPlannedExit("");
      setStopLoss("");
      setPositionSizePct("");
      setOutcomeNote("");
      setMessage("Journal entry saved.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save journal entry.");
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Journal</p>
          <h2>Plan and review</h2>
        </div>
      </div>

      <div className="journal-layout">
        <form className="journal-form" onSubmit={handleSubmit}>
          <div className="form-heading full-field">
            <div>
              <p className="eyebrow">Planning tool</p>
              <h3>New trade plan</h3>
            </div>
            <span>{entries.length} saved</span>
          </div>
          <label>
            Title
            <input value={title} onChange={(event) => setTitle(event.target.value)} required />
          </label>
          <label>
            Symbol
            <input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="NVDA" />
          </label>
          <label>
            Bucket
            <select value={bucket} onChange={(event) => setBucket(event.target.value as BucketType | "")}>
              <option value="">None</option>
              <option value="core">Core</option>
              <option value="swing">Swing</option>
              <option value="event">Event</option>
            </select>
          </label>
          <label>
            Planned entry
            <input value={plannedEntry} type="number" step="0.01" onChange={(event) => setPlannedEntry(event.target.value)} />
          </label>
          <label>
            Planned exit
            <input value={plannedExit} type="number" step="0.01" onChange={(event) => setPlannedExit(event.target.value)} />
          </label>
          <label>
            Stop loss
            <input value={stopLoss} type="number" step="0.01" onChange={(event) => setStopLoss(event.target.value)} />
          </label>
          <label>
            Position %
            <input
              value={positionSizePct}
              type="number"
              step="0.01"
              onChange={(event) => setPositionSizePct(event.target.value)}
            />
          </label>
          <label className="full-field">
            Plan
            <textarea value={content} onChange={(event) => setContent(event.target.value)} required />
          </label>
          <label className="full-field">
            Outcome note
            <textarea value={outcomeNote} onChange={(event) => setOutcomeNote(event.target.value)} />
          </label>
          <button type="submit">Save entry</button>
        </form>
      </div>

      {message ? <p className="notice">{message}</p> : null}
      {loading ? <LoadingState label="Loading saved journal entries..." /> : null}

      <div className="section-heading">
        <div>
          <p className="eyebrow">Saved log</p>
          <h3>Journal entries</h3>
        </div>
      </div>

      {!loading && entries.length === 0 ? (
        <EmptyState title="No journal entries" detail="Save a plan to start tracking manual trade decisions." />
      ) : null}

      <div className="journal-list">
        {entries.map((entry) => {
          const preview = getEntryPreview(entry);

          return (
            <article key={entry.id} className="journal-entry">
              <div className="journal-entry-header">
                <div>
                  <p className="meta-line">
                    {[entry.symbol ?? "General", entry.bucket ? labelBucket(entry.bucket) : null].filter(Boolean).join(" / ")}
                  </p>
                  <h3>{entry.title}</h3>
                </div>
                <div className="updated-stamp">
                  <span>Updated</span>
                  <strong>{formatDateTime(entry.updated_at)}</strong>
                </div>
              </div>

              <div className="journal-metrics">
                <div>
                  <span>Planned entry</span>
                  <strong>{formatPrice(entry.planned_entry)}</strong>
                </div>
                <div>
                  <span>Planned exit</span>
                  <strong>{formatPrice(entry.planned_exit)}</strong>
                </div>
                <div>
                  <span>Stop loss</span>
                  <strong>{formatPrice(entry.stop_loss)}</strong>
                </div>
                <div>
                  <span>Position size</span>
                  <strong>{formatPositionSize(entry.position_size_pct)}</strong>
                </div>
              </div>

              <section className="journal-preview">
                <h4>{preview.label}</h4>
                <p>{preview.text}</p>
              </section>
            </article>
          );
        })}
      </div>
    </section>
  );
}
