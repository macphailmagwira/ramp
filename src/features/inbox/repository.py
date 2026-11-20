"""Repository (CRUD + upsert) for :class:`InboxItem` rows."""

from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.common.base_repository import BaseRepository
from src.features.inbox.models import InboxItem
from src.features.inbox.schema import InboxItemCreate


class InboxRepository(BaseRepository):
    async def list_inbox(
        self,
        user_id,
        category: Optional[str] = None,
        cleared: bool = False,
    ) -> list[InboxItem]:
        """Return the user's inbox items, newest-first, filtered by category and cleared state."""
        query = select(InboxItem).where(
            InboxItem.user_id == user_id,
            InboxItem.cleared == cleared,
        )
        if category:
            query = query.where(InboxItem.category == category)
        query = query.order_by(InboxItem.timestamp.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def mark_read(self, item_id, user_id) -> int:
        """Set unread=False for a single item owned by the user. Returns rows affected."""
        result = await self.db.execute(
            update(InboxItem)
            .where(InboxItem.id == item_id, InboxItem.user_id == user_id)
            .values(unread=False)
        )
        await self.db.commit()
        return result.rowcount

    async def mark_cleared(self, item_id, user_id) -> int:
        """Set cleared=True for a single item owned by the user. Returns rows affected."""
        result = await self.db.execute(
            update(InboxItem)
            .where(InboxItem.id == item_id, InboxItem.user_id == user_id)
            .values(cleared=True)
        )
        await self.db.commit()
        return result.rowcount

    async def mark_all_read(self, user_id) -> int:
        """Bulk set unread=False for a user. Returns rows affected."""
        result = await self.db.execute(
            update(InboxItem).where(InboxItem.user_id == user_id).values(unread=False)
        )
        await self.db.commit()
        return result.rowcount

    async def upsert_inbox_item(self, user_id, payload: InboxItemCreate) -> None:
        """Insert an inbox item, or update it when (user_id, source_ref) already exists.

        Mirrors ArchitectureResultRepository.upsert_by_repo: a Postgres
        INSERT ... ON CONFLICT DO UPDATE so re-firing the same event updates
        the existing row instead of creating a duplicate.
        """
        data = payload.model_dump()
        data["user_id"] = user_id
        stmt = pg_insert(InboxItem).values(**data).on_conflict_do_update(
            index_elements=["user_id", "source_ref"],
            set_={
                "category": payload.category,
                "title": payload.title,
                "context": payload.context,
                "actor": payload.actor,
                "actor_is_ai": payload.actor_is_ai,
                "action": payload.action,
                "timestamp": payload.timestamp,
                "priority": payload.priority,
                "replies": payload.replies,
                "preview": payload.preview,
                "activity": payload.activity,
                "action_label": payload.action_label,
                "url": payload.url,
                "updated_at": func.now(),
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()
