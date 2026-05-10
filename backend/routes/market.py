from fastapi import APIRouter, HTTPException

from data.coindcx import get_all_tickers
from data.sentiment import get_combined_sentiment

router = APIRouter()


@router.get("/prices")
async def get_market_prices():
    try:
        return {"prices": await get_all_tickers()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sentiment")
async def get_market_sentiment():
    try:
        return await get_combined_sentiment()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
