from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session
from src.features.account.schema import (
    AccountMemberResponse,
    AccountResponse,
    AccountUpdate,
)
from src.features.account.service import AccountService
from src.middleware.user_context import EnrichedUserContext, get_current_user

account_router = APIRouter(prefix="/accounts", tags=["accounts"])


@account_router.get("/me", response_model=AccountResponse, operation_id="getMyAccount")
async def get_my_account(
    user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AccountResponse:
    return await AccountService(db).get_account(user.account_id, user.account_role)


@account_router.patch("/me", response_model=AccountResponse, operation_id="updateMyAccount")
async def update_my_account(
    payload: AccountUpdate,
    user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AccountResponse:
    return await AccountService(db).update_name(user.account_id, user.account_role, payload.name)


@account_router.delete("/me", status_code=204, operation_id="deleteMyAccount")
async def delete_my_account(
    user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await AccountService(db).delete_account(user.account_id, user.account_role)


@account_router.get("/me/members", response_model=list[AccountMemberResponse], operation_id="listAccountMembers")
async def list_account_members(
    user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[AccountMemberResponse]:
    return await AccountService(db).list_members(user.account_id)
