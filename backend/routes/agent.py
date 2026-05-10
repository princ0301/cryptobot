import logging

from fastapi import APIRouter, HTTPException

from agents.scheduler import is_running
from models.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
async def get_agent_status():
    try:
        supabase = get_db()
        metrics = supabase.table("performance_metrics").select("*").order("id", desc=True).limit(1).execute()
        last_log = supabase.table("agent_logs").select("*").order("cycle_time", desc=True).limit(1).execute()

        metrics_data = metrics.data[0] if metrics.data else {}
        last_log_data = last_log.data[0] if last_log.data else {}

        return {
            "is_running": is_running(),
            "mode": "paper",
            "last_analysis": last_log_data.get("cycle_time"),
            "last_action": last_log_data.get("action_taken"),
            "last_coin": last_log_data.get("coin"),
            "total_trades": metrics_data.get("total_trades", 0),
            "live_mode_unlocked": metrics_data.get("live_mode_unlocked", False),
            "all_criteria_met": metrics_data.get("all_criteria_met", False),
        }
    except Exception as exc:
        logger.error("Error getting agent status: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/start")
async def start_agent():
    return {"message": "Agent started", "mode": "paper", "status": "running"}


@router.post("/stop")
async def stop_agent():
    return {"message": "Agent stopped", "status": "stopped"}


@router.get("/last-analysis")
async def get_last_analysis():
    try:
        supabase = get_db()
        logs = supabase.table("agent_logs").select("*").order("cycle_time", desc=True).limit(3).execute()
        return {"analyses": logs.data}
    except Exception as exc:
        logger.error("Error getting last analysis: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
