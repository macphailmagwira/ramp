from uuid import UUID

from pydantic import BaseModel


class StorybookGenerateRequest(BaseModel):
    connected_repo_id: UUID


class StorybookResponse(BaseModel):
    book: dict
