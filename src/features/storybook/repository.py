"""Repository (CRUD) for :class:`Storybook` rows."""

import json
import uuid
from typing import Optional

from sqlalchemy import select

from src.common.base_repository import BaseRepository
from src.features.storybook.models import Storybook


class StorybookRepository(BaseRepository):
    async def get_latest(self, connected_repo_id: uuid.UUID) -> Optional[Storybook]:
        """Return the most recently stored storybook for a repo, or None."""
        result = await self.db.execute(
            select(Storybook)
            .where(Storybook.connected_repo_id == connected_repo_id)
            .order_by(Storybook.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def upsert_by_repo(
        self,
        connected_repo_id: uuid.UUID,
        user_id: uuid.UUID,
        book: dict,
        schema_version: int = 1,
    ) -> Storybook:
        """Store a storybook for a repo, replacing any previous one."""
        existing = await self.get_latest(connected_repo_id)
        payload = json.dumps(book, indent=2)
        if existing:
            existing.book = payload
            existing.schema_version = schema_version
            existing.user_id = user_id
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        storybook = Storybook(
            connected_repo_id=connected_repo_id,
            user_id=user_id,
            schema_version=schema_version,
            book=payload,
        )
        self.db.add(storybook)
        await self.db.commit()
        await self.db.refresh(storybook)
        return storybook
