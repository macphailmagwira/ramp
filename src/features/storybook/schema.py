from uuid import UUID

from pydantic import BaseModel


class StorybookGenerateRequest(BaseModel):
    connected_repo_id: UUID


class StorybookResponse(BaseModel):
    book: dict


class StorybookFileContentResponse(BaseModel):
    """Full (uncapped) content of one indexed file, for storybook drill-down."""

    path: str
    content: str
    language: str | None = None
    extension: str | None = None
    size_bytes: int = 0
    is_binary: bool = False
    line_count: int = 0
