"""Persisted architecture graph for a connected repository.

Mirrors the Storybook pattern: the full ArchitectureGraphResponse is stored as
JSON so it can be loaded on demand instead of regenerated (the generation pass
includes LLM calls). One row per repo (upsert replaces the previous result).
"""

import uuid

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base_class import Base
from src.db.model_mixins import BaseDbModelMixin


class ArchitectureResult(BaseDbModelMixin, Base):
    __tablename__ = "architecture_result"

    connected_repo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connected_repository.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)

    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    graph: Mapped[str] = mapped_column(Text, nullable=False)  # JSON of ArchitectureGraphResponse
