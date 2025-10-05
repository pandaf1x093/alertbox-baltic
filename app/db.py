from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import settings

engine = create_async_engine(settings.database_url, future=True, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
