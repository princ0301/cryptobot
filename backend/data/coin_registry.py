import json
from pathlib import Path


COINS_FILE = Path(__file__).resolve().parent / "coins.json"

DEFAULT_PAIRS = [
    {"symbol": "BTCINR", "display": "BTC/INR", "candle_pair": "I-BTC_INR"},
    {"symbol": "ETHINR", "display": "ETH/INR", "candle_pair": "I-ETH_INR"},
    {"symbol": "BNBINR", "display": "BNB/INR", "candle_pair": "I-BNB_INR"},
]


def load_coin_pairs() -> list[dict[str, str]]:
    try:
        payload = json.loads(COINS_FILE.read_text(encoding="utf-8"))
        pairs = payload.get("pairs", [])
        cleaned = []
        for pair in pairs:
            symbol = str(pair.get("symbol", "")).upper().strip()
            display = str(pair.get("display", "")).strip()
            candle_pair = str(pair.get("candle_pair", "")).strip()
            if symbol and display and candle_pair:
                cleaned.append(
                    {
                        "symbol": symbol,
                        "display": display,
                        "candle_pair": candle_pair,
                    }
                )
        return cleaned or DEFAULT_PAIRS.copy()
    except Exception:
        return DEFAULT_PAIRS.copy()


def load_trading_pairs() -> list[str]:
    return [pair["symbol"] for pair in load_coin_pairs()]


def load_pair_map() -> dict[str, dict[str, str]]:
    return {
        pair["symbol"]: {
            "display": pair["display"],
            "candle_pair": pair["candle_pair"],
        }
        for pair in load_coin_pairs()
    }


def save_coin_pairs(pairs: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized = [
        {
            "symbol": str(pair["symbol"]).upper().strip(),
            "display": str(pair["display"]).strip(),
            "candle_pair": str(pair["candle_pair"]).strip(),
        }
        for pair in pairs
        if pair.get("symbol") and pair.get("display") and pair.get("candle_pair")
    ]
    COINS_FILE.write_text(
        json.dumps({"pairs": normalized}, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized

