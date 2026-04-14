import { FormEvent, useEffect, useState } from "react";
import { createJournalEntry, listJournalEntries } from "../api/client";
import type { BucketType, JournalEntry } from "../api/types";
import { EmptyState } from "../components/EmptyState";

function optionalNumber(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
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
      await createJournalEntry({
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
      setTitle("");
      setSymbol("");
      setBucket("");
      setContent("");
      setPlannedEntry("");
      setPlannedExit("");
      setStopLoss("");
      setPositionSizePct("");
      setOutcomeNote("");
      await load();
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
          <h2>Trade plan notes</h2>
        </div>
      </div>

      <form className="journal-form" onSubmit={handleSubmit}>
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
            <option value="">none</option>
            <option value="core">core</option>
            <option value="swing">swing</option>
            <option value="event">event</option>
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

      {message ? <p className="notice">{message}</p> : null}
      {loading ? <p className="muted">Loading journal...</p> : null}

      {!loading && entries.length === 0 ? (
        <EmptyState title="No journal entries" detail="Save a plan to start tracking manual trade decisions." />
      ) : null}

      <div className="journal-list">
        {entries.map((entry) => (
          <article key={entry.id} className="journal-entry">
            <div className="card-heading">
              <div>
                <p className="eyebrow">
                  {[entry.symbol, entry.bucket].filter(Boolean).join(" / ") || "general"}
                </p>
                <h3>{entry.title}</h3>
              </div>
              <span>{new Date(entry.created_at).toLocaleDateString()}</span>
            </div>
            <p>{entry.content}</p>
            <div className="field-grid">
              <div>
                <span>Planned entry</span>
                <strong>{entry.planned_entry ?? "n/a"}</strong>
              </div>
              <div>
                <span>Planned exit</span>
                <strong>{entry.planned_exit ?? "n/a"}</strong>
              </div>
              <div>
                <span>Stop loss</span>
                <strong>{entry.stop_loss ?? "n/a"}</strong>
              </div>
              <div>
                <span>Position %</span>
                <strong>{entry.position_size_pct ?? "n/a"}</strong>
              </div>
            </div>
            <section>
              <h4>Outcome note</h4>
              <p>{entry.outcome_note ?? "No outcome yet."}</p>
            </section>
          </article>
        ))}
      </div>
    </section>
  );
}
