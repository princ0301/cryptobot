import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from data.coin_registry import load_coin_pairs, save_coin_pairs
from data.coindcx import get_inr_market_details, get_ohlcv, get_ticker, search_inr_markets
from models.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

MIN_NOTIONAL_VOLUME_INR = 100000.0
MAX_SPREAD_PCT = 2.0
MIN_CANDLE_HISTORY = 100


class AddCoinRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=20)


class UpdateCoinRequest(BaseModel):
    watched: Optional[bool] = None
    tradable: Optional[bool] = None


def _normalize_coin_input(value: str) -> str:
    symbol = value.upper().strip()
    if not symbol.endswith("INR"):
        symbol = f"{symbol}INR"
    return symbol


async def _validate_tradable(symbol: str) -> dict:
    reasons = []
    ticker = await get_ticker(symbol)
    if not ticker:
        return {
            "eligible": False,
            "reasons": ["Live ticker is unavailable for this market."],
            "checks": {},
        }

    price = float(ticker.get("price", 0) or 0)
    volume = float(ticker.get("volume", 0) or 0)
    bid = float(ticker.get("bid", 0) or 0)
    ask = float(ticker.get("ask", 0) or 0)

    notional_volume_inr = price * volume
    spread_pct = ((ask - bid) / ask * 100) if ask > 0 and bid > 0 and ask >= bid else 0

    if notional_volume_inr < MIN_NOTIONAL_VOLUME_INR:
        reasons.append(
            f"24h notional volume is too low (INR {notional_volume_inr:,.0f}; need at least INR {MIN_NOTIONAL_VOLUME_INR:,.0f})."
        )

    if ask <= 0 or bid <= 0:
        reasons.append("Bid/ask data is incomplete for this market.")
    elif spread_pct > MAX_SPREAD_PCT:
        reasons.append(
            f"Spread is too wide ({spread_pct:.2f}%; max allowed is {MAX_SPREAD_PCT:.2f}%)."
        )

    candles = await get_ohlcv(symbol, interval="1h", limit=MIN_CANDLE_HISTORY + 20)
    candle_count = len(candles.index) if candles is not None else 0
    if candle_count < MIN_CANDLE_HISTORY:
        reasons.append(
            f"Not enough candle history ({candle_count} candles; need at least {MIN_CANDLE_HISTORY})."
        )

    return {
        "eligible": len(reasons) == 0,
        "reasons": reasons,
        "checks": {
            "notional_volume_inr": round(notional_volume_inr, 2),
            "spread_pct": round(spread_pct, 4),
            "candle_count": candle_count,
            "min_notional_volume_inr": MIN_NOTIONAL_VOLUME_INR,
            "max_spread_pct": MAX_SPREAD_PCT,
            "min_candle_history": MIN_CANDLE_HISTORY,
        },
    }


@router.get("")
async def get_coins():
    pairs = load_coin_pairs()
    return {
        "pairs": pairs,
        "count": len(pairs),
        "watched_count": sum(1 for pair in pairs if pair.get("watched")),
        "tradable_count": sum(1 for pair in pairs if pair.get("tradable")),
    }


@router.get("/search")
async def search_coins(q: str = Query(min_length=1), limit: int = Query(default=8, ge=1, le=20)):
    suggestions = await search_inr_markets(q, limit=limit)
    return {"query": q, "suggestions": suggestions, "count": len(suggestions)}


@router.post("")
async def add_coin(request: AddCoinRequest):
    symbol = _normalize_coin_input(request.symbol)
    pairs = load_coin_pairs()

    if any(pair["symbol"] == symbol for pair in pairs):
        raise HTTPException(status_code=409, detail=f"{symbol} is already in the trading universe.")

    market = await get_inr_market_details(symbol)
    if not market or not market.get("candle_pair"):
        raise HTTPException(
            status_code=400,
            detail=f"{symbol} is not an active INR market on CoinDCX.",
        )

    market["watched"] = True
    market["tradable"] = False
    pairs.append(market)
    save_coin_pairs(pairs)

    logger.info("Added coin to trading universe: %s", symbol)
    return {
        "message": f"{symbol} added to the watchlist. Enable tradable after validation if you want the agent to trade it.",
        "coin": market,
        "count": len(pairs),
    }


@router.patch("/{symbol}")
async def update_coin(symbol: str, request: UpdateCoinRequest):
    normalized = _normalize_coin_input(symbol)
    pairs = load_coin_pairs()
    current = next((pair for pair in pairs if pair["symbol"] == normalized), None)

    if not current:
        raise HTTPException(status_code=404, detail=f"{normalized} is not in the trading universe.")

    watched = current.get("watched", True) if request.watched is None else request.watched
    tradable = current.get("tradable", False) if request.tradable is None else request.tradable

    if not watched:
        tradable = False

    validation = None
    if tradable:
        validation = await _validate_tradable(normalized)
        if not validation["eligible"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"{normalized} cannot be marked tradable yet.",
                    "reasons": validation["reasons"],
                    "checks": validation["checks"],
                },
            )

    updated = []
    for pair in pairs:
        if pair["symbol"] == normalized:
            updated.append(
                {
                    **pair,
                    "watched": watched,
                    "tradable": tradable,
                }
            )
        else:
            updated.append(pair)

    save_coin_pairs(updated)
    logger.info("Updated coin state: %s watched=%s tradable=%s", normalized, watched, tradable)
    return {
        "message": f"{normalized} updated.",
        "coin": next(pair for pair in updated if pair["symbol"] == normalized),
        "validation": validation,
    }


@router.delete("/{symbol}")
async def remove_coin(symbol: str):
    normalized = _normalize_coin_input(symbol)
    pairs = load_coin_pairs()
    remaining = [pair for pair in pairs if pair["symbol"] != normalized]

    if len(remaining) == len(pairs):
        raise HTTPException(status_code=404, detail=f"{normalized} is not in the trading universe.")

    open_result = (
        get_db()
        .table("open_positions")
        .select("id")
        .eq("coin", normalized)
        .limit(1)
        .execute()
    )
    if open_result.data:
        raise HTTPException(
            status_code=400,
            detail=f"{normalized} has an open position and cannot be removed yet.",
        )

    if not remaining:
        raise HTTPException(status_code=400, detail="At least one trading pair must remain configured.")

    save_coin_pairs(remaining)
    logger.info("Removed coin from trading universe: %s", normalized)
    return {
        "message": f"{normalized} removed from the trading universe.",
        "count": len(remaining),
    }
