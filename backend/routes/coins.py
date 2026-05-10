import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from data.coin_registry import load_coin_pairs, save_coin_pairs
from data.coindcx import get_inr_market_details
from models.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class AddCoinRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=20)


def _normalize_coin_input(value: str) -> str:
    symbol = value.upper().strip()
    if not symbol.endswith("INR"):
        symbol = f"{symbol}INR"
    return symbol


@router.get("")
async def get_coins():
    pairs = load_coin_pairs()
    return {"pairs": pairs, "count": len(pairs)}


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

    pairs.append(market)
    save_coin_pairs(pairs)

    logger.info("Added coin to trading universe: %s", symbol)
    return {
        "message": f"{symbol} added to the trading universe.",
        "coin": market,
        "count": len(pairs),
    }


@router.delete("/{symbol}")
async def remove_coin(symbol: str):
    normalized = symbol.upper().strip()
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
