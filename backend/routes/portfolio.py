from fastapi import APIRouter, HTTPException

from config import settings
from models.database import get_db

router = APIRouter()


@router.get("/balance")
async def get_portfolio_balance():
    try:
        result = get_db().table("paper_portfolio").select("*").order("id", desc=True).limit(1).execute()
        if not result.data:
            return {
                "inr_balance": settings.paper_starting_balance,
                "total_value": settings.paper_starting_balance,
                "pnl_total": 0,
                "pnl_today": 0,
                "degraded": False,
            }
        payload = result.data[0]
        payload["degraded"] = False
        return payload
    except Exception as exc:
        return {
            "inr_balance": settings.paper_starting_balance,
            "total_value": settings.paper_starting_balance,
            "invested_value": 0,
            "pnl_total": 0,
            "pnl_today": 0,
            "degraded": True,
        }


@router.get("/history")
async def get_portfolio_history():
    try:
        result = (
            get_db()
            .table("daily_summary")
            .select("date, portfolio_value, pnl_gross")
            .order("date", desc=False)
            .execute()
        )
        return {"history": result.data, "degraded": False}
    except Exception as exc:
        return {"history": [], "degraded": True}
