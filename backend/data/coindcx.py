import hashlib
import hmac
import json
import logging
import time
import asyncio
from typing import Optional

import httpx
import pandas as pd

from config import settings
from data.coin_registry import load_pair_map

logger = logging.getLogger(__name__)

COINDCX_BASE = "https://api.coindcx.com"
PUBLIC_BASE = "https://public.coindcx.com"
MARKETS_CACHE_TTL_SECONDS = 300
_markets_cache: dict[str, object] = {"fetched_at": 0.0, "markets": []}
TICKER_CACHE_TTL_SECONDS = 180
_ticker_cache: dict[str, object] = {"fetched_at": 0.0, "tickers": {}}


def _auth_headers(body: dict) -> dict:
    body_str = json.dumps(body, separators=(",", ":"))
    signature = hmac.new(
        settings.coindcx_api_secret.encode(),
        body_str.encode(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-AUTH-APIKEY": settings.coindcx_api_key,
        "X-AUTH-SIGNATURE": signature,
    }


def get_cached_tickers(max_age_seconds: int = TICKER_CACHE_TTL_SECONDS) -> dict:
    cached = _ticker_cache.get("tickers", {}) or {}
    fetched_at = float(_ticker_cache.get("fetched_at", 0.0) or 0.0)
    if cached and (time.time() - fetched_at) <= max_age_seconds:
        return dict(cached)
    return {}


async def get_all_tickers() -> dict:
    pair_map = load_pair_map()
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{COINDCX_BASE}/exchange/ticker")
                response.raise_for_status()
                tickers = response.json()
            break
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                await asyncio.sleep(0.75 * (attempt + 1))
            else:
                stale = get_cached_tickers()
                if stale:
                    logger.warning("CoinDCX ticker fetch failed, using cached prices: %s", exc)
                    return stale
                raise
    else:
        if last_error:
            raise last_error

    result = {}
    for ticker in tickers:
        market = ticker.get("market", "")
        if market in pair_map:
            result[market] = {
                "market": market,
                "display": pair_map[market]["display"],
                "price": float(ticker.get("last_price", 0)),
                "change_24h": float(ticker.get("change_24_hour", 0)),
                "high_24h": float(ticker.get("high", 0)),
                "low_24h": float(ticker.get("low", 0)),
                "volume": float(ticker.get("volume", 0)),
                "bid": float(ticker.get("bid", 0)),
                "ask": float(ticker.get("ask", 0)),
                "timestamp": ticker.get("timestamp"),
            }

    _ticker_cache["tickers"] = result
    _ticker_cache["fetched_at"] = time.time()
    return result


async def get_ticker(pair: str) -> Optional[dict]:
    tickers = await get_all_tickers()
    return tickers.get(pair)


async def get_ohlcv(pair: str, interval: str = "1h", limit: int = 200) -> pd.DataFrame:
    pair_map = load_pair_map()
    if pair not in pair_map:
        raise ValueError(f"Unknown pair: {pair}. Valid pairs: {list(pair_map)}")

    url = f"{PUBLIC_BASE}/market_data/candles"
    params = {
        "pair": pair_map[pair]["candle_pair"],
        "interval": interval,
        "limit": limit,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            candles = response.json()

        if not candles:
            logger.warning("No candles returned for %s", pair)
            return pd.DataFrame()

        df = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "volume"])
        df = df.astype(
            {
                "time": "int64",
                "open": "float64",
                "high": "float64",
                "low": "float64",
                "close": "float64",
                "volume": "float64",
            }
        )
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df.sort_values("time").reset_index(drop=True)

        logger.debug("Fetched %s candles for %s (%s)", len(df), pair, interval)
        return df
    except Exception as exc:
        logger.error("Error fetching OHLCV for %s: %s", pair, exc)
        return pd.DataFrame()


async def get_inr_market_details(symbol: str) -> Optional[dict]:
    symbol = symbol.upper().strip()
    markets = await get_active_inr_markets()

    for market in markets:
        if market.get("symbol") == symbol:
            asset = market.get("target_currency_short_name", symbol.replace("INR", ""))
            return {
                "symbol": symbol,
                "display": f"{asset}/INR",
                "candle_pair": market.get("pair"),
            }

    return None


async def get_active_inr_markets() -> list[dict]:
    now = time.time()
    cached_markets = _markets_cache.get("markets", [])
    fetched_at = float(_markets_cache.get("fetched_at", 0.0) or 0.0)

    if cached_markets and (now - fetched_at) < MARKETS_CACHE_TTL_SECONDS:
        return list(cached_markets)

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(f"{COINDCX_BASE}/exchange/v1/markets_details")
        response.raise_for_status()
        markets = response.json()

    filtered = [
        market
        for market in markets
        if market.get("ecode") == "I" and market.get("status") == "active"
    ]
    _markets_cache["markets"] = filtered
    _markets_cache["fetched_at"] = now
    return list(filtered)


async def search_inr_markets(query: str, limit: int = 10) -> list[dict[str, str]]:
    normalized = query.upper().strip()
    if not normalized:
        return []

    markets = await get_active_inr_markets()
    suggestions = []
    for market in markets:
        symbol = str(market.get("symbol", "")).upper()
        asset = str(market.get("target_currency_short_name", "")).upper()
        display = f"{asset}/INR" if asset else symbol

        haystacks = [symbol, asset, display.upper()]
        if not any(normalized in value for value in haystacks):
            continue

        rank = 0
        if symbol == normalized or asset == normalized:
            rank = 0
        elif symbol.startswith(normalized) or asset.startswith(normalized):
            rank = 1
        else:
            rank = 2

        suggestions.append(
            {
                "symbol": symbol,
                "display": display,
                "candle_pair": str(market.get("pair", "")),
                "asset": asset,
                "_rank": rank,
            }
        )

    suggestions.sort(key=lambda item: (item["_rank"], item["symbol"]))
    return [
        {
            "symbol": item["symbol"],
            "display": item["display"],
            "asset": item["asset"],
        }
        for item in suggestions[:limit]
    ]


async def get_account_balance() -> dict:
    body = {"timestamp": int(time.time() * 1000)}
    headers = _auth_headers(body)

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{COINDCX_BASE}/exchange/v1/users/balances",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        balances = response.json()

    relevant = {"INR", "BTC", "ETH", "BNB"}
    return {
        balance["currency"]: {
            "balance": float(balance.get("balance", 0)),
            "locked": float(balance.get("locked_balance", 0)),
        }
        for balance in balances
        if balance.get("currency") in relevant
    }


async def place_order(
    pair: str,
    side: str,
    order_type: str,
    price: float,
    quantity: float,
) -> dict:
    body = {
        "side": side,
        "order_type": order_type,
        "market": pair,
        "price_per_unit": str(price),
        "total_quantity": str(quantity),
        "timestamp": int(time.time() * 1000),
    }
    headers = _auth_headers(body)

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{COINDCX_BASE}/exchange/v1/orders/create",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        return response.json()


async def cancel_order(order_id: str) -> dict:
    body = {"id": order_id, "timestamp": int(time.time() * 1000)}
    headers = _auth_headers(body)

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{COINDCX_BASE}/exchange/v1/orders/cancel",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        return response.json()


async def get_order_status(order_id: str) -> dict:
    body = {"id": order_id, "timestamp": int(time.time() * 1000)}
    headers = _auth_headers(body)

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{COINDCX_BASE}/exchange/v1/orders/status",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        return response.json()
