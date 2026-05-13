import asyncio
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from agents.analyzer import calculate_indicators, calculate_trade_levels, get_latest_signals, score_signals
from agents.executor import (
    get_latest_closed_trade,
    get_open_positions_count,
    get_paper_portfolio,
    monitor_open_trades,
    open_paper_trade,
)
from agents.llm import get_trading_decision
from agents.performance import log_agent_cycle, recalculate_performance
from agents.risk_manager import check_circuit_breaker
from config import settings
from data.coin_registry import load_trading_pairs
from data.coindcx import get_all_tickers, get_ohlcv
from data.sentiment import get_combined_sentiment

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
agent_running = False
latest_scan_snapshot = {
    "selected_pairs": [],
    "ranked_pairs": [],
    "updated_at": None,
}


def _build_rule_based_hold(signals: dict, scores: dict, sentiment: dict) -> dict | None:
    trend = signals.get("trend", "unknown")
    rsi = float(signals.get("rsi", 50))
    macd_state = signals.get("macd_crossover", "none")
    bullish_macd = macd_state in {"bullish", "bullish_continuation"}
    total = int(scores.get("total", 0))
    volume_veto = bool(scores.get("volume_veto"))
    volume_override_candidate = bool(scores.get("volume_override_candidate", False))
    pause_trading = bool(sentiment.get("pause_trading"))

    favorable_setup = (
        trend == "uptrend"
        and bullish_macd
        and total >= 68
        and rsi <= 68
        and (not volume_veto or volume_override_candidate)
    )
    caution_setup = (
        trend == "uptrend"
        and bullish_macd
        and total >= 60
        and (not volume_veto or volume_override_candidate)
    )

    if favorable_setup or caution_setup:
        return None

    reasons = []
    confidence = 40
    risk = "medium"

    if pause_trading:
        reasons.append("trading pause active")
        confidence = 40
        risk = "high"

    if total < 45:
        reasons.append("signal score too weak")
        confidence = 35
        risk = "high"

    if trend != "uptrend" and rsi > 25:
        reasons.append("trend not favorable")
        confidence = min(confidence, 40)
        risk = "high"

    if not bullish_macd and total < 60:
        reasons.append("MACD not bullish")
        confidence = min(confidence, 40)

    if volume_veto and total < 68:
        reasons.append("effective hard volume veto")
        confidence = min(confidence, 40)
        risk = "high"

    if rsi > 72:
        reasons.append("RSI overbought")
        confidence = min(confidence, 40)

    if not reasons:
        return None

    skip_reason = ", ".join(dict.fromkeys(reasons))
    return {
        "action": "HOLD",
        "confidence": confidence,
        "reasoning": "Rule-based prefilter skipped Groq because the setup was clearly not strong enough.",
        "key_signals": [trend, macd_state, f"score {total}/90"],
        "risk_assessment": risk,
        "skip_reason": skip_reason,
    }


def _rank_candidate_pairs(tradable_pairs: list[str], tickers: dict) -> list[str]:
    ranked = []
    for pair in tradable_pairs:
        ticker = tickers.get(pair)
        if not ticker:
            continue

        price = float(ticker.get("price", 0) or 0)
        volume = float(ticker.get("volume", 0) or 0)
        bid = float(ticker.get("bid", 0) or 0)
        ask = float(ticker.get("ask", 0) or 0)
        change_24h = float(ticker.get("change_24h", 0) or 0)

        notional_volume = price * volume
        spread_pct = ((ask - bid) / ask * 100) if ask > 0 and bid > 0 and ask >= bid else 99.0
        momentum_score = min(abs(change_24h), 25.0) * 50000
        spread_penalty = spread_pct * 250000
        ranking_score = notional_volume + momentum_score - spread_penalty

        ranked.append(
            {
                "pair": pair,
                "score": ranking_score,
                "notional_volume": notional_volume,
                "change_24h": change_24h,
                "spread_pct": spread_pct,
            }
        )

    ranked.sort(
        key=lambda item: (
            item["score"],
            item["notional_volume"],
            abs(item["change_24h"]),
        ),
        reverse=True,
    )
    return ranked


def _build_scan_shortlist(tradable_pairs: list[str], tickers: dict) -> list[str]:
    global latest_scan_snapshot

    ranked = _rank_candidate_pairs(tradable_pairs, tickers)
    core_pairs = [pair for pair in settings.core_trading_pairs if pair in tradable_pairs]
    shortlist = []

    for pair in core_pairs:
        if pair not in shortlist:
            shortlist.append(pair)

    for item in ranked:
        pair = item["pair"]
        if pair not in shortlist:
            shortlist.append(pair)
        if len(shortlist) >= max(settings.scan_top_n, len(core_pairs)):
            break

    ranked_preview = [
        {
            "pair": item["pair"],
            "score": round(item["score"], 2),
            "vol_inr": round(item["notional_volume"], 2),
            "change_24h": round(item["change_24h"], 2),
            "spread_pct": round(item["spread_pct"], 3),
        }
        for item in ranked[: min(len(ranked), settings.scan_top_n)]
    ]

    latest_scan_snapshot = {
        "selected_pairs": shortlist.copy(),
        "ranked_pairs": ranked_preview,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "Ranked scan shortlist: %s",
        ranked_preview,
    )
    logger.info("Selected pairs for this cycle: %s", shortlist)
    return shortlist


async def run_agent_cycle(*, allow_trading: bool = True, cycle_label: str = "scheduled"):
    global agent_running

    started_at = datetime.now(timezone.utc)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    logger.info("Cycle start | type=%s | trading_enabled=%s | at=%s", cycle_label, allow_trading, now)
    cycle_stats = {
        "type": cycle_label,
        "trading_enabled": allow_trading,
        "selected_count": 0,
        "analyzed": 0,
        "buy": 0,
        "hold": 0,
        "skipped": 0,
        "errors": 0,
        "sentiment_paused": False,
    }

    try:
        tickers = await get_all_tickers()
        if not tickers:
            logger.error("No ticker data available, skipping cycle")
            return

        portfolio = await get_paper_portfolio()
        open_count = await get_open_positions_count()
        inr_balance = portfolio.get("inr_balance", settings.paper_starting_balance)
        total_value = portfolio.get("total_value", settings.paper_starting_balance)
        daily_pnl = portfolio.get("pnl_today", 0)

        logger.info(
            "Portfolio: INR %.2f available | INR %.2f total | %s open positions",
            inr_balance,
            total_value,
            open_count,
        )

        breaker = check_circuit_breaker(
            portfolio_balance=total_value,
            starting_balance=settings.paper_starting_balance,
            daily_pnl=daily_pnl,
        )
        if breaker["stop_trading"]:
            logger.warning("Circuit breaker active: %s", breaker["reason"])
            return

        sentiment = await get_combined_sentiment()
        logger.info(
            "Market regime | fg=%s(%s) | btc_dom=%.1f%% | sentiment=%s/100(%s) | news_risk=%s",
            sentiment["fear_greed"]["score"],
            sentiment["fear_greed"]["label"],
            sentiment["btc_dominance"]["btc_dominance"],
            sentiment["combined_score"],
            sentiment["sentiment_label"],
            sentiment.get("news_risk_level", "normal"),
        )

        if sentiment.get("pause_trading"):
            cycle_stats["sentiment_paused"] = True
            logger.warning("High-risk news detected, skipping new entries this cycle")
        elif sentiment.get("news_risk_level") == "caution":
            logger.info("Cautionary news detected, but trading remains enabled for strong setups")
        if not allow_trading:
            logger.info("Observation mode active for this cycle")

        portfolio_context = {
            "inr_balance": inr_balance,
            "total_value": total_value,
            "open_positions": open_count,
        }

        tradable_pairs = load_trading_pairs()
        if not tradable_pairs:
            logger.warning("No tradable pairs configured, skipping cycle")
            return

        selected_pairs = _build_scan_shortlist(tradable_pairs, tickers)
        cycle_stats["selected_count"] = len(selected_pairs)
        for pair in selected_pairs:
            result = await analyze_coin(
                pair,
                tickers,
                sentiment,
                portfolio_context,
                allow_trading=allow_trading,
            )
            cycle_stats["analyzed"] += 1
            if result == "BUY":
                cycle_stats["buy"] += 1
            elif result == "HOLD":
                cycle_stats["hold"] += 1
            elif result == "SKIPPED":
                cycle_stats["skipped"] += 1
            elif result == "ERROR":
                cycle_stats["errors"] += 1
            await asyncio.sleep(2)

        duration = (datetime.now(timezone.utc) - started_at).total_seconds()
        logger.info(
            "Cycle summary | type=%s | trading_enabled=%s | selected=%s | analyzed=%s | buy=%s | hold=%s | skipped=%s | errors=%s | sentiment_paused=%s | duration=%.1fs",
            cycle_stats["type"],
            cycle_stats["trading_enabled"],
            cycle_stats["selected_count"],
            cycle_stats["analyzed"],
            cycle_stats["buy"],
            cycle_stats["hold"],
            cycle_stats["skipped"],
            cycle_stats["errors"],
            cycle_stats["sentiment_paused"],
            duration,
        )
    except Exception as exc:
        logger.error("Agent cycle error: %s", exc, exc_info=True)


async def analyze_coin(pair: str, tickers: dict, sentiment: dict, portfolio: dict, *, allow_trading: bool = True):
    ticker = tickers.get(pair)
    if not ticker:
        logger.warning("No ticker for %s, skipping", pair)
        return "SKIPPED"

    current_price = ticker["price"]

    try:
        df = await get_ohlcv(pair, interval="1h", limit=200)
        if df is None or df.empty or len(df) < 50:
            message = "Insufficient candle data"
            logger.warning("%s for %s, skipping", message, pair)
            await log_agent_cycle(pair, "SKIPPED", {}, sentiment, {}, current_price, message)
            return "SKIPPED"

        df = calculate_indicators(df)
        if df is None:
            message = "Indicator calculation failed"
            logger.warning("%s for %s", message, pair)
            await log_agent_cycle(pair, "SKIPPED", {}, sentiment, {}, current_price, message)
            return "SKIPPED"

        signals = get_latest_signals(df)
        if not signals:
            message = "Could not extract signals"
            logger.warning("%s for %s", message, pair)
            await log_agent_cycle(pair, "SKIPPED", {}, sentiment, {}, current_price, message)
            return "SKIPPED"

        scores = score_signals(signals)
        decision = _build_rule_based_hold(signals, scores, sentiment)
        if decision is None:
            decision = await get_trading_decision(
                pair=pair,
                signals=signals,
                signal_scores=scores,
                sentiment=sentiment,
                portfolio=portfolio,
            )
        else:
            logger.info(
                "Skipping Groq for %s | score=%s | trend=%s | rsi=%.1f | reason=%s",
                pair,
                scores["total"],
                signals["trend"],
                signals["rsi"],
                decision["skip_reason"],
            )

        action = decision.get("action", "HOLD")
        confidence = decision.get("confidence", 0)
        reasoning = decision.get("reasoning", "")
        risk_level = decision.get("risk_assessment", "unknown")

        if action == "BUY" and confidence >= settings.min_confidence_threshold:
            if not allow_trading:
                message = "Startup observation mode: trade execution disabled"
                logger.info(
                    "Coin summary | %s | score=%s | trend=%s | rsi=%.1f | action=HOLD | conf=%s | risk=%s | reason=%s",
                    pair,
                    scores["total"],
                    signals["trend"],
                    signals["rsi"],
                    confidence,
                    risk_level,
                    message,
                )
                await log_agent_cycle(pair, "HOLD", signals, sentiment, decision, current_price, message)
                return "HOLD"

            latest_closed = await get_latest_closed_trade(pair)
            if latest_closed and latest_closed.get("closed_at"):
                try:
                    closed_at = datetime.fromisoformat(str(latest_closed["closed_at"]).replace("Z", "+00:00"))
                    cooldown_until = closed_at + timedelta(minutes=settings.coin_reentry_cooldown_minutes)
                    if datetime.now(timezone.utc) < cooldown_until:
                        pnl_after_tax = float(latest_closed.get("pnl_after_tax", 0) or 0)
                        message = (
                            f"Cooldown active until {cooldown_until.astimezone().strftime('%I:%M %p')}"
                            f" after recent {'profit' if pnl_after_tax > 0 else 'exit'}"
                        )
                        logger.info(
                            "Coin summary | %s | score=%s | trend=%s | rsi=%.1f | action=SKIPPED | conf=%s | risk=%s | reason=%s",
                            pair,
                            scores["total"],
                            signals["trend"],
                            signals["rsi"],
                            confidence,
                            risk_level,
                            message,
                        )
                        await log_agent_cycle(pair, "SKIPPED", signals, sentiment, decision, current_price, message)
                        return "SKIPPED"
                except Exception as exc:
                    logger.warning("Could not evaluate cooldown for %s: %s", pair, exc)

            open_count = await get_open_positions_count()
            if open_count >= settings.max_open_positions:
                message = "Max positions reached"
                logger.info(
                    "Coin summary | %s | score=%s | trend=%s | rsi=%.1f | action=SKIPPED | conf=%s | risk=%s | reason=%s",
                    pair,
                    scores["total"],
                    signals["trend"],
                    signals["rsi"],
                    confidence,
                    risk_level,
                    message,
                )
                await log_agent_cycle(pair, "SKIPPED", signals, sentiment, decision, current_price, message)
                return "SKIPPED"

            trade_levels = calculate_trade_levels(signals, confidence)

            trade = await open_paper_trade(
                pair=pair,
                decision=decision,
                signals=signals,
                trade_levels=trade_levels,
                signal_scores=scores,
                sentiment=sentiment,
            )

            if trade:
                portfolio["open_positions"] = open_count + 1
                logger.info(
                    "Coin summary | %s | score=%s | trend=%s | rsi=%.1f | action=BUY | conf=%s | risk=%s | trade_id=%s | rr=%s",
                    pair,
                    scores["total"],
                    signals["trend"],
                    signals["rsi"],
                    confidence,
                    risk_level,
                    trade.get("trade_id"),
                    trade_levels["risk_reward_1"],
                )
            else:
                logger.info(
                    "Coin summary | %s | score=%s | trend=%s | rsi=%.1f | action=SKIPPED | conf=%s | risk=%s | reason=trade_open_failed",
                    pair,
                    scores["total"],
                    signals["trend"],
                    signals["rsi"],
                    confidence,
                    risk_level,
                )

            await log_agent_cycle(pair, "BUY", signals, sentiment, decision, current_price)
            return "BUY"

        skip_reason = decision.get("skip_reason", f"Action={action}, Confidence={confidence}%")
        logger.info(
            "Coin summary | %s | score=%s | trend=%s | rsi=%.1f | action=HOLD | conf=%s | risk=%s | reason=%s",
            pair,
            scores["total"],
            signals["trend"],
            signals["rsi"],
            confidence,
            risk_level,
            skip_reason,
        )
        await log_agent_cycle(pair, "HOLD", signals, sentiment, decision, current_price, skip_reason)
        return "HOLD"
    except Exception as exc:
        logger.error("Error analyzing %s: %s", pair, exc, exc_info=True)
        await log_agent_cycle(pair, "SKIPPED", {}, sentiment, {}, current_price, str(exc))
        return "ERROR"


async def monitor_positions():
    try:
        tickers = await get_all_tickers()
        if tickers:
            await monitor_open_trades(tickers)
    except Exception as exc:
        logger.error("Position monitor error: %s", exc)


async def update_performance():
    logger.info("Recalculating performance metrics")
    await recalculate_performance()


def start_scheduler():
    global agent_running

    scheduler.add_job(
        run_agent_cycle,
        trigger=IntervalTrigger(minutes=settings.trade_interval_minutes),
        id="agent_cycle",
        name="Main Trading Cycle",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=900,
    )
    scheduler.add_job(
        monitor_positions,
        trigger=IntervalTrigger(minutes=settings.position_monitor_interval_minutes),
        id="position_monitor",
        name="Position Monitor",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        update_performance,
        trigger=IntervalTrigger(hours=6),
        id="performance_update",
        name="Performance Recalculator",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=1800,
    )

    scheduler.start()
    agent_running = True
    logger.info("Scheduler started")
    logger.info("Trading cycle: every %s minutes", settings.trade_interval_minutes)
    logger.info("Ranked scan: top %s tradable pairs per cycle", settings.scan_top_n)
    logger.info("Core scan pairs: %s", settings.core_trading_pairs)
    logger.info("Position monitor: every %s minutes", settings.position_monitor_interval_minutes)
    logger.info("Performance update: every 6 hours")


def stop_scheduler():
    global agent_running
    if scheduler.running:
        scheduler.shutdown(wait=False)
    agent_running = False
    logger.info("Scheduler stopped")


def is_running() -> bool:
    return agent_running and scheduler.running


def get_latest_scan_snapshot() -> dict:
    return latest_scan_snapshot


async def run_now():
    logger.info("Manual cycle triggered")
    await run_agent_cycle(cycle_label="manual")


async def run_startup_cycle():
    logger.info("Startup cycle triggered")
    await run_agent_cycle(
        allow_trading=settings.startup_trade_enabled,
        cycle_label="startup",
    )
