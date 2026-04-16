import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createPortfolioPosition,
  importPortfolioPositionsCsv,
  listPortfolioPositions,
  previewPortfolioPositionsCsv
} from "../api/client";
import type { PortfolioPosition, PositionCsvPreviewResult } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { labelPositionAction, labelPositionSource } from "../utils/labels";

const sampleCsv = "symbol,shares,average_cost,current_price,portfolio_weight,thesis,notes\nAMD,10,120,135,0.08,Swing AI exposure,Watch volume\nMSFT,5,330,410,0.12,Core compounder,Long-term hold";
const importFields = [
  "symbol",
  "shares",
  "average_cost",
  "current_price",
  "portfolio_weight",
  "thesis",
  "notes"
];

const importFieldLabels: Record<string, string> = {
  symbol: "Symbol",
  shares: "Shares",
  average_cost: "Average cost",
  current_price: "Current price",
  portfolio_weight: "Portfolio weight",
  thesis: "Thesis",
  notes: "Notes"
};

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
  const [csvText, setCsvText] = useState("");
  const [csvFileName, setCsvFileName] = useState<string | null>(null);
  const [showPasteFallback, setShowPasteFallback] = useState(false);
  const [csvPreview, setCsvPreview] = useState<PositionCsvPreviewResult | null>(null);
  const [columnMapping, setColumnMapping] = useState<Record<string, string | null>>({});
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
    const actionCounts = positions.reduce<Record<string, number>>((counts, position) => {
      counts[position.recommended_action] = (counts[position.recommended_action] ?? 0) + 1;
      return counts;
    }, {});
    return { actionCounts, marketValue, unrealizedPnl };
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
    if (!csvPreview) {
      setMessage("Preview a CSV before importing.");
      return;
    }
    if (csvPreview.error_count > 0) {
      setMessage("Resolve CSV mapping or validation errors before importing.");
      return;
    }
    setMessage("Importing CSV positions...");
    try {
      const result = await importPortfolioPositionsCsv({
        csv_text: csvText,
        source_type: "csv_import",
        column_mapping: columnMapping
      });
      await load();
      setMessage(`Imported ${result.imported_count} positions. Skipped ${result.skipped_count}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to import CSV.");
    }
  }

  async function previewCsv(text: string, mapping?: Record<string, string | null>) {
    if (text.trim().length === 0) {
      setMessage("Choose a CSV file or paste CSV text before previewing.");
      return;
    }
    setMessage("Previewing CSV...");
    try {
      const preview = await previewPortfolioPositionsCsv({ csv_text: text, column_mapping: mapping });
      setCsvPreview(preview);
      setColumnMapping(mapping ?? preview.suggested_mapping);
      setMessage(
        preview.error_count > 0
          ? "Review mapping and validation errors before importing."
          : `Preview ready: ${preview.valid_count} valid rows.`
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to preview CSV.");
    }
  }

  async function handleFileUpload(file: File | null) {
    if (!file) return;
    const text = await file.text();
    setCsvText(text);
    setCsvFileName(file.name);
    setCsvPreview(null);
    setColumnMapping({});
    await previewCsv(text);
  }

  async function updateMapping(field: string, value: string) {
    const nextMapping = { ...columnMapping, [field]: value === "" ? null : value };
    setColumnMapping(nextMapping);
    await previewCsv(csvText, nextMapping);
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

      <div className="action-summary">
        {(["hold", "add", "trim", "exit", "review"] as const).map((action) => (
          <div key={action}>
            <span>{labelPositionAction(action)}</span>
            <strong>{totals.actionCounts[action] ?? 0}</strong>
          </div>
        ))}
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
              <p className="eyebrow">CSV import</p>
              <h3>Import positions</h3>
            </div>
            <span>No orders or execution</span>
          </div>
          <label className="full-span upload-panel">
            CSV file
            <input accept=".csv,text/csv" type="file" onChange={(event) => void handleFileUpload(event.target.files?.[0] ?? null)} />
            <span>{csvFileName ? `Selected: ${csvFileName}` : "Upload a broker export or spreadsheet CSV."}</span>
          </label>

          {csvPreview ? (
            <div className="full-span import-preview">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Column mapping</p>
                  <h3>Review before import</h3>
                </div>
                <span>{csvPreview.valid_count} valid rows</span>
              </div>
              <div className="mapping-grid">
                {importFields.map((field) => (
                  <label key={field}>
                    {importFieldLabels[field]}
                    <select value={columnMapping[field] ?? ""} onChange={(event) => void updateMapping(field, event.target.value)}>
                      <option value="">Do not import</option>
                      {csvPreview.headers.map((header) => (
                        <option key={header} value={header}>
                          {header}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              {csvPreview.errors.length > 0 ? (
                <div className="import-errors">
                  {csvPreview.errors.map((error) => (
                    <p key={error}>{error}</p>
                  ))}
                </div>
              ) : null}
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Symbol</th>
                      <th>Shares</th>
                      <th>Avg cost</th>
                      <th>Current price</th>
                      <th>Weight</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {csvPreview.rows.map((row) => (
                      <tr key={row.row_number}>
                        <td>{row.row_number}</td>
                        <td>{row.values.symbol ?? "n/a"}</td>
                        <td>{row.values.shares ?? "n/a"}</td>
                        <td>{row.values.average_cost ?? "n/a"}</td>
                        <td>{row.values.current_price ?? "n/a"}</td>
                        <td>{row.values.portfolio_weight ?? "n/a"}</td>
                        <td>{row.errors.length > 0 ? row.errors.join(" ") : "Ready"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button type="button" disabled={csvPreview.error_count > 0} onClick={handleCsvImport}>
                Import previewed positions
              </button>
            </div>
          ) : null}

          <button className="text-button" type="button" onClick={() => setShowPasteFallback((value) => !value)}>
            {showPasteFallback ? "Hide paste fallback" : "Paste CSV instead"}
          </button>
          {showPasteFallback ? (
            <>
              <label className="full-span">
                CSV text fallback
                <textarea rows={8} value={csvText || sampleCsv} onChange={(event) => setCsvText(event.target.value)} />
              </label>
              <button
                type="button"
                onClick={() => {
                  const text = csvText || sampleCsv;
                  setCsvText(text);
                  void previewCsv(text);
                }}
              >
                Preview pasted CSV
              </button>
            </>
          ) : null}
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
              <div>
                <span>P/L from cost</span>
                <strong>{position.pnl_pct === null ? "n/a" : `${position.pnl_pct.toFixed(1)}%`}</strong>
              </div>
              <div>
                <span>Trend</span>
                <strong>{position.market_snapshot?.trend_positive ? "Constructive" : "Review"}</strong>
              </div>
              <div>
                <span>Holding type</span>
                <strong>{position.market_snapshot?.holding_type === "fund_or_index" ? "ETF / Index" : "Stock"}</strong>
              </div>
              <div>
                <span>RSI</span>
                <strong>{position.market_snapshot ? position.market_snapshot.rsi_14.toFixed(1) : "n/a"}</strong>
              </div>
              <div>
                <span>Volume</span>
                <strong>
                  {position.market_snapshot?.volume_ratio === null || position.market_snapshot?.volume_ratio === undefined
                    ? "n/a"
                    : `${position.market_snapshot.volume_ratio.toFixed(2)}x`}
                </strong>
              </div>
            </div>
            <section className="decision-summary">
              <div>
                <span>Assessment</span>
                <p>{position.assessment_summary || "Review manually before changing this holding."}</p>
              </div>
              <div className="top-risk">
                <span>Rationale</span>
                <p>{position.assessment_rationale || "Position analysis is incomplete."}</p>
              </div>
            </section>
            {position.thesis || position.notes ? (
              <section className="decision-summary">
                <div>
                  <span>Thesis</span>
                  <p>{position.thesis || "No thesis saved yet."}</p>
                </div>
                <div className="top-risk">
                  <span>Notes</span>
                  <p>{position.notes || "No notes saved yet."}</p>
                </div>
              </section>
            ) : null}
            <p className="source-note">
              {position.source_type === "broker_readonly"
                ? "Broker read-only position. No execution is enabled."
                : position.read_only_note}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
