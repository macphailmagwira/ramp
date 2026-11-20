import uuid

from sqlalchemy import select

from src.common.base_repository import BaseRepository
from src.features.account.models import Account


class AccountRepository(BaseRepository):
    async def get(self, account_id: uuid.UUID) -> Account | None:
        return (
            await self.db.execute(select(Account).where(Account.id == account_id))
        ).scalar_one_or_none()

    async def update_name(self, account: Account, name: str) -> Account:
        account.name = name
        await self.db.flush()
        return account
