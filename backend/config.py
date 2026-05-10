import json
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


COINS_FILE = Path(__file__).resolve().parent / "data" / "coins.json"


def load_trading_pairs() -> list[str]:
    try:
        payload = json.loads(COINS_FILE.read_text(encoding="utf-8"))
        pairs = payload.get("pairs", [])
        return [pair["symbol"] for pair in pairs if pair.get("symbol")]
    except Exception:
        return ["BTCINR", "ETHINR", "BNBINR"]


class Settings(BaseSettings):
    coindcx_api_key: str = ""
    coindcx_api_secret: str = ""

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    gcp_project_id: str = ""
    gcp_location: str = "asia-south1"
    google_application_credentials: str = "./gcp-service-account.json"

    paper_starting_balance: float = 100000.0
    risk_per_trade_percent: float = 2.0
    max_position_percent: float = 25.0
    min_confidence_threshold: float = 65.0
    trade_interval_minutes: int = 60

    tax_rate_percent: float = 30.0
    tds_rate_percent: float = 1.0

    app_env: str = "development"
    frontend_url: str = "http://localhost:5173"
    backend_port: int = 8000

    min_win_rate: float = 60.0
    min_trades_required: int = 30
    max_drawdown_allowed: float = 15.0
    min_profit_factor: float = 1.5

    trading_pairs: list[str] = load_trading_pairs()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
