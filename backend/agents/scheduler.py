import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from agents.analyzer import calculate_indicators, calculate_trade_levels, get_latest_signals, score_signals
from agents.executor import (
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

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    logger.info("%s", "=" * 60)
    logger.info("Agent cycle started (%s) - %s", cycle_label, now)
    logger.info("%s", "=" * 60)

    try:
        logger.info("Fetching live prices")
        tickers = await get_all_tickers()
        if not tickers:
            logger.error("No ticker data available, skipping cycle")
            return

        for ticker in tickers.values():
            logger.info(
                "%s: INR %.2f (%+.2f%%)",
                ticker["display"],
                ticker["price"],
                ticker["change_24h"],
            )

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

        logger.info("Fetching market sentiment")
        sentiment = await get_combined_sentiment()
        logger.info(
            "Fear & Greed: %s (%s)",
            sentiment["fear_greed"]["score"],
            sentiment["fear_greed"]["label"],
        )
        logger.info(
            "BTC Dominance: %.1f%%",
            sentiment["btc_dominance"]["btc_dominance"],
        )
        logger.info(
            "Combined score: %s/100 - %s",
            sentiment["combined_score"],
            sentiment["sentiment_label"],
        )

        if sentiment.get("pause_trading"):
            logger.warning("High-risk news detected, skipping new entries this cycle")
        if not allow_trading:
            logger.info("Trading is disabled for this cycle; scan will run in observation mode only")

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
        for pair in selected_pairs:
            await analyze_coin(pair, tickers, sentiment, portfolio_context, allow_trading=allow_trading)
            await asyncio.sleep(2)

        logger.info("Agent cycle complete - %s", now)
    except Exception as exc:
        logger.error("Agent cycle error: %s", exc, exc_info=True)


async def analyze_coin(pair: str, tickers: dict, sentiment: dict, portfolio: dict, *, allow_trading: bool = True):
    logger.info("Analyzing %s", pair)

    ticker = tickers.get(pair)
    if not ticker:
        logger.warning("No ticker for %s, skipping", pair)
        return

    current_price = ticker["price"]

    try:
        df = await get_ohlcv(pair, interval="1h", limit=200)
        if df is None or df.empty or len(df) < 50:
            message = "Insufficient candle data"
            logger.warning("%s for %s, skipping", message, pair)
            await log_agent_cycle(pair, "SKIPPED", {}, sentiment, {}, current_price, message)
            return

        df = calculate_indicators(df)
        if df is None:
            message = "Indicator calculation failed"
            logger.warning("%s for %s", message, pair)
            await log_agent_cycle(pair, "SKIPPED", {}, sentiment, {}, current_price, message)
            return

        signals = get_latest_signals(df)
        if not signals:
            message = "Could not extract signals"
            logger.warning("%s for %s", message, pair)
            await log_agent_cycle(pair, "SKIPPED", {}, sentiment, {}, current_price, message)
            return

        logger.info(
            "Trend: %s | RSI: %.1f | MACD: %s",
            signals["trend"],
            signals["rsi"],
            signals["macd_crossover"],
        )
        logger.info(
            "Volume: %.2fx avg | ATR: %.2f%%",
            signals["volume_ratio"],
            signals["atr_pct"],
        )

        scores = score_signals(signals)
        logger.info("Signal score: %s/90 | Tradeable: %s", scores["total"], scores["tradeable"])

        logger.info("Requesting Groq decision")
        decision = await get_trading_decision(
            pair=pair,
            signals=signals,
            signal_scores=scores,
            sentiment=sentiment,
            portfolio=portfolio,
        )

        action = decision.get("action", "HOLD")
        confidence = decision.get("confidence", 0)
        reasoning = decision.get("reasoning", "")

        logger.info(
            "Decision: %s | Confidence: %s%% | Risk: %s",
            action,
            confidence,
            decision.get("risk_assessment", "unknown"),
        )
        logger.info("Reasoning: %s", reasoning[:100])

        if action == "BUY" and confidence >= settings.min_confidence_threshold:
            if not allow_trading:
                message = "Startup observation mode: trade execution disabled"
                logger.info("Observation-only cycle, not opening %s despite BUY signal", pair)
                await log_agent_cycle(pair, "HOLD", signals, sentiment, decision, current_price, message)
                return

            open_count = portfolio.get("open_positions", 0)
            if open_count >= 3:
                message = "Max positions reached"
                logger.info("Max positions (3) reached, skipping %s", pair)
                await log_agent_cycle(pair, "SKIPPED", signals, sentiment, decision, current_price, message)
                return

            trade_levels = calculate_trade_levels(signals, confidence)
            logger.info(
                "Entry: INR %.2f | SL: INR %.2f | TP1: INR %.2f | TP2: INR %.2f",
                trade_levels["entry"],
                trade_levels["stop_loss"],
                trade_levels["tp1_with_tax"],
                trade_levels["tp2_with_tax"],
            )
            logger.info("R:R = %s", trade_levels["risk_reward_1"])

            trade = await open_paper_trade(
                pair=pair,
                decision=decision,
                signals=signals,
                trade_levels=trade_levels,
                signal_scores=scores,
                sentiment=sentiment,
            )

            if trade:
                logger.info(
                    "Trade opened. ID: %s | Position: INR %.2f | Qty: %.6f",
                    trade.get("trade_id"),
                    trade.get("position_inr", 0),
                    trade.get("quantity", 0),
                )

            await log_agent_cycle(pair, "BUY", signals, sentiment, decision, current_price)
            return

        skip_reason = decision.get("skip_reason", f"Action={action}, Confidence={confidence}%")
        logger.info("Hold for %s: %s", pair, skip_reason)
        await log_agent_cycle(pair, "HOLD", signals, sentiment, decision, current_price, skip_reason)
    except Exception as exc:
        logger.error("Error analyzing %s: %s", pair, exc, exc_info=True)
        await log_agent_cycle(pair, "SKIPPED", {}, sentiment, {}, current_price, str(exc))


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
    )
    scheduler.add_job(
        monitor_positions,
        trigger=IntervalTrigger(minutes=15),
        id="position_monitor",
        name="Position Monitor",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        update_performance,
        trigger=IntervalTrigger(hours=6),
        id="performance_update",
        name="Performance Recalculator",
        replace_existing=True,
    )

    scheduler.start()
    agent_running = True
    logger.info("Scheduler started")
    logger.info("Trading cycle: every %s minutes", settings.trade_interval_minutes)
    logger.info("Ranked scan: top %s tradable pairs per cycle", settings.scan_top_n)
    logger.info("Core scan pairs: %s", settings.core_trading_pairs)
    logger.info("Position monitor: every 15 minutes")
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
