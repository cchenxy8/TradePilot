import { FormEvent, useEffect, useMemo, useState } from "react";
import { createPortfolioPosition, importPortfolioPositionsCsv, listPortfolioPositions } from "../api/client";
import type { PortfolioPosition } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { labelPositionAction, labelPositionSource } from "../utils/labels";

const sampleCsv = "symbol,shares,average_cost,current_price,portfolio_weight,thesis,notes\nAMD,10,120,135,0.08,Swing AI exposure,Watch volume\nMSFT,5,330,410,0.12,Core compounder,Long-term hold";

function formatCurrency(value: number | null): string {
  if (value === null) return "n/a";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function formatNumber(value: number | null, digits = 2): string {
  if (value === null) return "n/a";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function formatPercent(value: number | null): string {
  if (value === null) return "n/a";
  return `${(value * 100).toFixed(1)}%`;
}

export function Portfolio() {
  const [positions, setPositions] = useState<PortfolioPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [csvText, setCsvText] = useState(sampleCsv);
  const [manual, setManual] = useState({
    symbol: "",
    shares: "",
    average_cost: "",
    current_price: "",
    thesis: "",
    notes: ""
  });

  async function load() {
    setLoading(true);
    setMessage(null);
    try {
      setPositions(await listPortfolioPositions());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load positions.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const totals = useMemo(() => {
    const marketValue = positions.reduce((sum, position) => {
      if (position.current_price === null) return sum;
      return sum + position.current_price * position.shares;
    }, 0);
    const unrealizedPnl = positions.reduce((sum, position) => sum + (position.unrealized_pnl ?? 0), 0);
    return { marketValue, unrealizedPnl };
  }, [positions]);

  async function handleManualSubmit(event: FormEvent) {
    event.preventDefault();
    setMessage("Saving position...");
    try {
      await createPortfolioPosition({
        source_type: "manual_entry",
        symbol: manual.symbol,
        shares: Number(manual.shares),
        average_cost: manual.average_cost ? Number(manual.average_cost) : null,
        current_price: manual.current_price ? Number(manual.current_price) : null,
        thesis: manual.thesis || null,
        notes: manual.notes || null,
        recommended_action: "review"
      });
      setManual({ symbol: "", shares: "", average_cost: "", current_price: "", thesis: "", notes: "" });
      await load();
      setMessage("Position saved for manual review.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save position.");
    }
  }

  async function handleCsvImport() {
    setMessage("Importing CSV positions...");
    try {
      const result = await importPortfolioPositionsCsv({ csv_text: csvText, source_type: "csv_import" });
      await load();
      setMessage(`Imported ${result.imported_count} positions. Skipped ${result.skipped_count}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to import CSV.");
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Portfolio</p>
          <h2>Positions and holdings review</h2>
        </div>
      </div>

      {message ? <p className="notice">{message}</p> : null}

      <div className="decision-dashboard">
        <div>
          <span>Positions</span>
          <strong>{positions.length}</strong>
        </div>
        <div>
          <span>Known market value</span>
          <strong>{formatCurrency(totals.marketValue)}</strong>
        </div>
        <div>
          <span>Known unrealized P/L</span>
          <strong>{formatCurrency(totals.unrealizedPnl)}</strong>
        </div>
      </div>

      <section className="portfolio-layout">
        <form className="portfolio-form" onSubmit={handleManualSubmit}>
          <div className="form-heading">
            <div>
              <p className="eyebrow">Manual entry</p>
              <h3>Add a held position</h3>
            </div>
            <span>Human review only</span>
          </div>
          <label>
            Symbol
            <input value={manual.symbol} onChange={(event) => setManual({ ...manual, symbol: event.target.value })} required />
          </label>
          <label>
            Shares
            <input
              min="0"
              step="0.000001"
              type="number"
              value={manual.shares}
              onChange={(event) => setManual({ ...manual, shares: event.target.value })}
              required
            />
          </label>
          <label>
            Average cost
            <input
              min="0"
              step="0.01"
              type="number"
              value={manual.average_cost}
              onChange={(event) => setManual({ ...manual, average_cost: event.target.value })}
            />
          </label>
          <label>
            Current price
            <input
              min="0"
              step="0.01"
              type="number"
              value={manual.current_price}
              onChange={(event) => setManual({ ...manual, current_price: event.target.value })}
            />
          </label>
          <label className="full-span">
            Thesis
            <textarea value={manual.thesis} onChange={(event) => setManual({ ...manual, thesis: event.target.value })} />
          </label>
          <label className="full-span">
            Notes
            <textarea value={manual.notes} onChange={(event) => setManual({ ...manual, notes: event.target.value })} />
          </label>
          <button type="submit">Save position</button>
        </form>

        <section className="portfolio-form">
          <div className="form-heading">
            <div>
              <p className="eyebrow">CSV fallback</p>
              <h3>Import positions</h3>
            </div>
            <span>No orders or execution</span>
          </div>
          <label className="full-span">
            CSV text
            <textarea rows={8} value={csvText} onChange={(event) => setCsvText(event.target.value)} />
          </label>
          <button type="button" onClick={handleCsvImport}>
            Import CSV
          </button>
          <p className="source-note">
            Future broker connections should use broker read-only account APIs and sync holdings into this same position
            model. TradePilot will not place orders.
          </p>
        </section>
      </section>

      {loading ? <LoadingState label="Loading portfolio positions..." /> : null}
      {!loading && positions.length === 0 ? (
        <EmptyState title="No positions yet" detail="Add a manual position or import CSV holdings to start portfolio review." />
      ) : null}

      <div className="position-grid">
        {positions.map((position) => (
          <article className="position-card" key={position.id}>
            <div className="card-heading">
              <div>
                <p className="meta-line">{labelPositionSource(position.source_type)}</p>
                <h3>{position.symbol}</h3>
              </div>
              <span className={`action-badge ${position.recommended_action}`}>
                {labelPositionAction(position.recommended_action)}
              </span>
            </div>
            <div className="snapshot-grid">
              <div>
                <span>Shares</span>
                <strong>{formatNumber(position.shares, 6)}</strong>
              </div>
              <div>
                <span>Average cost</span>
                <strong>{formatCurrency(position.average_cost)}</strong>
              </div>
              <div>
                <span>Current price</span>
                <strong>{formatCurrency(position.current_price)}</strong>
              </div>
              <div>
                <span>Portfolio weight</span>
                <strong>{formatPercent(position.portfolio_weight)}</strong>
              </div>
            </div>
            <section className="decision-summary">
              <div>
                <span>Thesis</span>
                <p>{position.thesis || "No thesis saved yet."}</p>
              </div>
              <div className="top-risk">
                <span>Notes</span>
                <p>{position.notes || "Manual review required before changing this holding."}</p>
              </div>
            </section>
            <p className="source-note">
              {position.source_type === "broker_readonly"
                ? "Broker read-only position. No execution is enabled."
                : "Read-only portfolio record. Any action remains a manual decision."}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
