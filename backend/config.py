from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from data.coin_registry import load_trading_pairs


class Settings(BaseSettings):
    coindcx_api_key: str = ""
    coindcx_api_secret: str = ""

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    groq_api_key: str = ""
    groq_api_key_1: str = ""
    groq_api_key_2: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    gcp_project_id: str = ""
    gcp_location: str = "asia-south1"
    google_application_credentials: str = "./gcp-service-account.json"

    paper_starting_balance: float = 100000.0
    risk_per_trade_percent: float = 2.0
    max_position_percent: float = 25.0
    max_open_positions: int = 5
    coin_reentry_cooldown_minutes: int = 180
    min_confidence_threshold: float = 65.0
    trade_interval_minutes: int = 60
    position_monitor_interval_minutes: int = 5
    scan_top_n: int = 8
    startup_scan_enabled: bool = True
    startup_trade_enabled: bool = False
    min_volume_ratio_soft: float = 0.8
    min_volume_ratio_hard: float = 0.55
    reddit_high_risk_min_hits: int = 2
    reddit_high_risk_min_ratio: float = 0.15
    sentiment_pause_max_fg: int = 40
    stop_loss_atr_multiplier: float = 1.5
    structure_stop_buffer_percent: float = 0.5
    min_stop_distance_percent: float = 0.5
    max_stop_distance_percent: float = 3.5
    tp1_r_multiple: float = 0.8
    tp2_r_multiple: float = 1.4
    partial_take_profit_fraction: float = 0.6
    profit_lock_trigger_r_multiple: float = 0.5
    profit_lock_buffer_r_multiple: float = 0.1
    trailing_stop_trigger_r_multiple: float = 1.0
    trailing_stop_distance_r_multiple: float = 0.5

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
    core_trading_pairs: list[str] = ["BTCINR", "ETHINR", "SOLINR"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
