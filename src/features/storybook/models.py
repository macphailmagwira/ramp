"""DB model for a generated Storybook.

A Storybook is the output of the Storybook agent (see
``src.features.storybook.agent.story_book_agent``) for one connected repository. It is keyed
to a :class:`ConnectedRepository` and persists the full ``book`` dict as JSON so
it can be fetched later and refreshed when the stored repo changes.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base_class import Base
from src.db.model_mixins import BaseDbModelMixin


class Storybook(BaseDbModelMixin, Base):
    __tablename__ = "storybook"

    connected_repo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connected_repository.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)

    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    book: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded book dict
