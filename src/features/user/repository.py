import uuid

from sqlalchemy import select

from src.common.base_repository import BaseRepository
from src.features.user.models import User
from src.features.user.schema import UserCreateSchema, UserProfileUpdateSchema


class UserRepository(BaseRepository):
    async def create(self, data: UserCreateSchema) -> User:
        user = User(**data.model_dump())
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_all(self):
        result = await self.db.execute(select(User))
        return result.scalars().all()

    async def update(self, user_id: uuid.UUID, data: UserProfileUpdateSchema) -> User | None:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        for key, value in data.model_dump(exclude_none=True).items():
            if hasattr(user, key):
                setattr(user, key, value)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete(self, user_id: uuid.UUID) -> None:
        user = await self.get_by_id(user_id)
        if user:
            await self.db.delete(user)
            await self.db.commit()