"""HTTP endpoints for the user inbox. All routes require an authenticated user."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session
from src.features.inbox.repository import InboxRepository
from src.features.inbox.schema import InboxItemResponse
from src.middleware.user_context import EnrichedUserContext, get_current_user

inbox_router = APIRouter(tags=["inbox"])


@inbox_router.get(
    "/inbox",
    response_model=list[InboxItemResponse],
    operation_id="getInbox",
    summary="List a user's inbox items, newest-first",
)
async def get_inbox(
    category: str | None = None,
    cleared: bool = False,
    current_user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[InboxItemResponse]:
    return await InboxRepository(db).list_inbox(
        user_id=current_user.id, category=category, cleared=cleared
    )


@inbox_router.post(
    "/inbox/{item_id}/read",
    status_code=204,
    operation_id="markInboxRead",
    summary="Mark a single inbox item as read",
)
async def mark_read(
    item_id: UUID,
    current_user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    rowcount = await InboxRepository(db).mark_read(item_id, current_user.id)
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Inbox item not found")


@inbox_router.post(
    "/inbox/{item_id}/clear",
    status_code=204,
    operation_id="markInboxCleared",
    summary="Clear a single inbox item",
)
async def mark_cleared(
    item_id: UUID,
    current_user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    rowcount = await InboxRepository(db).mark_cleared(item_id, current_user.id)
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Inbox item not found")


@inbox_router.post(
    "/inbox/read-all",
    status_code=204,
    operation_id="markAllInboxRead",
    summary="Mark all of a user's inbox items as read",
)
async def mark_all_read(
    current_user: EnrichedUserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await InboxRepository(db).mark_all_read(current_user.id)
