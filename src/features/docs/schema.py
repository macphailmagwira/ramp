import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.features.docs.enums import NodeType, WorkspaceRole

BLOCK_TYPES = Literal[
    "paragraph",
    "heading1",
    "heading2",
    "heading3",
    "bulleted",
    "numbered",
    "todo",
    "quote",
    "code",
    "divider",
]

MAX_BLOCKS = 5000
MAX_TEXT_LEN = 100_000
MAX_LABEL_LEN = 300
MAX_WORKSPACE_LABEL = 120


class DocBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: BLOCK_TYPES
    text: str = ""
    checked: bool | None = None

    @field_validator("checked")
    @classmethod
    def _checked_only_for_todo(cls, v, info):
        if v is not None and info.data.get("type") != "todo":
            raise ValueError("checked is only allowed for type 'todo'")
        return v

    @field_validator("text")
    @classmethod
    def _text_length(cls, v):
        if len(v) > MAX_TEXT_LEN:
            raise ValueError(f"text exceeds {MAX_TEXT_LEN} chars")
        return v


class PutContentRequest(BaseModel):
    label: str | None = Field(None, max_length=MAX_LABEL_LEN)
    blocks: list[DocBlock]
    base_version: int | None = None

    @field_validator("blocks")
    @classmethod
    def _block_count(cls, v):
        if len(v) > MAX_BLOCKS:
            raise ValueError(f"too many blocks (max {MAX_BLOCKS})")
        return v


class WorkspaceCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=MAX_WORKSPACE_LABEL)
    icon: str | None = Field(None, max_length=32)


class WorkspaceUpdate(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=MAX_WORKSPACE_LABEL)
    icon: str | None = Field(None, max_length=32)


class WorkspaceResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    label: str
    icon: str | None
    role: str
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberCreate(BaseModel):
    user_id: uuid.UUID | None = None
    email: str | None = None
    role: WorkspaceRole

    @field_validator("email")
    @classmethod
    def _require_one(cls, v, info):
        if not v and not info.data.get("user_id"):
            raise ValueError("provide user_id or email")
        return v


class WorkspaceMemberResponse(BaseModel):
    user_id: uuid.UUID
    name: str | None = None
    email: str | None = None
    avatar: str | None = None
    role: str
    added_at: datetime


class NodeCreate(BaseModel):
    parent_id: uuid.UUID | None = None
    type: NodeType
    label: str = Field(..., min_length=1, max_length=MAX_LABEL_LEN)


class NodeRename(BaseModel):
    label: str = Field(..., min_length=1, max_length=MAX_LABEL_LEN)


class MoveRequest(BaseModel):
    new_parent_id: uuid.UUID | None = None


class KnowledgeNode(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    type: str
    label: str
    version: int
    updated_at: datetime
    updated_by: uuid.UUID | None = None


class ContentResponse(BaseModel):
    id: uuid.UUID
    label: str
    blocks: list[DocBlock]
    version: int
    updated_at: datetime


class VersionSummary(BaseModel):
    version: int
    label: str
    block_count: int
    edited_by: uuid.UUID
    created_at: datetime


class VersionDetail(BaseModel):
    label: str
    blocks: list[DocBlock]
