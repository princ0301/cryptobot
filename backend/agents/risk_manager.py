import logging

from config import settings

logger = logging.getLogger(__name__)


def calculate_position(
    confidence: float,
    portfolio_balance: float,
    entry_price: float,
    stop_loss: float,
    open_positions: int = 0,
) -> dict:
    if confidence >= 80:
        risk_pct = 0.03
    elif confidence >= 65:
        risk_pct = 0.02
    else:
        risk_pct = 0.01

    if open_positions >= 3:
        logger.info("3 or more open positions detected, reducing new position size by 50%%")
        risk_pct *= 0.5
    elif open_positions == 2:
        risk_pct *= 0.75

    risk_inr = portfolio_balance * risk_pct
    stop_distance = entry_price - stop_loss

    if stop_distance <= 0:
        logger.error("Stop loss must be below entry price")
        return {}

    quantity = risk_inr / stop_distance
    position_inr = quantity * entry_price

    max_position_inr = portfolio_balance * (settings.max_position_percent / 100)
    if position_inr > max_position_inr:
        logger.info(
            "Position INR %.0f exceeds %.0f%% cap of INR %.0f, capping size",
            position_inr,
            settings.max_position_percent,
            max_position_inr,
        )
        position_inr = max_position_inr
        quantity = position_inr / entry_price
        risk_inr = quantity * stop_distance

    return {
        "quantity": round(quantity, 8),
        "position_inr": round(position_inr, 2),
        "risk_inr": round(risk_inr, 2),
        "risk_pct": round(risk_pct * 100, 2),
        "capped": position_inr >= max_position_inr * 0.99,
    }


def calculate_tax_adjusted_targets(entry: float, tp1: float, tp2: float) -> dict:
    tax_rate = settings.tax_rate_percent / 100
    tds_rate = settings.tds_rate_percent / 100

    tp1_gross_gain = tp1 - entry
    tp2_gross_gain = tp2 - entry

    tp1_tax = round(entry + (tp1_gross_gain / (1 - tax_rate)), 2)
    tp2_tax = round(entry + (tp2_gross_gain / (1 - tax_rate)), 2)

    return {
        "tp1_original": round(tp1, 2),
        "tp2_original": round(tp2, 2),
        "tp1_tax_adjusted": tp1_tax,
        "tp2_tax_adjusted": tp2_tax,
        "tds_tp1": round(tp1_tax * tds_rate, 2),
        "tds_tp2": round(tp2_tax * tds_rate, 2),
        "effective_tax_rate": f"{settings.tax_rate_percent}% + {settings.tds_rate_percent}% TDS",
    }


def claculate_tax_adjusted_targets(entry: float, tp1: float, tp2: float) -> dict:
    return calculate_tax_adjusted_targets(entry, tp1, tp2)


def check_circuit_breaker(portfolio_balance: float, starting_balance: float, daily_pnl: float) -> dict:
    daily_loss_pct = (daily_pnl / portfolio_balance) * 100 if portfolio_balance else 0
    total_drawdown_pct = (
        ((starting_balance - portfolio_balance) / starting_balance) * 100 if starting_balance else 0
    )

    stop_trading = False
    reason = None
    severity = "normal"

    if daily_loss_pct <= -5:
        stop_trading = True
        reason = f"Daily loss limit hit: {daily_loss_pct:.1f}% (limit: -5%)"
        severity = "warning"

    if total_drawdown_pct >= 10:
        stop_trading = True
        reason = f"Total drawdown alert: {total_drawdown_pct:.1f}% (alert: 10%)"
        severity = "warning"

    if total_drawdown_pct >= settings.max_drawdown_allowed:
        stop_trading = True
        reason = (
            f"Emergency stop: drawdown {total_drawdown_pct:.1f}% exceeds "
            f"max {settings.max_drawdown_allowed:.1f}%"
        )
        severity = "emergency"

    return {
        "stop_trading": stop_trading,
        "reason": reason,
        "severity": severity,
        "daily_loss_pct": round(daily_loss_pct, 2),
        "total_drawdown_pct": round(total_drawdown_pct, 2),
    }


def calculate_pnl(entry: float, exit_price: float, quantity: float, action: str = "BUY") -> dict:
    if action == "BUY":
        gross_pnl = (exit_price - entry) * quantity
    else:
        gross_pnl = (entry - exit_price) * quantity

    tax_amount = max(0, gross_pnl * (settings.tax_rate_percent / 100))
    tds_amount = exit_price * quantity * (settings.tds_rate_percent / 100)
    net_pnl = gross_pnl - tax_amount - tds_amount

    return {
        "gross_pnl": round(gross_pnl, 2),
        "tax_amount": round(tax_amount, 2),
        "tds_amount": round(tds_amount, 2),
        "net_pnl": round(net_pnl, 2),
        "is_profit": gross_pnl > 0,
    }
