import logging

from data.coindcx import PAIR_MAP
from models.database import get_db
from config import settings

logger = logging.getLogger(__name__)


def _db():
    return get_db()


def _coin_label(coin: str) -> str:
    return PAIR_MAP.get(coin, {}).get("display", coin)


async def recalculate_performance() -> dict:
    try:
        result = (
            _db()
            .table("trades")
            .select("*")
            .eq("mode", "paper")
            .neq("status", "OPEN")
            .execute()
        )
        trades = result.data

        if not trades:
            logger.info("No closed trades yet for performance calculation")
            return {}

        total_trades = len(trades)
        winning = [trade for trade in trades if float(trade.get("pnl_gross", 0)) > 0]
        losing = [trade for trade in trades if float(trade.get("pnl_gross", 0)) <= 0]

        win_count = len(winning)
        loss_count = len(losing)
        win_rate = (win_count / total_trades) * 100 if total_trades else 0

        total_wins = sum(float(trade.get("pnl_gross", 0)) for trade in winning)
        total_losses = abs(sum(float(trade.get("pnl_gross", 0)) for trade in losing))
        if total_losses > 0:
            profit_factor = total_wins / total_losses
        elif total_wins > 0:
            profit_factor = total_wins
        else:
            profit_factor = 0

        max_drawdown = await _calculate_max_drawdown()
        total_pnl = sum(float(trade.get("pnl_after_tax", 0)) for trade in trades)
        best_trade = max((float(trade.get("pnl_gross", 0)) for trade in trades), default=0)
        worst_trade = min((float(trade.get("pnl_gross", 0)) for trade in trades), default=0)
        avg_win = (total_wins / win_count) if win_count else 0
        avg_loss = (total_losses / loss_count) if loss_count else 0
        avg_conf = sum(float(trade.get("confidence", 0)) for trade in trades) / total_trades

        enough_trades = total_trades >= settings.min_trades_required
        win_rate_pass = win_rate >= settings.min_win_rate and enough_trades
        drawdown_pass = max_drawdown < settings.max_drawdown_allowed
        profit_factor_pass = profit_factor >= settings.min_profit_factor and enough_trades
        all_criteria_met = win_rate_pass and drawdown_pass and profit_factor_pass

        metrics = {
            "total_trades": total_trades,
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 4),
            "max_drawdown": round(max_drawdown, 2),
            "total_pnl": round(total_pnl, 2),
            "best_trade_pnl": round(best_trade, 2),
            "worst_trade_pnl": round(worst_trade, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "avg_confidence": round(avg_conf, 2),
            "criteria_win_rate_pass": win_rate_pass,
            "criteria_drawdown_pass": drawdown_pass,
            "criteria_profit_factor_pass": profit_factor_pass,
            "all_criteria_met": all_criteria_met,
            "live_mode_unlocked": all_criteria_met,
        }

        _db().table("performance_metrics").insert(metrics).execute()
        await _update_coin_performance(trades)

        if all_criteria_met:
            logger.info("All promotion criteria met. Live mode unlocked.")
        else:
            logger.info(
                "Performance: WR=%.1f%% PF=%.2f DD=%.1f%% (%s/%s trades)",
                win_rate,
                profit_factor,
                max_drawdown,
                total_trades,
                settings.min_trades_required,
            )

        return metrics
    except Exception as exc:
        logger.error("Error recalculating performance: %s", exc)
        return {}


async def _calculate_max_drawdown() -> float:
    try:
        result = _db().table("paper_portfolio").select("total_value").order("id", desc=False).execute()
        values = [float(row["total_value"]) for row in result.data]

        if not values:
            return 0.0

        peak = values[0]
        max_drawdown = 0.0
        for value in values:
            if value > peak:
                peak = value
            drawdown = ((peak - value) / peak) * 100 if peak else 0
            max_drawdown = max(max_drawdown, drawdown)

        return round(max_drawdown, 2)
    except Exception as exc:
        logger.error("Drawdown calculation error: %s", exc)
        return 0.0


async def _update_coin_performance(trades: list[dict]):
    coin_stats: dict[str, dict[str, float]] = {}

    for trade in trades:
        coin = trade.get("coin", "")
        stats = coin_stats.setdefault(coin, {"total": 0, "wins": 0, "pnl": 0.0})
        stats["total"] += 1
        if float(trade.get("pnl_gross", 0)) > 0:
            stats["wins"] += 1
        stats["pnl"] += float(trade.get("pnl_after_tax", 0))

    for coin, stats in coin_stats.items():
        win_rate = (stats["wins"] / stats["total"] * 100) if stats["total"] else 0
        _db().table("coin_performance").upsert(
            {
                "coin": _coin_label(coin),
                "total_trades": stats["total"],
                "winning_trades": stats["wins"],
                "win_rate": round(win_rate, 2),
                "total_pnl": round(stats["pnl"], 2),
            },
            on_conflict="coin",
        ).execute()


async def log_agent_cycle(
    coin: str,
    action: str,
    signals: dict,
    sentiment: dict,
    decision: dict,
    current_price: float,
    skip_reason: str | None = None,
):
    try:
        _db().table("agent_logs").insert(
            {
                "coin": coin,
                "action_taken": action,
                "skip_reason": skip_reason,
                "confidence": decision.get("confidence", 0),
                "current_price": current_price,
                "indicators": signals,
                "sentiment": {
                    "score": sentiment.get("combined_score"),
                    "label": sentiment.get("sentiment_label"),
                    "fg_score": sentiment.get("fear_greed", {}).get("score"),
                },
                "gemini_response": {
                    "action": decision.get("action"),
                    "confidence": decision.get("confidence"),
                    "reasoning": decision.get("reasoning"),
                    "key_signals": decision.get("key_signals", []),
                },
            }
        ).execute()
    except Exception as exc:
        logger.error("Error logging agent cycle: %s", exc)
