import json
from pathlib import Path


COINS_FILE = Path(__file__).resolve().parent / "coins.json"

DEFAULT_PAIRS = [
    {
        "symbol": "BTCINR",
        "display": "BTC/INR",
        "candle_pair": "I-BTC_INR",
        "watched": True,
        "tradable": True,
    },
    {
        "symbol": "ETHINR",
        "display": "ETH/INR",
        "candle_pair": "I-ETH_INR",
        "watched": True,
        "tradable": True,
    },
    {
        "symbol": "BNBINR",
        "display": "BNB/INR",
        "candle_pair": "I-BNB_INR",
        "watched": True,
        "tradable": True,
    },
]


def _normalize_pair(pair: dict, *, default_tradable: bool = True) -> dict[str, str | bool]:
    symbol = str(pair.get("symbol", "")).upper().strip()
    display = str(pair.get("display", "")).strip()
    candle_pair = str(pair.get("candle_pair", "")).strip()
    watched = bool(pair.get("watched", True))
    tradable = bool(pair.get("tradable", default_tradable))

    if not watched:
        tradable = False

    return {
        "symbol": symbol,
        "display": display,
        "candle_pair": candle_pair,
        "watched": watched,
        "tradable": tradable,
    }


def load_coin_pairs() -> list[dict[str, str | bool]]:
    try:
        payload = json.loads(COINS_FILE.read_text(encoding="utf-8"))
        pairs = payload.get("pairs", [])
        cleaned = []
        for pair in pairs:
            normalized = _normalize_pair(pair, default_tradable=True)
            if normalized["symbol"] and normalized["display"] and normalized["candle_pair"]:
                cleaned.append(normalized)
        return cleaned or DEFAULT_PAIRS.copy()
    except Exception:
        return DEFAULT_PAIRS.copy()


def load_trading_pairs() -> list[str]:
    return [pair["symbol"] for pair in load_coin_pairs() if pair.get("tradable")]


def load_watched_pairs() -> list[str]:
    return [pair["symbol"] for pair in load_coin_pairs() if pair.get("watched")]


def load_pair_map() -> dict[str, dict[str, str]]:
    return {
        pair["symbol"]: {
            "display": pair["display"],
            "candle_pair": pair["candle_pair"],
        }
        for pair in load_coin_pairs()
        if pair.get("watched")
    }


def save_coin_pairs(pairs: list[dict[str, str | bool]]) -> list[dict[str, str | bool]]:
    normalized = [
        _normalize_pair(pair, default_tradable=False)
        for pair in pairs
        if pair.get("symbol") and pair.get("display") and pair.get("candle_pair")
    ]
    COINS_FILE.write_text(
        json.dumps({"pairs": normalized}, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized
