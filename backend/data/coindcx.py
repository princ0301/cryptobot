import hashlib
import hmac
import json
import logging
import time
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd

from config import settings

logger = logging.getLogger(__name__)

COINDCX_BASE = "https://api.coindcx.com"
PUBLIC_BASE = "https://public.coindcx.com"

COINS_FILE = Path(__file__).resolve().parent / "coins.json"


def _load_pair_map() -> dict[str, dict[str, str]]:
    try:
        payload = json.loads(COINS_FILE.read_text(encoding="utf-8"))
        pairs = payload.get("pairs", [])
        return {
            pair["symbol"]: {
                "candle_pair": pair["candle_pair"],
                "display": pair["display"],
            }
            for pair in pairs
            if pair.get("symbol") and pair.get("candle_pair") and pair.get("display")
        }
    except Exception as exc:
        logger.warning("Failed to load coins.json, using built-in defaults: %s", exc)
        return {
            "BTCINR": {"candle_pair": "I-BTC_INR", "display": "BTC/INR"},
            "ETHINR": {"candle_pair": "I-ETH_INR", "display": "ETH/INR"},
            "BNBINR": {"candle_pair": "I-BNB_INR", "display": "BNB/INR"},
        }


PAIR_MAP = _load_pair_map()


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


async def get_all_tickers() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{COINDCX_BASE}/exchange/ticker")
        response.raise_for_status()
        tickers = response.json()

    result = {}
    for ticker in tickers:
        market = ticker.get("market", "")
        if market in PAIR_MAP:
            result[market] = {
                "market": market,
                "display": PAIR_MAP[market]["display"],
                "price": float(ticker.get("last_price", 0)),
                "change_24h": float(ticker.get("change_24_hour", 0)),
                "high_24h": float(ticker.get("high", 0)),
                "low_24h": float(ticker.get("low", 0)),
                "volume": float(ticker.get("volume", 0)),
                "bid": float(ticker.get("bid", 0)),
                "ask": float(ticker.get("ask", 0)),
                "timestamp": ticker.get("timestamp"),
            }
    return result


async def get_ticker(pair: str) -> Optional[dict]:
    tickers = await get_all_tickers()
    return tickers.get(pair)


async def get_ohlcv(pair: str, interval: str = "1h", limit: int = 200) -> pd.DataFrame:
    if pair not in PAIR_MAP:
        raise ValueError(f"Unknown pair: {pair}. Valid pairs: {list(PAIR_MAP)}")

    url = f"{PUBLIC_BASE}/market_data/candles"
    params = {
        "pair": PAIR_MAP[pair]["candle_pair"],
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

        logger.info("Fetched %s candles for %s (%s)", len(df), pair, interval)
        return df
    except Exception as exc:
        logger.error("Error fetching OHLCV for %s: %s", pair, exc)
        return pd.DataFrame()


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
