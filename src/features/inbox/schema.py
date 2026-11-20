from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActivityLine(BaseModel):
    icon: str
    text: str
    time: str  # ISO


class InboxItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str
    title: str
    context: List[str]
    actor: str
    actorIsAi: bool = Field(alias="actor_is_ai", default=False)
    action: str
    timestamp: datetime
    unread: bool
    cleared: bool
    priority: Optional[int] = None
    replies: Optional[int] = None
    preview: str
    activity: List[ActivityLine]
    actionLabel: str = Field(alias="action_label")
    url: str


class InboxItemCreate(BaseModel):
    """Payload for creating/upserting an inbox item from a hook."""

    category: str
    title: str
    context: List[str] = []
    actor: str
    actor_is_ai: bool = False
    action: str
    timestamp: datetime
    priority: Optional[int] = None
    replies: Optional[int] = None
    preview: str
    activity: List[ActivityLine] = []
    action_label: str
    url: str
    source_ref: Optional[str] = None
