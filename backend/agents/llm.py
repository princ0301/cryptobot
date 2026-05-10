import json
import logging

from groq import Groq

from config import settings

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.groq_api_key)

SYSTEM_PROMPT = """You are an expert crypto trading agent specializing in INR markets on CoinDCX India.

Your job is to analyze market data and make precise trading decisions.

STRICT RULES:
1. Only respond in valid JSON with no markdown or extra text.
2. Only recommend BUY when confidence >= 65.
3. Never recommend BUY in a downtrend unless RSI is extremely oversold (<25).
4. Always consider the risk:reward ratio. Minimum 1:2 is required.
5. If signals conflict or are unclear, respond with HOLD.
6. Account for 30% Indian tax on profits in your reasoning.
7. Be conservative. Missing a trade is better than taking a bad trade.

Respond with this exact JSON structure:
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": <number 0-100>,
  "reasoning": "<plain English explanation, 2-3 sentences>",
  "key_signals": ["<signal1>", "<signal2>", "<signal3>"],
  "risk_assessment": "low" | "medium" | "high",
  "skip_reason": "<only if HOLD, explain why>"
}"""


async def get_trading_decision(
    pair: str,
    signals: dict,
    signal_scores: dict,
    sentiment: dict,
    portfolio: dict,
) -> dict:
    user_message = f"""
Analyze this market data and make a trading decision:

PAIR: {pair}
CURRENT PRICE: INR {signals.get('price', 0):,.2f}

TECHNICAL INDICATORS
Trend: {signals.get('trend', 'unknown')} (50 EMA: INR {signals.get('ema_50', 0):,.2f} | 200 EMA: INR {signals.get('ema_200', 0):,.2f})
Price vs EMA50: {signals.get('price_vs_ema50', 'unknown')}
RSI (14): {signals.get('rsi', 50)} -> Zone: {signals.get('rsi_zone', 'neutral')}
MACD: {signals.get('macd_crossover', 'none')} (Histogram: {signals.get('macd_histogram', 0):.4f})
ATR: INR {signals.get('atr', 0):,.2f} ({signals.get('atr_pct', 0):.2f}% of price)
Volume: {signals.get('volume_ratio', 1):.2f}x average -> {signals.get('volume_signal', 'average')}
Bollinger Band Position: {signals.get('bb_position', 'middle')}
Support: INR {signals.get('support', 0):,.2f} ({signals.get('dist_support_pct', 0):.2f}% away)
Resistance: INR {signals.get('resistance', 0):,.2f} ({signals.get('dist_resistance_pct', 0):.2f}% away)

SIGNAL SCORES
EMA Score: {signal_scores.get('breakdown', {}).get('ema', 0)}/25
RSI Score: {signal_scores.get('breakdown', {}).get('rsi', 0)}/25
MACD Score: {signal_scores.get('breakdown', {}).get('macd', 0)}/20
Volume Score: {signal_scores.get('breakdown', {}).get('volume', 0)}/10
Support/Resistance Score: {signal_scores.get('breakdown', {}).get('support_resistance', 0)}/10
TOTAL SCORE: {signal_scores.get('total', 0)}/90
Volume Veto Active: {signal_scores.get('volume_veto', False)}
High Volatility: {signal_scores.get('high_volatility', False)} (ATR {signal_scores.get('atr_pct', 0):.2f}%)

MARKET SENTIMENT
Combined Sentiment Score: {sentiment.get('combined_score', 50)}/100 -> {sentiment.get('sentiment_label', 'Neutral')}
Fear & Greed: {sentiment.get('fear_greed', {}).get('score', 50)} ({sentiment.get('fear_greed', {}).get('label', 'Neutral')})
BTC Dominance: {sentiment.get('btc_dominance', {}).get('btc_dominance', 50):.1f}% -> {sentiment.get('btc_dominance', {}).get('signal', 'balanced')}
Reddit Mood: {sentiment.get('reddit', {}).get('signal', 'neutral')}
High Risk News Detected: {sentiment.get('pause_trading', False)}

PORTFOLIO
Paper Balance: INR {portfolio.get('inr_balance', 100000):,.2f}
Open Positions: {portfolio.get('open_positions', 0)}
Total Portfolio Value: INR {portfolio.get('total_value', 100000):,.2f}

CONSTRAINTS
- Minimum confidence to trade: 65%
- Risk per trade: 2% of portfolio = INR {portfolio.get('inr_balance', 100000) * 0.02:,.0f}
- Maximum position: 25% = INR {portfolio.get('inr_balance', 100000) * 0.25:,.0f}
- Minimum Risk:Reward ratio: 1:2
- Tax: 30% on profits (already factored into TP levels)
""".strip()

    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=400,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()
        logger.info("Groq raw response for %s: %s", pair, raw)

        decision = json.loads(raw)
        for field in ("action", "confidence", "reasoning"):
            if field not in decision:
                raise ValueError(f"Missing field in Groq response: {field}")

        if decision["action"] == "BUY" and decision["confidence"] < 65:
            decision["action"] = "HOLD"
            decision["skip_reason"] = f"Groq confidence {decision['confidence']}% below threshold 65%"

        if signal_scores.get("volume_veto") and decision["action"] == "BUY":
            decision["action"] = "HOLD"
            decision["skip_reason"] = "Volume veto: trading volume is below average"

        if sentiment.get("pause_trading") and decision["action"] == "BUY":
            decision["action"] = "HOLD"
            decision["skip_reason"] = "High-risk news detected, pausing new entries"

        logger.info("Decision for %s: %s (%s%%)", pair, decision["action"], decision.get("confidence", 0))
        return decision
    except json.JSONDecodeError as exc:
        logger.error("Groq returned invalid JSON for %s: %s", pair, exc)
        return {
            "action": "HOLD",
            "confidence": 0,
            "reasoning": "AI response parsing error, skipping trade to stay safe.",
            "skip_reason": "JSON parse error",
            "risk_assessment": "high",
        }
    except Exception as exc:
        logger.error("Groq API error for %s: %s", pair, exc)
        return {
            "action": "HOLD",
            "confidence": 0,
            "reasoning": f"AI unavailable: {exc}",
            "skip_reason": "Groq API error",
            "risk_assessment": "high",
        }
