import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class AccountMemberResponse(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
