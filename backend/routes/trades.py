from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models.database import get_db

router = APIRouter()


@router.get("/history")
async def get_trade_history(
    coin: Optional[str] = None,
    mode: str = "paper",
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
):
    try:
        query = get_db().table("trades").select("*")

        if coin:
            query = query.eq("coin", coin)
        if mode:
            query = query.eq("mode", mode)
        if status:
            query = query.eq("status", status)

        result = query.order("opened_at", desc=True).limit(limit).execute()
        return {"trades": result.data, "count": len(result.data)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/open")
async def get_open_positions():
    try:
        result = get_db().table("open_positions").select("*").order("opened_at", desc=True).execute()
        return {"positions": result.data, "count": len(result.data)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{trade_id}")
async def get_trade_detail(trade_id: int):
    try:
        result = get_db().table("trades").select("*").eq("id", trade_id).single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Trade not found")
        return result.data
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
