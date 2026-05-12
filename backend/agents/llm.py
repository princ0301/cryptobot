import json
import logging
from typing import Any

from groq import Groq

from config import settings

logger = logging.getLogger(__name__)

def _load_groq_api_keys() -> list[str]:
    keys = [
        settings.groq_api_key_1.strip(),
        settings.groq_api_key_2.strip(),
        settings.groq_api_key.strip(),
    ]
    unique_keys = []
    for key in keys:
        if key and key not in unique_keys:
            unique_keys.append(key)
    return unique_keys


GROQ_API_KEYS = _load_groq_api_keys()
GROQ_CLIENTS = [Groq(api_key=key) for key in GROQ_API_KEYS]
_active_groq_client_index = 0

SYSTEM_PROMPT_TEMPLATE = """You are an expert crypto trading agent specializing in INR markets on CoinDCX India.

Your job is to analyze market data and make precise trading decisions.

STRICT RULES:
1. Only respond in valid JSON with no markdown or extra text.
2. Only recommend BUY when confidence >= {min_confidence_threshold}.
3. Never recommend BUY in a downtrend unless RSI is extremely oversold (<25).
4. Always consider the risk:reward ratio. Minimum 1:2 is required.
5. If signals conflict or are unclear, respond with HOLD.
6. Account for 30% Indian tax on profits in your reasoning.
7. Be conservative. Missing a trade is better than taking a bad trade.
8. Treat weak volume and cautionary news as risk penalties, not automatic blocks.
9. Treat effective hard volume veto or explicit trading pause as strong blockers.
10. When trend is uptrend, MACD is bullish, total score is strong, RSI is not extreme, and volume is weak but not vetoed, you may still recommend BUY if risk:reward remains favorable.
11. Do not downgrade an otherwise strong setup to HOLD only because volume is weak when effective hard volume veto is false.
12. If a raw hard volume veto exists but Volume Override Candidate is true, treat that as a severe caution rather than an automatic rejection.

Respond with this exact JSON structure:
{{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": <number 0-100>,
  "reasoning": "<plain English explanation, 2-3 sentences>",
  "key_signals": ["<signal1>", "<signal2>", "<signal3>"],
  "risk_assessment": "low" | "medium" | "high",
  "skip_reason": "<only if HOLD, explain why>"
}}"""


def _coerce_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content).strip()


def _parse_json_payload(raw: str) -> dict:
    if not raw:
        raise json.JSONDecodeError("Empty response", raw, 0)

    normalized = raw.strip()
    if normalized.startswith("```"):
        normalized = normalized.strip("`").strip()
        if normalized.lower().startswith("json"):
            normalized = normalized[4:].strip()

    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        start = normalized.find("{")
        end = normalized.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(normalized[start : end + 1])
        raise


def _is_groq_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = [
        "rate limit",
        "rate_limit",
        "too many requests",
        "quota",
        "token",
        "tokens per min",
        "request too large",
        "context length",
        "exceeded",
        "429",
    ]
    return any(marker in text for marker in markers)


def _next_client_index(index: int) -> int:
    if not GROQ_CLIENTS:
        return 0
    return (index + 1) % len(GROQ_CLIENTS)


def _fallback_decision(signals: dict, signal_scores: dict, sentiment: dict) -> dict:
    total = int(signal_scores.get("total", 0))
    trend = signals.get("trend", "unknown")
    rsi = float(signals.get("rsi", 50))
    macd_state = signals.get("macd_crossover", "none")
    volume_veto = bool(signal_scores.get("volume_veto"))
    raw_volume_veto = bool(signal_scores.get("raw_volume_veto", volume_veto))
    volume_override_candidate = bool(signal_scores.get("volume_override_candidate", False))
    weak_volume = bool(signal_scores.get("weak_volume"))
    pause_trading = bool(sentiment.get("pause_trading"))
    news_risk = sentiment.get("news_risk_level", "normal")
    bullish_macd = macd_state in {"bullish", "bullish_continuation"}

    if (
        trend == "uptrend"
        and bullish_macd
        and total >= 68
        and rsi <= 68
        and (not volume_veto or volume_override_candidate)
        and not pause_trading
    ):
        confidence = 72 if not weak_volume else 66
        return {
            "action": "BUY",
            "confidence": confidence,
            "reasoning": "Fallback rules found a strong uptrend setup with supportive momentum and acceptable risk.",
            "key_signals": ["uptrend", "bullish MACD", f"score {total}/90"],
            "risk_assessment": "medium" if weak_volume or news_risk == "caution" else "low",
        }

    reasons = []
    if trend != "uptrend":
        reasons.append("trend not favorable")
    if not bullish_macd:
        reasons.append("MACD not bullish")
    if rsi > 72:
        reasons.append("RSI overbought")
    if volume_veto:
        reasons.append("hard volume veto")
    elif raw_volume_veto and volume_override_candidate:
        reasons.append("raw volume veto softened by strong setup")
    if pause_trading:
        reasons.append("trading pause active")
    if total < settings.min_confidence_threshold:
        reasons.append("signal score below confidence threshold")
    if not reasons:
        reasons.append("setup not strong enough on fallback rules")

    return {
        "action": "HOLD",
        "confidence": 40 if rsi > 72 or volume_veto else 58,
        "reasoning": "Fallback rules did not find a sufficiently strong or safe long setup.",
        "key_signals": [trend, macd_state, f"score {total}/90"],
        "risk_assessment": "high" if volume_veto or pause_trading else "medium",
        "skip_reason": ", ".join(reasons),
    }


async def get_trading_decision(
    pair: str,
    signals: dict,
    signal_scores: dict,
    sentiment: dict,
    portfolio: dict,
) -> dict:
    global _active_groq_client_index

    min_confidence = settings.min_confidence_threshold
    total_score = signal_scores.get("total", 0)
    volume_veto = signal_scores.get("volume_veto", False)
    raw_volume_veto = signal_scores.get("raw_volume_veto", volume_veto)
    volume_override_candidate = signal_scores.get("volume_override_candidate", False)
    weak_volume = signal_scores.get("weak_volume", False)
    bullish_macd = signals.get("macd_crossover") in {"bullish", "bullish_continuation"}
    rsi_value = float(signals.get("rsi", 50))
    favorable_setup = (
        signals.get("trend") == "uptrend"
        and bullish_macd
        and total_score >= 68
        and rsi_value <= 68
        and (not volume_veto or volume_override_candidate)
    )
    caution_setup = (
        signals.get("trend") == "uptrend"
        and bullish_macd
        and total_score >= 60
        and (not volume_veto or volume_override_candidate)
    )

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        min_confidence_threshold=f"{min_confidence:.0f}%"
    )

    user_message = f"""
PAIR: {pair}
PRICE: INR {signals.get('price', 0):,.2f}

TECHNICALS
- Trend: {signals.get('trend', 'unknown')}
- EMA50/EMA200: {signals.get('ema_50', 0):,.2f} / {signals.get('ema_200', 0):,.2f}
- Price vs EMA50: {signals.get('price_vs_ema50', 'unknown')}
- RSI: {signals.get('rsi', 50)} ({signals.get('rsi_zone', 'neutral')})
- MACD: {signals.get('macd_crossover', 'none')} | Hist {signals.get('macd_histogram', 0):.4f}
- ATR: INR {signals.get('atr', 0):,.2f} ({signals.get('atr_pct', 0):.2f}%)
- Volume ratio: {signals.get('volume_ratio', 1):.2f}x ({signals.get('volume_signal', 'average')})
- Support/Resistance distance: {signals.get('dist_support_pct', 0):.2f}% / {signals.get('dist_resistance_pct', 0):.2f}%

SCORES
- Total: {signal_scores.get('total', 0)}/90
- EMA/RSI/MACD/Volume/SR: {signal_scores.get('breakdown', {}).get('ema', 0)}/{signal_scores.get('breakdown', {}).get('rsi', 0)}/{signal_scores.get('breakdown', {}).get('macd', 0)}/{signal_scores.get('breakdown', {}).get('volume', 0)}/{signal_scores.get('breakdown', {}).get('support_resistance', 0)}
- Weak volume: {signal_scores.get('weak_volume', False)}
- Raw veto: {raw_volume_veto}
- Effective veto: {volume_veto}
- Volume override candidate: {volume_override_candidate}
- High volatility: {signal_scores.get('high_volatility', False)}
- Favorable setup: {favorable_setup}
- Caution setup: {caution_setup}

SENTIMENT
- Combined: {sentiment.get('combined_score', 50)}/100 ({sentiment.get('sentiment_label', 'Neutral')})
- Fear & Greed: {sentiment.get('fear_greed', {}).get('score', 50)} ({sentiment.get('fear_greed', {}).get('label', 'Neutral')})
- BTC dominance: {sentiment.get('btc_dominance', {}).get('btc_dominance', 50):.1f}% ({sentiment.get('btc_dominance', {}).get('signal', 'balanced')})
- News risk: {sentiment.get('news_risk_level', 'normal')}
- Trading pause: {sentiment.get('pause_trading', False)}

PORTFOLIO
- Cash: INR {portfolio.get('inr_balance', 100000):,.2f}
- Open positions: {portfolio.get('open_positions', 0)}
- Total value: INR {portfolio.get('total_value', 100000):,.2f}

CONSTRAINTS
- Minimum confidence: {min_confidence:.0f}%
- Risk per trade: INR {portfolio.get('inr_balance', 100000) * 0.02:,.0f}
- Maximum position: INR {portfolio.get('inr_balance', 100000) * 0.25:,.0f}
- Minimum risk:reward: 1:2
- 30% Indian tax on profits
    """.strip()

    try:
        if not GROQ_CLIENTS:
            raise RuntimeError("No Groq API keys configured")

        response = None
        last_exc = None
        attempted = 0
        client_index = _active_groq_client_index
        max_attempts = min(2, len(GROQ_CLIENTS))

        while attempted < max_attempts:
            client = GROQ_CLIENTS[client_index]
            try:
                response = client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=220,
                    temperature=0.1,
                )
                _active_groq_client_index = client_index
                break
            except Exception as exc:
                last_exc = exc
                if _is_groq_limit_error(exc) and len(GROQ_CLIENTS) > 1 and attempted + 1 < max_attempts:
                    next_index = _next_client_index(client_index)
                    logger.warning(
                        "Groq limit reached on key #%s for %s, switching to key #%s",
                        client_index + 1,
                        pair,
                        next_index + 1,
                    )
                    client_index = next_index
                    _active_groq_client_index = next_index
                    attempted += 1
                    continue
                raise

        if response is None:
            raise last_exc or RuntimeError("Groq request failed without response")

        raw = _coerce_content_to_text(response.choices[0].message.content)
        logger.debug("Groq raw response for %s: %s", pair, raw)

        decision = _parse_json_payload(raw)
        for field in ("action", "confidence", "reasoning"):
            if field not in decision:
                raise ValueError(f"Missing field in Groq response: {field}")

        if decision["action"] == "BUY" and decision["confidence"] < min_confidence:
            decision["action"] = "HOLD"
            decision["skip_reason"] = (
                f"Groq confidence {decision['confidence']}% below threshold {min_confidence:.0f}%"
            )

        if signal_scores.get("volume_veto") and decision["action"] == "BUY":
            decision["action"] = "HOLD"
            decision["skip_reason"] = "Effective hard volume veto: trading volume is too weak"

        if sentiment.get("pause_trading") and decision["action"] == "BUY":
            decision["action"] = "HOLD"
            decision["skip_reason"] = "High-risk news detected, pausing new entries"

        logger.debug("Decision for %s: %s (%s%%)", pair, decision["action"], decision.get("confidence", 0))
        return decision
    except json.JSONDecodeError as exc:
        logger.error("Groq returned invalid JSON for %s: %s", pair, exc)
        return _fallback_decision(signals, signal_scores, sentiment)
    except Exception as exc:
        logger.error("Groq API error for %s: %s", pair, exc)
        return _fallback_decision(signals, signal_scores, sentiment)
