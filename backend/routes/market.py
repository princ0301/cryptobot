import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException

from data.coindcx import get_all_tickers, get_ticker_cache_meta

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/prices")
async def get_live_prices():
    """Get live prices for configured INR markets from CoinDCX."""
    try:
        prices = await get_all_tickers()
        meta = get_ticker_cache_meta()
        return {
            "prices": prices,
            "meta": {
                **meta,
                "served_at": datetime.now(timezone.utc).isoformat(),
            },
        }
    except httpx.TimeoutException as exc:
        logger.warning("Market prices request timed out: %r", exc)
        raise HTTPException(status_code=504, detail="CoinDCX price request timed out") from exc
    except httpx.HTTPError as exc:
        logger.error("Market prices request failed: %r", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="CoinDCX price request failed") from exc
    except Exception as exc:
        logger.error("Unexpected error fetching prices: %r", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error fetching market prices") from exc


@router.get("/sentiment")
async def get_market_sentiment():
    """Get Fear & Greed index."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://api.alternative.me/fng/?limit=1")
            response.raise_for_status()
            data = response.json()

        fng = data["data"][0]
        score = int(fng["value"])
        label = fng["value_classification"]

        if score <= 25:
            signal_text = "Extreme fear - contrarian BUY opportunity, market likely oversold"
        elif score <= 45:
            signal_text = "Fear in the market - wait for technical confirmation before entering"
        elif score <= 55:
            signal_text = "Neutral sentiment - follow technicals only, no strong bias"
        elif score <= 75:
            signal_text = "Greed building - good for trend riding, watch for reversal signs"
        else:
            signal_text = "Extreme greed - caution advised, reduce position size"

        return {
            "score": score,
            "label": label,
            "signal_text": signal_text,
            "timestamp": fng.get("timestamp"),
        }
    except httpx.TimeoutException as exc:
        logger.warning("Market sentiment request timed out: %r", exc)
        raise HTTPException(status_code=504, detail="Fear & Greed request timed out") from exc
    except httpx.HTTPError as exc:
        logger.error("Market sentiment request failed: %r", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Fear & Greed request failed") from exc
    except Exception as exc:
        logger.error("Unexpected error fetching sentiment: %r", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error fetching market sentiment") from exc
