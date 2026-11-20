import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base_class import Base
from src.db.model_mixins import BaseDbModelMixin


class InboxItem(BaseDbModelMixin, Base):
    __tablename__ = "inbox_item"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(20), index=True)  # mention|review|doc|meeting
    title: Mapped[str] = mapped_column(String(300))
    context: Mapped[list] = mapped_column(JSONB, default=list)  # breadcrumb segments
    actor: Mapped[str] = mapped_column(String(200))  # who triggered it
    actor_is_ai: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    action: Mapped[str] = mapped_column(String(300))  # e.g. "requested your review"
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    unread: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    cleared: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), index=True, nullable=False
    )
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    replies: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preview: Mapped[str] = mapped_column(Text)
    activity: Mapped[list] = mapped_column(JSONB, default=list)  # [{icon, text, time}]
    action_label: Mapped[str] = mapped_column(String(100))  # button text
    url: Mapped[str] = mapped_column(String(500))

    # Stable id of the originating event, so re-firing updates instead of duplicating.
    source_ref: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("user_id", "source_ref", name="uq_inbox_user_source"),
    )
