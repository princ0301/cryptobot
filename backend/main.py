import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.scheduler import is_running, run_now, start_scheduler, stop_scheduler
from config import settings
from data.coin_registry import load_trading_pairs, load_watched_pairs
from models.database import init_db
from routes import agent, coins, live, market, performance, portfolio, trades

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Crypto Agent starting")
    logger.info("Environment: %s", settings.app_env)
    logger.info("Paper balance: INR %.0f", settings.paper_starting_balance)
    logger.info("Trade interval: every %s minutes", settings.trade_interval_minutes)
    logger.info("AI model: %s", settings.groq_model)
    logger.info("Watched pairs: %s", load_watched_pairs())
    logger.info("Tradable pairs: %s", load_trading_pairs())

    db_ready = init_db()
    if db_ready:
        logger.info("Supabase connection ready")
    else:
        logger.warning("Supabase tables are not ready. Run the SQL schema first.")

    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()
        logger.info("Crypto Agent stopped")


app = FastAPI(
    title="Crypto Trading Agent",
    description="",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent.router, prefix="/agent", tags=["Agent"])
app.include_router(trades.router, prefix="/trades", tags=["Trades"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["Portfolio"])
app.include_router(performance.router, prefix="/performance", tags=["Performance"])
app.include_router(live.router, prefix="/live", tags=["Live Mode"])
app.include_router(market.router, prefix="/market", tags=["Market Data"])
app.include_router(coins.router, prefix="/coins", tags=["Coins"])


@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "agent_running": is_running(),
        "mode": "paper",
        "environment": settings.app_env,
        "paper_balance": settings.paper_starting_balance,
        "trade_interval": settings.trade_interval_minutes,
        "ai_model": settings.groq_model,
        "coins": load_watched_pairs(),
        "tradable_coins": load_trading_pairs(),
    }


@app.post("/agent/run-now", tags=["Agent"])
async def trigger_cycle():
    asyncio.create_task(run_now())
    return {"message": "Agent cycle triggered. Check logs for progress."}


@app.get("/", tags=["System"])
async def root():
    return {
        "message": "Crypto Agent API is running",
        "docs": "/docs",
        "health": "/health",
        "trigger": "POST /agent/run-now",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.backend_port,
        reload=False,
        log_level="info",
    )
