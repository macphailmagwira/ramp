import uuid

from fastapi import Depends, HTTPException
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session
from src.features.account.enums import AccountRole
from src.features.account.models import Account
from src.features.github.repository import GitHubOAuthTokenRepository
from src.features.user.models import User
from src.features.user.repository import UserRepository
from src.features.user.schema import (
    GitHubConnectionStatusSchema,
    UserCreateSchema,
    UserMemberCreateSchema,
    UserProfileUpdateSchema,
    UserWithGitHubSchema,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    def __init__(
        self,
        repository: UserRepository = Depends(UserRepository),
        github_token_repo: GitHubOAuthTokenRepository = Depends(GitHubOAuthTokenRepository),
        db: AsyncSession = Depends(get_db_session),
    ):
        self.repository = repository
        self.github_token_repo = github_token_repo
        self.db = db

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
            account_id=user.account_id,
            account_role=user.account_role.value if user.account_role else None,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def signup(self, data: UserCreateSchema) -> UserWithGitHubSchema:
        existing = await self.repository.get_by_email(data.email)
        if existing:
            raise HTTPException(status_code=400, detail="User with this email already exists")
        account = Account(name=data.company_name)
        self.db.add(account)
        await self.db.flush()
        user = User(
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            hashed_password=pwd_context.hash(data.password),
            account_id=account.id,
            account_role=AccountRole.ADMIN,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(user)
        return await self._to_schema(user)

    async def create_member(
        self, current_user_id: uuid.UUID, data: UserMemberCreateSchema
    ) -> UserWithGitHubSchema:
        admin = await self.repository.get_by_id(current_user_id)
        if admin is None or admin.account_role != AccountRole.ADMIN or admin.account_id is None:
            raise HTTPException(status_code=403, detail="Only account admins can add members")
        existing = await self.repository.get_by_email(data.email)
        if existing:
            raise HTTPException(status_code=400, detail="User with this email already exists")
        user = User(
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            hashed_password=pwd_context.hash(data.password),
            account_id=admin.account_id,
            account_role=AccountRole.MEMBER,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(user)
        return await self._to_schema(user)

    async def authenticate(self, email: str, password: str) -> UserWithGitHubSchema:
        user = await self.repository.get_by_email(email)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not user.hashed_password or not pwd_context.verify(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return await self._to_schema(user)

    async def get_user(
        self, user_id: uuid.UUID, current_user=None
    ) -> UserWithGitHubSchema:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if current_user is not None and user.account_id != current_user.account_id:
            raise HTTPException(status_code=404, detail="User not found")
        return await self._to_schema(user)

    async def get_user_with_github_status(
        self, user_id: uuid.UUID, current_user=None
    ) -> UserWithGitHubSchema:
        return await self.get_user(user_id, current_user)

    async def list_users(self, account_id: uuid.UUID) -> list[UserWithGitHubSchema]:
        users = await self.repository.get_by_account_id(account_id)
        return [await self._to_schema(u) for u in users]

    async def update_profile(
        self, user_id: uuid.UUID, data: UserProfileUpdateSchema, current_user
    ) -> UserWithGitHubSchema:
        user = await self.repository.get_by_id(user_id)
        if not user or user.account_id != current_user.account_id:
            raise HTTPException(status_code=404, detail="User not found")
        if user.id != current_user.id and not current_user.is_account_admin:
            raise HTTPException(status_code=403, detail="Only account admins can update other users")
        updated = await self.repository.update(user_id, data)
        if updated is None:
            raise HTTPException(status_code=404, detail="User not found")
        return await self._to_schema(updated)

    async def delete_user(self, user_id: uuid.UUID, current_user) -> None:
        if not current_user.is_account_admin:
            raise HTTPException(status_code=403, detail="Only account admins can delete users")
        user = await self.repository.get_by_id(user_id)
        if not user or user.account_id != current_user.account_id:
            raise HTTPException(status_code=404, detail="User not found")
        await self.repository.delete(user_id)
