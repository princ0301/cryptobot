import logging
from typing import Optional

import pandas as pd
import pandas_ta as _pandas_ta

from agents.risk_manager import calculate_tax_adjusted_targets
from config import settings

logger = logging.getLogger(__name__)


def calculate_indicators(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    if df is None or df.empty:
        logger.error("Empty dataframe passed to calculate_indicators")
        return None

    if len(df) < 50:
        logger.warning("Only %s candles available, need at least 50 for reliable signals", len(df))
        return None

    try:
        enriched = df.copy()
        enriched.ta.ema(length=50, append=True)
        enriched.ta.ema(length=200, append=True)
        enriched.ta.rsi(length=14, append=True)
        enriched.ta.macd(fast=12, slow=26, signal=9, append=True)
        enriched.ta.atr(length=14, append=True)
        enriched.ta.bbands(length=20, std=2, append=True)

        enriched["volume_ma30"] = enriched["volume"].rolling(window=30).mean()
        enriched["volume_ratio"] = enriched["volume"] / enriched["volume_ma30"]

        logger.debug("Indicators calculated on %s candles", len(enriched))
        return enriched
    except Exception as exc:
        logger.error("Error calculating indicators: %s", exc)
        return None


def _first_available(row: pd.Series, *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return float(value or 0)
    return default


def get_latest_signals(df: pd.DataFrame) -> Optional[dict]:
    if df is None or df.empty:
        return None

    try:
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last

        price = float(last["close"])
        ema50 = _first_available(last, "EMA_50")
        ema200 = _first_available(last, "EMA_200")
        rsi = _first_available(last, "RSI_14", default=50)
        macd = _first_available(last, "MACD_12_26_9")
        macd_signal = _first_available(last, "MACDs_12_26_9")
        macd_hist = _first_available(last, "MACDh_12_26_9")
        prev_macd = _first_available(prev, "MACD_12_26_9")
        prev_signal = _first_available(prev, "MACDs_12_26_9")
        atr = _first_available(last, "ATR_14", "ATRr_14")
        volume = float(last["volume"])
        volume_ratio = _first_available(last, "volume_ratio", default=1)
        bb_upper = _first_available(last, "BBU_20_2.0")
        bb_lower = _first_available(last, "BBL_20_2.0")
        bb_mid = _first_available(last, "BBM_20_2.0")

        trend = "uptrend" if ema50 > ema200 else "downtrend"
        price_vs_ema50 = "above" if price > ema50 else "below"

        if prev_macd < prev_signal and macd > macd_signal:
            macd_crossover = "bullish"
        elif prev_macd > prev_signal and macd < macd_signal:
            macd_crossover = "bearish"
        elif macd > macd_signal:
            macd_crossover = "bullish_continuation"
        else:
            macd_crossover = "bearish_continuation"

        if rsi <= 30:
            rsi_zone = "oversold"
        elif rsi <= 45:
            rsi_zone = "bearish_neutral"
        elif rsi <= 55:
            rsi_zone = "neutral"
        elif rsi <= 70:
            rsi_zone = "bullish_neutral"
        else:
            rsi_zone = "overbought"

        if volume_ratio >= 1.3:
            volume_signal = "above_average"
        elif volume_ratio >= settings.min_volume_ratio_soft:
            volume_signal = "average"
        else:
            volume_signal = "below_average"

        if price >= bb_upper * 0.98:
            bb_position = "upper"
        elif price <= bb_lower * 1.02:
            bb_position = "lower"
        else:
            bb_position = "middle"

        recent = df.tail(20)
        support = float(recent["low"].min())
        resistance = float(recent["high"].max())
        dist_support = ((price - support) / price) * 100
        dist_resistance = ((resistance - price) / price) * 100

        return {
            "price": price,
            "ema_50": round(ema50, 2),
            "ema_200": round(ema200, 2),
            "trend": trend,
            "price_vs_ema50": price_vs_ema50,
            "ema_gap_pct": round(((ema50 - ema200) / ema200) * 100, 2) if ema200 else 0,
            "rsi": round(rsi, 2),
            "rsi_zone": rsi_zone,
            "macd": round(macd, 4),
            "macd_signal": round(macd_signal, 4),
            "macd_histogram": round(macd_hist, 4),
            "macd_crossover": macd_crossover,
            "atr": round(atr, 2),
            "atr_pct": round((atr / price) * 100, 3) if price else 0,
            "volume": round(volume, 4),
            "volume_ratio": round(volume_ratio, 2),
            "volume_signal": volume_signal,
            "bb_upper": round(bb_upper, 2),
            "bb_lower": round(bb_lower, 2),
            "bb_mid": round(bb_mid, 2),
            "bb_position": bb_position,
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "dist_support_pct": round(dist_support, 2),
            "dist_resistance_pct": round(dist_resistance, 2),
        }
    except Exception as exc:
        logger.error("Error extracting signals: %s", exc)
        return None


def score_signals(signals: dict) -> dict:
    if not signals:
        return {
            "total": 0,
            "tradeable": False,
            "volume_veto": True,
            "raw_volume_veto": True,
            "volume_override_candidate": False,
            "weak_volume": True,
            "high_volatility": False,
            "atr_pct": 0,
            "breakdown": {
                "ema": 0,
                "rsi": 0,
                "macd": 0,
                "volume": 0,
                "support_resistance": 0,
            },
        }

    ema_score = 0
    if signals.get("trend") == "uptrend":
        ema_score += 15
    if signals.get("price_vs_ema50") == "above":
        ema_score += 10

    rsi = float(signals.get("rsi", 50))
    if 45 <= rsi <= 65:
        rsi_score = 25
    elif 35 <= rsi < 45 or 65 < rsi <= 72:
        rsi_score = 18
    elif 25 <= rsi < 35 or 72 < rsi <= 80:
        rsi_score = 8
    else:
        rsi_score = 0

    macd_state = signals.get("macd_crossover", "none")
    macd_score = {
        "bullish": 20,
        "bullish_continuation": 16,
        "none": 8,
        "bearish_continuation": 4,
        "bearish": 0,
    }.get(macd_state, 0)

    volume_ratio = float(signals.get("volume_ratio", 1))
    if volume_ratio >= 1.5:
        volume_score = 10
    elif volume_ratio >= 1.1:
        volume_score = 7
    elif volume_ratio >= settings.min_volume_ratio_soft:
        volume_score = 4
    elif volume_ratio >= settings.min_volume_ratio_hard:
        volume_score = 2
    else:
        volume_score = 0

    dist_support = float(signals.get("dist_support_pct", 0))
    dist_resistance = float(signals.get("dist_resistance_pct", 0))
    if dist_support <= 2 and dist_resistance >= 4:
        support_resistance_score = 10
    elif dist_support <= 3 and dist_resistance >= 3:
        support_resistance_score = 7
    elif dist_resistance >= 2:
        support_resistance_score = 4
    else:
        support_resistance_score = 0

    atr_pct = float(signals.get("atr_pct", 0))
    weak_volume = volume_ratio < settings.min_volume_ratio_soft
    raw_volume_veto = volume_ratio < settings.min_volume_ratio_hard
    high_volatility = atr_pct >= 4.5

    total = ema_score + rsi_score + macd_score + volume_score + support_resistance_score
    volume_override_candidate = (
        raw_volume_veto
        and signals.get("trend") == "uptrend"
        and macd_state in {"bullish", "bullish_continuation"}
        and 45 <= rsi <= 68
        and total >= 70
    )
    volume_veto = raw_volume_veto and not volume_override_candidate
    tradeable = (
        total >= 55
        and signals.get("trend") == "uptrend"
        and macd_state in {"bullish", "bullish_continuation"}
        and not volume_veto
    )

    return {
        "total": total,
        "tradeable": tradeable,
        "volume_veto": volume_veto,
        "raw_volume_veto": raw_volume_veto,
        "volume_override_candidate": volume_override_candidate,
        "weak_volume": weak_volume,
        "high_volatility": high_volatility,
        "atr_pct": atr_pct,
        "breakdown": {
            "ema": ema_score,
            "rsi": rsi_score,
            "macd": macd_score,
            "volume": volume_score,
            "support_resistance": support_resistance_score,
        },
    }


def calculate_trade_levels(signals: dict, confidence: float) -> dict:
    price = float(signals.get("price", 0))
    atr = max(float(signals.get("atr", 0)), price * 0.01)
    support = float(signals.get("support", price - atr))
    resistance = float(signals.get("resistance", price + (atr * 2)))

    entry = price
    stop_loss = min(price - (atr * 1.2), support * 0.995)
    if stop_loss >= entry:
        stop_loss = entry - (atr * 1.2)

    risk_per_unit = max(entry - stop_loss, price * 0.005)
    confidence_boost = max(0.0, min((confidence - 65) / 35, 1.0))
    tp1 = max(entry + (risk_per_unit * (2.0 + 0.25 * confidence_boost)), resistance * 0.995)
    tp2 = max(entry + (risk_per_unit * (3.0 + 0.5 * confidence_boost)), resistance * 1.015)

    tax_targets = calculate_tax_adjusted_targets(entry, tp1, tp2)
    risk_reward_1 = (tax_targets["tp1_tax_adjusted"] - entry) / risk_per_unit if risk_per_unit else 0
    risk_reward_2 = (tax_targets["tp2_tax_adjusted"] - entry) / risk_per_unit if risk_per_unit else 0

    return {
        "entry": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "tp1_with_tax": round(tax_targets["tp1_tax_adjusted"], 2),
        "tp2_with_tax": round(tax_targets["tp2_tax_adjusted"], 2),
        "tds_tp1": tax_targets["tds_tp1"],
        "tds_tp2": tax_targets["tds_tp2"],
        "risk_per_unit": round(risk_per_unit, 2),
        "risk_reward_1": f"1:{risk_reward_1:.2f}",
        "risk_reward_2": f"1:{risk_reward_2:.2f}",
    }
