import logging
from datetime import datetime, timezone

from agents.risk_manager import calculate_pnl, calculate_position
from config import settings
from data.coindcx import get_all_tickers
from models.database import get_db

logger = logging.getLogger(__name__)


def _db():
    return get_db()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_paper_portfolio() -> dict:
    default_portfolio = {
        "inr_balance": settings.paper_starting_balance,
        "total_value": settings.paper_starting_balance,
        "invested_value": 0,
        "pnl_total": 0,
        "pnl_today": 0,
    }

    try:
        result = _db().table("paper_portfolio").select("*").order("id", desc=True).limit(1).execute()
        return result.data[0] if result.data else default_portfolio
    except Exception as exc:
        logger.error("Error fetching paper portfolio: %s", exc)
        return default_portfolio


async def get_open_positions_count() -> int:
    try:
        result = _db().table("open_positions").select("id").eq("mode", "paper").execute()
        return len(result.data)
    except Exception as exc:
        logger.error("Error fetching open positions count: %s", exc)
        return 0


def _insert_portfolio_snapshot(
    portfolio: dict,
    *,
    inr_balance: float,
    total_value: float | None = None,
    invested_value: float | None = None,
    pnl_total: float | None = None,
    pnl_today: float | None = None,
):
    _db().table("paper_portfolio").insert(
        {
            "inr_balance": round(inr_balance, 2),
            "total_value": round(total_value if total_value is not None else inr_balance, 2),
            "invested_value": round(
                invested_value if invested_value is not None else portfolio.get("invested_value", 0),
                2,
            ),
            "pnl_total": round(pnl_total if pnl_total is not None else portfolio.get("pnl_total", 0), 2),
            "pnl_today": round(pnl_today if pnl_today is not None else portfolio.get("pnl_today", 0), 2),
        }
    ).execute()


def _update_trade_realization(trade_id: int, pnl: dict, *, status: str | None = None, exit_price: float | None = None):
    trade_result = _db().table("trades").select("*").eq("id", trade_id).single().execute()
    trade = trade_result.data or {}

    update_payload = {
        "pnl_gross": round(float(trade.get("pnl_gross", 0)) + pnl["gross_pnl"], 2),
        "pnl_after_tax": round(float(trade.get("pnl_after_tax", 0)) + pnl["net_pnl"], 2),
        "tax_provision": round(float(trade.get("tax_provision", 0)) + pnl["tax_amount"], 2),
        "tds_deducted": round(float(trade.get("tds_deducted", 0)) + pnl["tds_amount"], 2),
    }

    if status:
        update_payload["status"] = status
    if exit_price is not None:
        update_payload["exit_price"] = exit_price
    if status and status != "OPEN":
        update_payload["closed_at"] = _now_iso()

    _db().table("trades").update(update_payload).eq("id", trade_id).execute()


def _cash_released(entry_price: float, quantity: float, pnl: dict) -> float:
    return (entry_price * quantity) + pnl["net_pnl"]


def _get_trade_snapshot(trade_id: int) -> dict:
    try:
        trade_result = _db().table("trades").select("*").eq("id", trade_id).single().execute()
        return trade_result.data or {}
    except Exception as exc:
        logger.error("Error fetching trade snapshot %s: %s", trade_id, exc)
        return {}


async def get_latest_closed_trade(pair: str) -> dict:
    try:
        result = (
            _db()
            .table("trades")
            .select("*")
            .eq("mode", "paper")
            .eq("coin", pair)
            .neq("status", "OPEN")
            .order("closed_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else {}
    except Exception as exc:
        logger.error("Error fetching latest closed trade for %s: %s", pair, exc)
        return {}


def _get_initial_risk(position: dict, trade: dict) -> float:
    entry = float(position["entry_price"])
    initial_stop = float(trade.get("stop_loss", position["stop_loss"]))
    return max(0.0, entry - initial_stop)


async def open_paper_trade(
    pair: str,
    decision: dict,
    signals: dict,
    trade_levels: dict,
    signal_scores: dict,
    sentiment: dict,
) -> dict:
    portfolio = await get_paper_portfolio()
    open_count = await get_open_positions_count()
    inr_balance = portfolio.get("inr_balance", settings.paper_starting_balance)

    entry_price = trade_levels["entry"]
    stop_loss = trade_levels["stop_loss"]
    take_profit_1 = trade_levels["tp1_with_tax"]
    take_profit_2 = trade_levels["tp2_with_tax"]
    confidence = decision.get("confidence", 0)

    position = calculate_position(
        confidence=confidence,
        portfolio_balance=inr_balance,
        entry_price=entry_price,
        stop_loss=stop_loss,
        open_positions=open_count,
    )
    if not position:
        logger.error("Position calculation failed")
        return {}

    quantity = position["quantity"]
    position_inr = position["position_inr"]
    risk_inr = position["risk_inr"]

    if position_inr > inr_balance:
        logger.warning(
            "Insufficient paper balance: need INR %.0f, have INR %.0f",
            position_inr,
            inr_balance,
        )
        return {}

    now = _now_iso()
    trade_data = {
        "mode": "paper",
        "coin": pair,
        "action": decision["action"],
        "status": "OPEN",
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit_1": take_profit_1,
        "take_profit_2": take_profit_2,
        "quantity": quantity,
        "position_inr": position_inr,
        "risk_inr": risk_inr,
        "confidence": confidence,
        "risk_reward": trade_levels.get("risk_reward_1", ""),
        "reasoning": decision.get("reasoning", ""),
        "signals": signals,
        "sentiment": {
            "combined_score": sentiment.get("combined_score"),
            "fear_greed": sentiment.get("fear_greed", {}).get("score"),
            "btc_dominance": sentiment.get("btc_dominance", {}).get("btc_dominance"),
            "reddit_signal": sentiment.get("reddit", {}).get("signal"),
            "score_breakdown": signal_scores.get("breakdown", {}),
        },
        "opened_at": now,
    }

    trade_result = _db().table("trades").insert(trade_data).execute()
    trade_id = trade_result.data[0]["id"]

    _db().table("open_positions").insert(
        {
            "trade_id": trade_id,
            "coin": pair,
            "action": decision["action"],
            "entry_price": entry_price,
            "current_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit_1": take_profit_1,
            "take_profit_2": take_profit_2,
            "quantity": quantity,
            "position_inr": position_inr,
            "mode": "paper",
            "opened_at": now,
        }
    ).execute()

    new_balance = inr_balance - position_inr
    _insert_portfolio_snapshot(
        portfolio,
        inr_balance=new_balance,
        total_value=portfolio.get("total_value", inr_balance),
        invested_value=portfolio.get("invested_value", 0) + position_inr,
    )

    logger.info(
        "Paper trade opened: %s %s qty=%s @ INR %.2f | SL=INR %.2f TP1=INR %.2f",
        pair,
        decision["action"],
        quantity,
        entry_price,
        stop_loss,
        take_profit_1,
    )

    return {
        "trade_id": trade_id,
        "pair": pair,
        "action": decision["action"],
        "quantity": quantity,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit_1": take_profit_1,
        "take_profit_2": take_profit_2,
        "position_inr": position_inr,
        "risk_inr": risk_inr,
    }


async def monitor_open_trades(current_prices: dict):
    try:
        result = _db().table("open_positions").select("*").eq("mode", "paper").execute()
        positions = result.data
    except Exception as exc:
        logger.error("Error fetching open positions: %s", exc)
        return

    for position in positions:
        pair = position["coin"]
        current_price = current_prices.get(pair, {}).get("price")
        if not current_price:
            continue

        trade = _get_trade_snapshot(position["trade_id"])
        entry = float(position["entry_price"])
        stop_loss = float(position["stop_loss"])
        take_profit_1 = float(position["take_profit_1"])
        take_profit_2 = float(position["take_profit_2"])
        quantity = float(position["quantity"])
        tp1_hit = bool(position.get("tp1_hit", False))
        initial_risk = _get_initial_risk(position, trade)

        if current_price <= stop_loss:
            logger.warning("Stop loss hit: %s @ INR %.2f", pair, stop_loss)
            await close_paper_trade(position, stop_loss, "CLOSED_SL")
            continue

        if initial_risk > 0 and not tp1_hit:
            early_lock_trigger = entry + (initial_risk * settings.profit_lock_trigger_r_multiple)
            early_lock_stop = entry - (initial_risk * settings.profit_lock_buffer_r_multiple)

            if current_price >= early_lock_trigger and stop_loss < early_lock_stop:
                logger.info(
                    "Profit lock activated: %s @ INR %.2f - tightening SL from INR %.2f to INR %.2f",
                    pair,
                    current_price,
                    stop_loss,
                    early_lock_stop,
                )
                stop_loss = early_lock_stop
                _db().table("open_positions").update(
                    {
                        "stop_loss": round(early_lock_stop, 2),
                        "current_price": current_price,
                        "unrealized_pnl": round((current_price - entry) * quantity, 2),
                        "updated_at": _now_iso(),
                    }
                ).eq("id", position["id"]).execute()

        if not tp1_hit and current_price >= take_profit_1:
            logger.info(
                "TP1 hit: %s @ INR %.2f - realizing %.0f%% and moving SL to breakeven",
                pair,
                take_profit_1,
                settings.partial_take_profit_fraction * 100,
            )
            await take_partial_profit(position, take_profit_1, current_price)
            continue

        if tp1_hit and current_price >= take_profit_2:
            logger.info("TP2 hit: %s @ INR %.2f - full exit", pair, take_profit_2)
            await close_paper_trade(position, take_profit_2, "CLOSED_TP2")
            continue

        if initial_risk > 0 and current_price >= entry + (initial_risk * settings.trailing_stop_trigger_r_multiple):
            trailing_stop = current_price - (initial_risk * settings.trailing_stop_distance_r_multiple)
            desired_stop = max(stop_loss, entry, trailing_stop)
            if desired_stop > stop_loss:
                logger.info(
                    "Trailing stop advanced: %s @ INR %.2f - moving SL from INR %.2f to INR %.2f",
                    pair,
                    current_price,
                    stop_loss,
                    desired_stop,
                )
                stop_loss = desired_stop
                _db().table("open_positions").update(
                    {
                        "stop_loss": round(desired_stop, 2),
                        "current_price": current_price,
                        "unrealized_pnl": round((current_price - entry) * quantity, 2),
                        "updated_at": _now_iso(),
                    }
                ).eq("id", position["id"]).execute()

        unrealized = (current_price - entry) * quantity
        _db().table("open_positions").update(
            {
                "current_price": current_price,
                "unrealized_pnl": round(unrealized, 2),
                "updated_at": _now_iso(),
            }
        ).eq("id", position["id"]).execute()


async def take_partial_profit(position: dict, exit_price: float, current_price: float):
    trade_id = position["trade_id"]
    entry = float(position["entry_price"])
    quantity = float(position["quantity"])
    position_inr = float(position["position_inr"])
    close_qty = quantity * settings.partial_take_profit_fraction
    remaining_qty = quantity - close_qty

    pnl = calculate_pnl(entry, exit_price, close_qty, "BUY")
    portfolio = await get_paper_portfolio()
    released_cash = _cash_released(entry, close_qty, pnl)
    remaining_position_inr = remaining_qty * entry

    _update_trade_realization(trade_id, pnl)

    _db().table("open_positions").update(
        {
            "tp1_hit": True,
            "quantity": round(remaining_qty, 8),
            "position_inr": round(remaining_position_inr, 2),
            "stop_loss": entry,
            "current_price": current_price,
            "unrealized_pnl": round((current_price - entry) * remaining_qty, 2),
            "updated_at": _now_iso(),
        }
    ).eq("id", position["id"]).execute()

    _insert_portfolio_snapshot(
        portfolio,
        inr_balance=portfolio["inr_balance"] + released_cash,
        total_value=portfolio["total_value"] + pnl["net_pnl"],
        invested_value=max(
            0,
            portfolio.get("invested_value", 0) - (position_inr * settings.partial_take_profit_fraction),
        ),
        pnl_total=portfolio.get("pnl_total", 0) + pnl["net_pnl"],
        pnl_today=portfolio.get("pnl_today", 0) + pnl["net_pnl"],
    )


async def close_paper_trade(position: dict, exit_price: float, reason: str):
    trade_id = position["trade_id"]
    entry = float(position["entry_price"])
    quantity = float(position["quantity"])
    position_inr = float(position["position_inr"])

    pnl = calculate_pnl(entry, exit_price, quantity, "BUY")
    portfolio = await get_paper_portfolio()
    released_cash = _cash_released(entry, quantity, pnl)

    _update_trade_realization(trade_id, pnl, status=reason, exit_price=exit_price)
    _db().table("open_positions").delete().eq("id", position["id"]).execute()

    _insert_portfolio_snapshot(
        portfolio,
        inr_balance=portfolio["inr_balance"] + released_cash,
        total_value=portfolio["total_value"] + pnl["net_pnl"],
        invested_value=max(0, portfolio.get("invested_value", 0) - position_inr),
        pnl_total=portfolio.get("pnl_total", 0) + pnl["net_pnl"],
        pnl_today=portfolio.get("pnl_today", 0) + pnl["net_pnl"],
    )

    logger.info(
        "%s trade closed: %s %s @ INR %.2f | P&L: INR %.2f gross / INR %.2f net",
        "Profit" if pnl["is_profit"] else "Loss",
        position["coin"],
        reason,
        exit_price,
        pnl["gross_pnl"],
        pnl["net_pnl"],
    )


async def manually_close_trade(trade_id: int) -> dict:
    result = _db().table("open_positions").select("*").eq("trade_id", trade_id).single().execute()
    position = result.data
    if not position:
        raise ValueError("Open trade not found")

    pair = position["coin"]
    tickers = await get_all_tickers()
    current_price = float(tickers.get(pair, {}).get("price") or 0)
    if current_price <= 0:
        current_price = float(position.get("current_price") or 0)
    if current_price <= 0:
        raise ValueError(f"Current price unavailable for {pair}")

    await close_paper_trade(position, current_price, "CLOSED_MANUAL")
    logger.info("Manual exit executed: %s trade_id=%s @ INR %.2f", pair, trade_id, current_price)
    return {
        "trade_id": trade_id,
        "coin": pair,
        "exit_price": round(current_price, 2),
        "status": "CLOSED_MANUAL",
    }
