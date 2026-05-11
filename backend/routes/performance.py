from fastapi import APIRouter, HTTPException

from config import settings
from models.database import get_db

router = APIRouter()


@router.get("/metrics")
async def get_performance_metrics():
    try:
        result = get_db().table("performance_metrics").select("*").order("id", desc=True).limit(1).execute()
        payload = result.data[0] if result.data else {}
        payload["degraded"] = False
        return payload
    except Exception as exc:
        return {"degraded": True}


@router.get("/criteria")
async def get_promotion_criteria():
    try:
        result = get_db().table("performance_metrics").select("*").order("id", desc=True).limit(1).execute()
        metrics = result.data[0] if result.data else {}

        win_rate = metrics.get("win_rate", 0)
        drawdown = metrics.get("max_drawdown", 0)
        profit_factor = metrics.get("profit_factor", 0)
        total_trades = metrics.get("total_trades", 0)

        return {
            "criteria": [
                {
                    "name": "Win Rate",
                    "required": settings.min_win_rate,
                    "current": win_rate,
                    "unit": "%",
                    "pass": win_rate >= settings.min_win_rate,
                    "progress": min((win_rate / settings.min_win_rate) * 100, 100),
                },
                {
                    "name": "Max Drawdown",
                    "required": settings.max_drawdown_allowed,
                    "current": drawdown,
                    "unit": "%",
                    "pass": drawdown < settings.max_drawdown_allowed,
                    "progress": min(
                        100,
                        max(
                            0,
                            ((settings.max_drawdown_allowed - drawdown) / settings.max_drawdown_allowed) * 100,
                        ),
                    ),
                },
                {
                    "name": "Profit Factor",
                    "required": settings.min_profit_factor,
                    "current": profit_factor,
                    "unit": "x",
                    "pass": profit_factor >= settings.min_profit_factor,
                    "progress": min((profit_factor / settings.min_profit_factor) * 100, 100),
                },
            ],
            "trades_completed": total_trades,
            "trades_required": settings.min_trades_required,
            "trades_progress": min((total_trades / settings.min_trades_required) * 100, 100),
            "all_criteria_met": metrics.get("all_criteria_met", False),
            "live_mode_unlocked": metrics.get("live_mode_unlocked", False),
            "degraded": False,
        }
    except Exception as exc:
        return {
            "criteria": [],
            "trades_completed": 0,
            "trades_required": settings.min_trades_required,
            "trades_progress": 0,
            "all_criteria_met": False,
            "live_mode_unlocked": False,
            "degraded": True,
        }


@router.get("/coins")
async def get_coin_performance():
    try:
        result = get_db().table("coin_performance").select("*").execute()
        return {"coins": result.data, "degraded": False}
    except Exception as exc:
        return {"coins": [], "degraded": True}
