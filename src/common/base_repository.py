from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db_session

class BaseRepository:
    def __init__(self, db: AsyncSession = Depends(get_db_session)):
        self.db = db
    async def create(self, **kwargs):
        raise NotImplementedError()

    async def update(self, **kwargs):
        raise NotImplementedError()

    async def delete(self, **kwargs):
        raise NotImplementedError()

    async def filter(self, **kwargs):
        raise NotImplementedError()

    async def get_by_id(self, **kwargs):
        raise NotImplementedError()

    async def get_all(self):
        raise NotImplementedError()
