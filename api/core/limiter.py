from slowapi import Limiter
from slowapi.util import get_remote_address

from api.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.CELERY_BROKER_URL,
    default_limits=["200 per day", "50 per hour"],
)
