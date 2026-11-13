"""Repository (CRUD) for :class:`ArchitectureResult` rows."""

import json
import uuid
from typing import Optional

from sqlalchemy import select

from src.common.base_repository import BaseRepository
from src.features.architecture.models import ArchitectureResult


class ArchitectureResultRepository(BaseRepository):
    async def get_latest(self, connected_repo_id: uuid.UUID) -> Optional[ArchitectureResult]:
        """Return the most recently stored architecture result for a repo, or None."""
        result = await self.db.execute(
            select(ArchitectureResult)
            .where(ArchitectureResult.connected_repo_id == connected_repo_id)
            .order_by(ArchitectureResult.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def upsert_by_repo(
        self,
        connected_repo_id: uuid.UUID,
        user_id: uuid.UUID,
        graph: dict,
        schema_version: int = 1,
    ) -> ArchitectureResult:
        """Store an architecture result for a repo, replacing any previous one."""
        existing = await self.get_latest(connected_repo_id)
        payload = json.dumps(graph, indent=2)
        if existing:
            existing.graph = payload
            existing.schema_version = schema_version
            existing.user_id = user_id
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        row = ArchitectureResult(
            connected_repo_id=connected_repo_id,
            user_id=user_id,
            schema_version=schema_version,
            graph=payload,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row
