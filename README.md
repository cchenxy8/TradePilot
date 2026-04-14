# TradePilot

A trading research assistant that organizes watchlists, summarizes market signals, surfaces swing/core/event ideas, and supports manual approval workflows with audit logs before any execution.

## MVP Scope

Minimal backend-first scaffold for a single-user trading research assistant.

## Stack

- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic

## MVP Backend Capabilities

- Watchlist management
- Recommendation queue
- Approve / reject / defer workflow
- Trade journal and audit log
- Real market data snapshots for watchlist symbols
- Bucket types: `core`, `swing`, `event`

## Quick Start

1. Create a virtual environment and install dependencies.
2. Set `DATABASE_URL` in a local `.env` file.
3. Run the API:

```bash
uvicorn backend.app.main:app --reload
```

## Suggested PostgreSQL URL

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/tradepilot
```

## Market Data

TradePilot defaults to Yahoo Finance public quote/chart endpoints for lightweight research snapshots.

Optional `.env` settings:

```bash
MARKET_DATA_PROVIDER=yahoo
MARKET_DATA_BASE_URL=https://query1.finance.yahoo.com
MARKET_DATA_TIMEOUT_SECONDS=8
```
