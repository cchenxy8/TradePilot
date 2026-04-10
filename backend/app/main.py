from fastapi import FastAPI

from backend.app.api.router import api_router
from backend.app.db.init_db import create_db_and_tables


app = FastAPI(
    title="TradePilot API",
    version="0.1.0",
    summary="Single-user trading research assistant MVP",
)


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"message": "TradePilot backend is running."}


app.include_router(api_router, prefix="/api")
