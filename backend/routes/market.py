from fastapi import APIRouter, HTTPException
import httpx
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

COINDCX_BASE = "https://api.coindcx.com"

# Real CoinDCX market names confirmed from API
PAIRS = {
    "BTCINR": "BTC/INR",
    "ETHINR": "ETH/INR",
    "BNBINR": "BNB/INR",
}


@router.get("/prices")
async def get_live_prices():
    """Get live prices for BTC/INR, ETH/INR, BNB/INR from CoinDCX."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{COINDCX_BASE}/exchange/ticker")
            response.raise_for_status()
            tickers = response.json()

        prices = {}
        for ticker in tickers:
            market = ticker.get("market", "")
            if market in PAIRS:
                display = PAIRS[market]
                prices[display] = {
                    "market":     market,
                    "price":      float(ticker.get("last_price", 0)),
                    "change_24h": float(ticker.get("change_24_hour", 0)),
                    "high_24h":   float(ticker.get("high", 0)),
                    "low_24h":    float(ticker.get("low", 0)),
                    "volume":     float(ticker.get("volume", 0)),
                    "bid":        float(ticker.get("bid", 0)),
                    "ask":        float(ticker.get("ask", 0)),
                }

        return {"prices": prices}
    except Exception as e:
        logger.error(f"Error fetching prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment")
async def get_market_sentiment():
    """Get Fear & Greed index."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://api.alternative.me/fng/?limit=1")
            response.raise_for_status()
            data = response.json()

        fng   = data["data"][0]
        score = int(fng["value"])
        label = fng["value_classification"]

        if score <= 25:
            signal_text = "Extreme fear — contrarian BUY opportunity, market likely oversold"
        elif score <= 45:
            signal_text = "Fear in the market — wait for technical confirmation before entering"
        elif score <= 55:
            signal_text = "Neutral sentiment — follow technicals only, no strong bias"
        elif score <= 75:
            signal_text = "Greed building — good for trend riding, watch for reversal signs"
        else:
            signal_text = "Extreme greed — caution advised, reduce position size"

        return {
            "score":       score,
            "label":       label,
            "signal_text": signal_text,
            "timestamp":   fng.get("timestamp"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))