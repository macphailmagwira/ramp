import uuid

from fastapi import HTTPException
from sqlalchemy import select

from src.common.base_repository import BaseRepository
from src.features.account.enums import AccountRole
from src.features.account.repository import AccountRepository
from src.features.account.schema import AccountMemberResponse, AccountResponse
from src.features.user.models import User


class AccountService(BaseRepository):
    async def get_account(
        self, account_id: uuid.UUID, role: AccountRole | None
    ) -> AccountResponse:
        account = await AccountRepository(self.db).get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        return AccountResponse(
            id=account.id,
            name=account.name,
            role=role.value if role else AccountRole.MEMBER.value,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )

    async def update_name(
        self, account_id: uuid.UUID, role: AccountRole | None, name: str
    ) -> AccountResponse:
        if role != AccountRole.ADMIN:
            raise HTTPException(status_code=403, detail="Only account admins can do this")
        repo = AccountRepository(self.db)
        account = await repo.get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        account = await repo.update_name(account, name)
        await self.db.commit()
        await self.db.refresh(account)
        return AccountResponse(
            id=account.id,
            name=account.name,
            role=role.value if role else AccountRole.MEMBER.value,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )

    async def list_members(self, account_id: uuid.UUID) -> list[AccountMemberResponse]:
        rows = (
            await self.db.execute(
                select(User).where(User.account_id == account_id).order_by(User.created_at)
            )
        ).scalars().all()
        return [
            AccountMemberResponse(
                id=u.id,
                first_name=u.first_name,
                last_name=u.last_name,
                email=u.email,
                role=u.account_role.value,
                created_at=u.created_at,
            )
            for u in rows
        ]

    async def delete_account(self, account_id: uuid.UUID, role: AccountRole | None) -> None:
        if role != AccountRole.ADMIN:
            raise HTTPException(status_code=403, detail="Only account admins can do this")
        account = await AccountRepository(self.db).get(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        await self.db.delete(account)
        await self.db.commit()
