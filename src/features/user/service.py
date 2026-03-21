import uuid
from typing import Optional

from fastapi import Depends, HTTPException

from src.features.user.models import User
from src.features.user.repository import UserRepository
from src.features.user.schema import (
    GitHubConnectionStatusSchema,
    UserCreateSchema,
    UserProfileUpdateSchema,
    UserWithGitHubSchema,
)
from src.features.github.repository import GitHubOAuthTokenRepository


class UserService:
    def __init__(
        self,
        repository: UserRepository = Depends(UserRepository),
        github_token_repo: GitHubOAuthTokenRepository = Depends(GitHubOAuthTokenRepository),
    ):
        self.repository = repository
        self.github_token_repo = github_token_repo

    async def _build_github_status(self, user_id: uuid.UUID) -> GitHubConnectionStatusSchema:
        token = await self.github_token_repo.get_by_user_id(user_id)
        return GitHubConnectionStatusSchema(
            is_connected=token is not None,
            github_username=token.github_username if token else None,
            github_user_id=token.github_user_id if token else None,
            connected_at=token.created_at if token else None,
        )

    async def _to_schema(self, user: User) -> UserWithGitHubSchema:
        github_status = await self._build_github_status(user.id)
        return UserWithGitHubSchema(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            github=github_status,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def create_user(self, data: UserCreateSchema) -> UserWithGitHubSchema:
        existing = await self.repository.get_by_email(data.email)
        if existing:
            raise HTTPException(status_code=400, detail="User with this email already exists")
        user = await self.repository.create(data)
        return await self._to_schema(user)

    async def get_user(self, user_id: uuid.UUID) -> UserWithGitHubSchema:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return await self._to_schema(user)

    async def get_user_with_github_status(self, user_id: uuid.UUID) -> UserWithGitHubSchema:
        return await self.get_user(user_id)

    async def list_users(self):
        users = await self.repository.get_all()
        return [await self._to_schema(u) for u in users]

    async def update_profile(self, user_id: uuid.UUID, data: UserProfileUpdateSchema) -> UserWithGitHubSchema:
        user = await self.repository.update(user_id, data)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return await self._to_schema(user)

    async def delete_user(self, user_id: uuid.UUID) -> None:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await self.repository.delete(user_id)