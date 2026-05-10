import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data.coindcx import get_all_tickers
from data.sentiment import get_fear_greed
from models.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


def _db():
    return get_db()


class LiveActivationRequest(BaseModel):
    api_key: str
    api_secret: str
    confirmation: str


@router.get("/status")
async def get_live_status():
    try:
        result = (
            _db()
            .table("performance_metrics")
            .select("live_mode_unlocked, all_criteria_met")
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        metrics = result.data[0] if result.data else {}
        unlocked = metrics.get("live_mode_unlocked", False)
        return {
            "unlocked": unlocked,
            "all_criteria_met": metrics.get("all_criteria_met", False),
            "message": (
                "Live mode unlocked. Agent proved itself."
                if unlocked
                else "Agent is still in paper mode. Keep training."
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/activate")
async def activate_live_mode(request: LiveActivationRequest):
    result = _db().table("performance_metrics").select("all_criteria_met").order("id", desc=True).limit(1).execute()
    metrics = result.data[0] if result.data else {}

    if not metrics.get("all_criteria_met"):
        raise HTTPException(
            status_code=403,
            detail="Live mode locked. Agent has not met all promotion criteria yet.",
        )

    if request.confirmation != "I CONFIRM REAL MONEY TRADING":
        raise HTTPException(status_code=400, detail="Invalid confirmation string.")

    logger.warning("Live mode activation requested")
    return {
        "status": "activated",
        "mode": "live",
        "warning": "Real INR trades will now be placed on CoinDCX.",
        "message": "Live mode activated. Agent will trade with real money on the next cycle.",
    }


@router.get("/prices")
async def get_live_prices():
    try:
        tickers = await get_all_tickers()
        return {"prices": {ticker["display"]: ticker for ticker in tickers.values()}}
    except Exception as exc:
        logger.error("Error fetching prices: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sentiment")
async def get_market_sentiment():
    try:
        fear_greed = await get_fear_greed()
        return {
            "score": fear_greed["score"],
            "label": fear_greed["label"],
            "signal": fear_greed["trade_hint"],
            "source": fear_greed["source"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
