import uuid
from typing import List, Optional, Sequence

from sqlalchemy import delete, insert, select

from src.common.base_repository import BaseRepository
from src.features.github.models import ConnectedRepository, GitHubOAuthToken
from src.features.github.schema import (
    ConnectRepositoryRequestSchema,
    GitHubOAuthTokenCreateSchema,
)
from src.features.github.models import RepositoryFile
from src.features.github.models import FileDependency
from src.common.base_repository import BaseRepository
from src.features.github.models import FunctionCall, RepositoryFunction



class GitHubOAuthTokenRepository(BaseRepository):
    async def upsert(self, data: GitHubOAuthTokenCreateSchema) -> GitHubOAuthToken:
        existing = await self.get_by_user_id(user_id=data.user_id)

        if existing:
            existing.access_token = data.access_token
            existing.token_type = data.token_type
            existing.scope = data.scope
            existing.github_user_id = data.github_user_id
            existing.github_username = data.github_username
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        token = GitHubOAuthToken(**data.model_dump())
        self.db.add(token)
        await self.db.commit()
        await self.db.refresh(token)
        return token

    async def get_by_user_id(self, **kwargs) -> GitHubOAuthToken | None:
        user_id = kwargs['user_id']
        result = await self.db.execute(
            select(GitHubOAuthToken).where(GitHubOAuthToken.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def delete_by_user_id(self, user_id: uuid.UUID) -> None:
        token = await self.get_by_user_id(user_id=user_id)
        if token:
            await self.db.delete(token)
            await self.db.commit()


class ConnectedRepositoryRepository(BaseRepository):
    async def create(self, **kwargs) -> ConnectedRepository:
        data = kwargs['data']
        user_id = kwargs['user_id']
        
        repo = ConnectedRepository(
            user_id=user_id,
            repo_id=data.repo_id,
            owner=data.owner,
            name=data.name,
            full_name=data.full_name,
            clone_url=data.clone_url,
            default_branch=data.default_branch,
            is_private=data.is_private,
            description=data.description,
        )
        self.db.add(repo)
        await self.db.commit()
        await self.db.refresh(repo)
        return repo

    async def get_by_id(self, **kwargs) -> ConnectedRepository | None:
        repo_id = kwargs['repo_id']
        result = await self.db.execute(
            select(ConnectedRepository).where(ConnectedRepository.id == repo_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: uuid.UUID) -> Sequence[ConnectedRepository]:
        result = await self.db.execute(
            select(ConnectedRepository).where(
                ConnectedRepository.user_id == user_id,
                ConnectedRepository.is_active == True,  # noqa: E712
            )
        )
        return result.scalars().all()

    async def get_by_user_and_repo(
        self, user_id: uuid.UUID, full_name: str
    ) -> ConnectedRepository | None:
        result = await self.db.execute(
            select(ConnectedRepository).where(
                ConnectedRepository.user_id == user_id,
                ConnectedRepository.full_name == full_name,
            )
        )
        return result.scalar_one_or_none()

    async def soft_delete(self, repo_id: uuid.UUID) -> Optional[ConnectedRepository]:
        repo = await self.get_by_id(repo_id=repo_id)
        if repo:
            repo.is_active = False
            await self.db.commit()
            await self.db.refresh(repo)
        return repo


class RepositoryFileRepository(BaseRepository):
    async def replace_for_repo(
        self,
        connected_repo_id: uuid.UUID,
        user_id: uuid.UUID,
        files: List[dict],
    ) -> None:
        await self.db.execute(
            delete(RepositoryFile).where(
                RepositoryFile.connected_repo_id == connected_repo_id
            )
        )

        if files:
            await self.db.execute(
                insert(RepositoryFile),
                [
                    {
                        "id": uuid.uuid4(),
                        "connected_repo_id": connected_repo_id,
                        "user_id": user_id,
                        **f,
                    }
                    for f in files
                ],
            )

        await self.db.commit()

    async def get_by_repo(self, connected_repo_id: uuid.UUID) -> List[RepositoryFile]:
        result = await self.db.execute(
            select(RepositoryFile)
            .where(RepositoryFile.connected_repo_id == connected_repo_id)
            .order_by(RepositoryFile.path)
        )
        return list(result.scalars().all())
    

class FileDependencyRepository(BaseRepository):
    async def replace_for_repo(
        self,
        connected_repo_id: uuid.UUID,
        edges: List[dict],
    ) -> None:
        await self.db.execute(
            delete(FileDependency).where(
                FileDependency.connected_repo_id == connected_repo_id
            )
        )
        if edges:
            await self.db.execute(
                insert(FileDependency),
                [{"id": uuid.uuid4(), **e} for e in edges],
            )
        await self.db.commit()

    async def get_by_repo(self, connected_repo_id: uuid.UUID) -> List[FileDependency]:
        result = await self.db.execute(
            select(FileDependency)
            .where(FileDependency.connected_repo_id == connected_repo_id)
        )
        return list(result.scalars().all())
    

class RepositoryFunctionRepository(BaseRepository):
    """CRUD for repository_functions rows."""

    async def replace_for_repo(
        self,
        connected_repo_id: uuid.UUID,
        file_id: uuid.UUID,
        symbols: List[dict],
    ) -> None:
        """
        Delete all existing symbols for *file_id* then bulk-insert fresh ones.
        Called per-file so a partial re-scan is possible in future.
        """
        await self.db.execute(
            delete(RepositoryFunction).where(
                RepositoryFunction.file_id == file_id
            )
        )
        if symbols:
            await self.db.execute(
                insert(RepositoryFunction),
                [
                    {
                        "id": uuid.uuid4(),
                        "connected_repo_id": connected_repo_id,
                        "file_id": file_id,
                        **s,
                    }
                    for s in symbols
                ],
            )
        await self.db.commit()

    async def get_by_repo(
        self, connected_repo_id: uuid.UUID
    ) -> List[RepositoryFunction]:
        result = await self.db.execute(
            select(RepositoryFunction)
            .where(RepositoryFunction.connected_repo_id == connected_repo_id)
            .order_by(RepositoryFunction.name)
        )
        return list(result.scalars().all())

    async def get_by_file(self, file_id: uuid.UUID) -> List[RepositoryFunction]:
        result = await self.db.execute(
            select(RepositoryFunction).where(RepositoryFunction.file_id == file_id)
        )
        return list(result.scalars().all())


class FunctionCallRepository(BaseRepository):
    """CRUD for function_calls rows."""

    async def replace_for_repo(
        self,
        connected_repo_id: uuid.UUID,
        edges: List[dict],
    ) -> None:
        """Replace the entire call graph for a repository in one shot."""
        await self.db.execute(
            delete(FunctionCall).where(
                FunctionCall.connected_repo_id == connected_repo_id
            )
        )
        if edges:
            await self.db.execute(
                insert(FunctionCall),
                [{"id": uuid.uuid4(), **e} for e in edges],
            )
        await self.db.commit()

    async def get_by_repo(
        self, connected_repo_id: uuid.UUID
    ) -> List[FunctionCall]:
        result = await self.db.execute(
            select(FunctionCall).where(
                FunctionCall.connected_repo_id == connected_repo_id
            )
        )
        return list(result.scalars().all())