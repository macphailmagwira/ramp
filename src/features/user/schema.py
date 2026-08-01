import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class GitHubConnectionStatusSchema(BaseModel):
    is_connected: bool
    github_username: Optional[str] = None
    github_user_id: Optional[str] = None
    connected_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserCreateSchema(BaseModel):
    first_name: str = Field(max_length=255)
    last_name: str = Field(max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(from_attributes=True)


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str

    model_config = ConfigDict(from_attributes=True)


class LoginResponseSchema(BaseModel):
    user: 'UserWithGitHubSchema'
    token: str

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdateSchema(BaseModel):
    first_name: Optional[str] = Field(None, max_length=255)
    last_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None

    model_config = ConfigDict(from_attributes=True)


class UserWithGitHubSchema(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    github: Optional[GitHubConnectionStatusSchema] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
