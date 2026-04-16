import type {
  BucketType,
  BrokerReadonlySyncRequest,
  JournalEntry,
  JournalEntryCreate,
  MarketSnapshot,
  PortfolioPosition,
  PortfolioPositionCreate,
  PositionCsvImportRequest,
  PositionCsvImportResult,
  PositionCsvPreviewRequest,
  PositionCsvPreviewResult,
  Recommendation,
  RecommendationDecisionRequest,
  RecommendationDecisionStatus,
  WatchlistItem,
  WatchlistItemCreate
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

type QueryValue = string | number | boolean | null | undefined;

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url.toString();
}

async function request<T>(path: string, init?: RequestInit, query?: Record<string, QueryValue>): Promise<T> {
  const response = await fetch(buildUrl(path, query), {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    },
    ...init
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function listWatchlistItems(filters?: { bucket?: BucketType }): Promise<WatchlistItem[]> {
  return request<WatchlistItem[]>("/watchlist", undefined, filters);
}

export function createWatchlistItem(payload: WatchlistItemCreate): Promise<WatchlistItem> {
  return request<WatchlistItem>("/watchlist", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function listRecommendations(filters?: {
  bucket?: BucketType;
  decision_status?: RecommendationDecisionStatus;
}): Promise<Recommendation[]> {
  return request<Recommendation[]>("/recommendations", undefined, filters);
}

export function generateSwingRecommendations(): Promise<Recommendation[]> {
  return request<Recommendation[]>("/recommendations/generate/swing", {
    method: "POST"
  });
}

export function decideRecommendation(
  recommendationId: number,
  payload: RecommendationDecisionRequest
): Promise<Recommendation> {
  return request<Recommendation>(`/recommendations/${recommendationId}/decision`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function listJournalEntries(): Promise<JournalEntry[]> {
  return request<JournalEntry[]>("/journal");
}

export function createJournalEntry(payload: JournalEntryCreate): Promise<JournalEntry> {
  return request<JournalEntry>("/journal", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function listMarketSnapshots(): Promise<MarketSnapshot[]> {
  return request<MarketSnapshot[]>("/system/market-snapshots");
}

export function seedDemoData(): Promise<unknown> {
  return request<unknown>("/system/seed", {
    method: "POST"
  });
}

export function refreshMarketSnapshots(): Promise<MarketSnapshot[]> {
  return request<MarketSnapshot[]>("/system/market-snapshots/refresh", {
    method: "POST"
  });
}

export function listPortfolioPositions(): Promise<PortfolioPosition[]> {
  return request<PortfolioPosition[]>("/portfolio/positions");
}

export function createPortfolioPosition(payload: PortfolioPositionCreate): Promise<PortfolioPosition> {
  return request<PortfolioPosition>("/portfolio/positions", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function importPortfolioPositionsCsv(payload: PositionCsvImportRequest): Promise<PositionCsvImportResult> {
  return request<PositionCsvImportResult>("/portfolio/positions/import-csv", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function previewPortfolioPositionsCsv(payload: PositionCsvPreviewRequest): Promise<PositionCsvPreviewResult> {
  return request<PositionCsvPreviewResult>("/portfolio/positions/import-csv/preview", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function syncBrokerReadonlyPositions(payload: BrokerReadonlySyncRequest): Promise<PortfolioPosition[]> {
  return request<PortfolioPosition[]>("/portfolio/positions/broker-readonly/sync", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
