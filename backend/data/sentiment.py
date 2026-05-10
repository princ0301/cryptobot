import logging

import feedparser
import httpx

logger = logging.getLogger(__name__)

BULLISH_KEYWORDS = [
    "bullish",
    "surge",
    "rally",
    "breakout",
    "ath",
    "moon",
    "pump",
    "buy",
    "adoption",
    "institutional",
    "upgrade",
    "partnership",
    "launch",
    "record",
    "soar",
    "gain",
    "rise",
]
BEARISH_KEYWORDS = [
    "crash",
    "dump",
    "bearish",
    "ban",
    "hack",
    "scam",
    "sell",
    "regulation",
    "sec",
    "lawsuit",
    "fraud",
    "collapse",
    "warning",
    "fear",
    "panic",
    "drop",
    "plunge",
    "lose",
]
HIGH_RISK_KEYWORDS = [
    "ban",
    "hack",
    "scam",
    "fraud",
    "collapse",
    "emergency",
    "seized",
    "arrested",
    "shutdown",
    "illegal",
]


async def get_fear_greed() -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://api.alternative.me/fng/?limit=1")
            response.raise_for_status()
            data = response.json()

        fear_greed = data["data"][0]
        score = int(fear_greed["value"])
        label = fear_greed["value_classification"]

        if score <= 25:
            signal = "extreme_fear"
            trade_hint = "Contrarian buy opportunity because the market looks oversold"
        elif score <= 45:
            signal = "fear"
            trade_hint = "Stay cautious and wait for technical confirmation"
        elif score <= 55:
            signal = "neutral"
            trade_hint = "Let the technical setup lead the trade"
        elif score <= 75:
            signal = "greed"
            trade_hint = "Trend is supportive, but watch for reversal risk"
        else:
            signal = "extreme_greed"
            trade_hint = "Reduce size and avoid chasing overheated moves"

        return {
            "score": score,
            "label": label,
            "signal": signal,
            "trade_hint": trade_hint,
            "source": "alternative.me",
        }
    except Exception as exc:
        logger.error("Fear & Greed API error: %s", exc)
        return {
            "score": 50,
            "label": "Neutral",
            "signal": "neutral",
            "trade_hint": "API unavailable",
            "source": "default",
        }


async def get_btc_dominance() -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://api.coingecko.com/api/v3/global")
            response.raise_for_status()
            data = response.json()

        dominance = data["data"]["market_cap_percentage"]
        btc_dom = round(dominance.get("btc", 50), 2)
        eth_dom = round(dominance.get("eth", 15), 2)
        total_cap = data["data"].get("total_market_cap", {}).get("usd", 0)
        cap_change = data["data"].get("market_cap_change_percentage_24h_usd", 0)

        if btc_dom > 55:
            signal = "btc_dominant"
            trade_hint = "Favor BTC, altcoins may lag"
        elif btc_dom < 45:
            signal = "altcoin_season"
            trade_hint = "Altcoins may have stronger upside than BTC"
        else:
            signal = "balanced"
            trade_hint = "Market leadership is balanced across majors"

        return {
            "btc_dominance": btc_dom,
            "eth_dominance": eth_dom,
            "signal": signal,
            "trade_hint": trade_hint,
            "total_market_cap_usd": total_cap,
            "market_cap_change_24h": round(cap_change, 2),
            "source": "coingecko",
        }
    except Exception as exc:
        logger.error("CoinGecko API error: %s", exc)
        return {
            "btc_dominance": 50,
            "signal": "balanced",
            "trade_hint": "API unavailable",
            "source": "default",
        }


async def get_reddit_sentiment() -> dict:
    feeds = [
        "https://www.reddit.com/r/Bitcoin/.rss",
        "https://www.reddit.com/r/CryptoCurrency/.rss",
        "https://www.reddit.com/r/ethereum/.rss",
    ]

    bullish_count = 0
    bearish_count = 0
    high_risk = False
    total_posts = 0

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                total_posts += 1

                if any(keyword in title for keyword in BULLISH_KEYWORDS):
                    bullish_count += 1
                if any(keyword in title for keyword in BEARISH_KEYWORDS):
                    bearish_count += 1
                if any(keyword in title for keyword in HIGH_RISK_KEYWORDS):
                    high_risk = True
        except Exception as exc:
            logger.warning("RSS parse error for %s: %s", feed_url, exc)

    if total_posts == 0:
        return {
            "signal": "neutral",
            "score": 50,
            "high_risk_news": False,
            "source": "reddit_rss",
        }

    bull_pct = (bullish_count / total_posts) * 100
    bear_pct = (bearish_count / total_posts) * 100

    if bull_pct > 60:
        signal = "euphoric"
        score = 30
    elif bull_pct > bear_pct * 2:
        signal = "bullish"
        score = 65
    elif bear_pct > bull_pct * 2:
        signal = "bearish"
        score = 70
    elif bear_pct > 60:
        signal = "panic"
        score = 80
    else:
        signal = "neutral"
        score = 50

    return {
        "signal": signal,
        "score": score,
        "bullish_posts": bullish_count,
        "bearish_posts": bearish_count,
        "total_posts": total_posts,
        "high_risk_news": high_risk,
        "source": "reddit_rss",
    }


async def get_combined_sentiment() -> dict:
    fear_greed = await get_fear_greed()
    dominance = await get_btc_dominance()
    reddit = await get_reddit_sentiment()

    fg_score = fear_greed["score"]
    reddit_score = reddit["score"]

    if fg_score <= 25:
        fg_opportunity = 85
    elif fg_score <= 40:
        fg_opportunity = 70
    elif fg_score <= 60:
        fg_opportunity = 50
    elif fg_score <= 75:
        fg_opportunity = 35
    else:
        fg_opportunity = 20

    combined = (fg_opportunity * 0.40) + (reddit_score * 0.20) + (50 * 0.40)

    return {
        "combined_score": round(combined, 1),
        "fear_greed": fear_greed,
        "btc_dominance": dominance,
        "reddit": reddit,
        "pause_trading": reddit.get("high_risk_news", False),
        "btc_only_mode": dominance.get("signal") == "btc_dominant",
        "sentiment_label": (
            "Very Bullish Opportunity"
            if combined >= 70
            else "Bullish"
            if combined >= 55
            else "Neutral"
            if combined >= 45
            else "Bearish"
            if combined >= 30
            else "Very Bearish - Caution"
        ),
    }
