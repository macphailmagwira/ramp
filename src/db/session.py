from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from fastapi import Request
from typing import AsyncGenerator

from src.config import settings
import src.db.base  

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,      
    pool_recycle=90,         
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

import logging
logging.getLogger("api-main").warning(f"DATABASE_URL in use: {settings.DATABASE_URL}")


async def get_db(request: Request = None) -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session.
    
    If called from a route and the middleware has already created a session,
    reuse that session. Otherwise, create a new session.
    
    This ensures:
    1. Middleware and routes share the same session (1 connection per request)
    2. Transaction consistency between middleware and routes
    3. Tests work naturally with dependency overrides
    """
    # Try to reuse middleware's session if available
    if request and hasattr(request.state, "db") and request.state.db is not None:
        # Middleware already created a session, reuse it
        yield request.state.db
    else:
        # No middleware session (public endpoint or direct call), create new one
        async with AsyncSessionLocal() as session:
            try:  
                yield session
            finally:
                await session.close()


# Wrapper for dependency injection that passes request
async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Wrapper for get_db to use in Depends().
    
    Use this in your repositories/services:
        db: AsyncSession = Depends(get_db_session)
    """
    async for session in get_db(request):
        yield session