"""
trading_bot.core.database
~~~~~~~~~~~~~~~~~~~~~~~~~~
SQLAlchemy async engine ve session yönetimi.
Tüm ORM modelleri trading_bot.models.db_models'da tanımlanır;
bu modül sadece bağlantı ve tablo oluşturma işlemlerini sağlar.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.logger import get_logger

logger = get_logger(__name__)

# Modül seviyesinde tutulacak singleton nesneler
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db(db_url: str) -> None:
    """
    Async engine'i başlatır ve tüm ORM tablolarını oluşturur.
    main.py tarafından uygulama başlangıcında bir kez çağrılır.
    """
    global _engine, _session_factory

    _engine = create_async_engine(db_url, echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    # Tabloları oluştur (models import edilerek Base.metadata alınır)
    from models.db_models import Base  # noqa: F811

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("database_initialized", db_url=db_url)


def get_session() -> AsyncSession:
    """
    Yeni bir async session döndürür.

    Kullanım:
        async with get_session() as session:
            session.add(record)
            await session.commit()
    """
    if _session_factory is None:
        raise RuntimeError("Veritabanı henüz başlatılmadı. Önce init_db() çağrılmalı.")
    return _session_factory()


async def close_db() -> None:
    """Engine'i kapatır. Graceful shutdown sırasında çağrılır."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database_closed")
