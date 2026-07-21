from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings

# Use the same connection string but with the synchronous driver
SYNC_DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)

engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
