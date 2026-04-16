from fastapi import APIRouter

from backend.app.api.routes import health, journal, portfolio, recommendations, system, watchlists


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(watchlists.router, prefix="/watchlist", tags=["watchlist"])
api_router.include_router(
    recommendations.router,
    prefix="/recommendations",
    tags=["recommendations"],
)
api_router.include_router(journal.router, prefix="/journal", tags=["journal"])
api_router.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
