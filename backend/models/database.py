import logging
from typing import Optional

from supabase import Client, create_client

from config import settings

logger = logging.getLogger(__name__)

supabase: Optional[Client] = None


def get_supabase() -> Client:
    if not settings.supabase_url or not settings.supabase_service_key:
        raise RuntimeError("Supabase credentials are not configured")

    return create_client(settings.supabase_url, settings.supabase_service_key)


def get_db() -> Client:
    if supabase is None:
        raise RuntimeError("Supabase client is not initialized")
    return supabase


def init_db() -> bool:
    global supabase

    supabase = get_supabase()
    try:
        supabase.table("paper_portfolio").select("id").limit(1).execute()
        logger.info("Supabase connected successfully")
        return True
    except Exception as exc:
        logger.warning("Supabase connected, but tables are not ready yet: %s", exc)
        return False
