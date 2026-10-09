import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from bot.config import settings
from bot.database.models import Base

logger = logging.getLogger(__name__)

def get_engine():
    db_url = settings.async_database_url
    if not db_url:
        raise ValueError(
            "DATABASE_URL belum diatur! "
            "Silakan tambahkan DATABASE_URL pada file .env atau Environment Variables Railway."
        )
    return create_async_engine(
        db_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True
    )

# Lazy/cached engine and sessionmaker
engine = None
_session_maker = None

def get_sessionmaker():
    global engine, _session_maker
    if _session_maker is None:
        engine = get_engine()
        _session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return _session_maker

def async_session():
    return get_sessionmaker()()

async def init_db():
    """Membuat tabel jika belum ada (auto-migrate sederhana untuk MVP)."""
    global engine
    if engine is None:
        get_sessionmaker()
    async with engine.begin() as conn:
        logger.info("Menginisialisasi tabel database...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database siap digunakan! ૮ ˶ᵔ ᵕ ᵔ˶ ა")
