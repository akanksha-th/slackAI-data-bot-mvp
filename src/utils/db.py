from sqlalchemy import create_engine, text
from src.core.config import get_settings
from src.core.logging import get_logger
from sqlalchemy.pool import QueuePool
from typing import Any

logger = get_logger(__name__)
settings = get_settings()

DATABASE_URL = (
    f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)

def execute_query(sql: str) -> list[dict[str, Any]]:
    logger.info(f"Executing SQL: {sql}")
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchall()
        columns = result.keys()
        data = [dict(zip(columns, row)) for row in rows]
        logger.info(f"Query returned {len(data)} rows")
        return data