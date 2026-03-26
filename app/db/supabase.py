from supabase import create_client, Client
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)

_supabase: Client | None = None


def get_supabase() -> Client:
    """Return Supabase client (uses service_role key - backend only)"""
    global _supabase
    if _supabase is None:
        _supabase = create_client(
            supabase_url=settings.supabase_url,
            supabase_key=settings.supabase_service_role_key,
        )
        logger.info("Supabase client initialized successfully")
    return _supabase