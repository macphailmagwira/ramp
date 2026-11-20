"""Repository (CRUD) for :class:`ArchitectureResult` rows."""

import json
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.common.base_repository import BaseRepository
from src.features.architecture.models import ArchitectureResult


class ArchitectureResultRepository(BaseRepository):
    async def get_latest(self, connected_repo_id: uuid.UUID) -> Optional[ArchitectureResult]:
        """Return the most recently stored architecture result for a repo, or None."""
        result = await self.db.execute(
            select(ArchitectureResult)
            .where(ArchitectureResult.connected_repo_id == connected_repo_id)
            .order_by(ArchitectureResult.updated_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def upsert_by_repo(
        self,
        connected_repo_id: uuid.UUID,
        user_id: uuid.UUID,
        graph: dict,
        schema_version: int = 1,
    ) -> ArchitectureResult:
        """Store an architecture result for a repo, replacing any previous one.

        Uses a Postgres INSERT ... ON CONFLICT DO UPDATE so concurrent
        regenerations cannot create duplicate rows (the unique
        connected_repo_id constraint turns a second insert into an update).
        """
        payload = json.dumps(graph, indent=2)
        stmt = pg_insert(ArchitectureResult).values(
            connected_repo_id=connected_repo_id,
            user_id=user_id,
            schema_version=schema_version,
            graph=payload,
        ).on_conflict_do_update(
            index_elements=['connected_repo_id'],
            set_={
                'user_id': user_id,
                'schema_version': schema_version,
                'graph': payload,
                'updated_at': func.now(),
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()
        return await self.get_latest(connected_repo_id)
