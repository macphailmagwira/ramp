import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.github.schema import (
    OverviewCommitSchema,
    OverviewResponseSchema,
    OverviewStatsSchema,
)
from src.features.github.models import (
    ConnectedRepository,
    RepositoryFile,
    FileDependency,
    RepositoryFunction,
)
from src.features.github.repository import GitHubOAuthTokenRepository
from src.config.constants import GITHUB_API_BASE
from fastapi import HTTPException
import httpx


class OverviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_overview(
        self,
        connected_repo_id: uuid.UUID,
        user_id: uuid.UUID,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> OverviewResponseSchema:
        repo = await self._get_repo(connected_repo_id, user_id)
        stats = await self._get_stats(connected_repo_id)
        commits = await self._get_recent_commits(repo, since, until)
        language = await self._get_language(connected_repo_id)

        return OverviewResponseSchema(
            stats=stats,
            recent_commits=commits,
            language=language,
            default_branch=repo.default_branch,
            description=repo.description,
        )

    async def _get_repo(
        self, repo_id: uuid.UUID, user_id: uuid.UUID
    ) -> ConnectedRepository:
        result = await self.db.execute(
            select(ConnectedRepository).where(
                ConnectedRepository.id == repo_id,
                ConnectedRepository.user_id == user_id,
                ConnectedRepository.is_active == True,
            )
        )
        repo = result.scalar_one_or_none()
        if not repo:
            raise HTTPException(
                status_code=404, detail="Connected repository not found."
            )
        return repo

    async def _get_language(self, repo_id: uuid.UUID) -> str | None:
        result = await self.db.execute(
            select(RepositoryFile.language, func.count(RepositoryFile.id))
            .where(
                RepositoryFile.connected_repo_id == repo_id,
                RepositoryFile.is_binary == False,
                RepositoryFile.language.isnot(None),
            )
            .group_by(RepositoryFile.language)
            .order_by(func.count(RepositoryFile.id).desc())
            .limit(1)
        )
        row = result.first()
        return row[0] if row else None

    async def _get_stats(self, repo_id: uuid.UUID) -> OverviewStatsSchema:
        file_count = await self.db.scalar(
            select(func.count(RepositoryFile.id)).where(
                RepositoryFile.connected_repo_id == repo_id,
                RepositoryFile.is_binary == False,
            )
        ) or 0

        folder_count = await self.db.scalar(
            select(func.count(func.distinct(func.replace(RepositoryFile.path, RepositoryFile.name, '')))).where(
                RepositoryFile.connected_repo_id == repo_id,
                RepositoryFile.is_binary == False,
            )
        ) or 0

        function_count = await self.db.scalar(
            select(func.count(RepositoryFunction.id)).where(
                RepositoryFunction.connected_repo_id == repo_id,
            )
        ) or 0

        dep_count = await self.db.scalar(
            select(func.count(FileDependency.id)).where(
                FileDependency.connected_repo_id == repo_id,
            )
        ) or 0

        return OverviewStatsSchema(
            files=file_count,
            folders=folder_count,
            functions=function_count,
            dependencies=dep_count,
        )

    async def _get_recent_commits(
        self,
        repo: ConnectedRepository,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[OverviewCommitSchema]:
        try:
            token_repo = GitHubOAuthTokenRepository(self.db)
            token = await token_repo.get_by_user_id(user_id=repo.user_id)
            if not token:
                return []

            headers = {
                "Authorization": f"Bearer {token.access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }

            params: dict = {"per_page": 100, "page": 1, "sha": repo.default_branch}
            if since:
                params["since"] = since
            if until:
                params["until"] = until

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GITHUB_API_BASE}/repos/{repo.owner}/{repo.name}/commits",
                    headers=headers,
                    params=params,
                )

            if response.status_code != 200:
                return []

            raw_commits = response.json()
            result = []
            for c in raw_commits:
                message = c.get("commit", {}).get("message", "").split("\n")[0]
                msg_lower = message.lower()
                if msg_lower.startswith("feat") or msg_lower.startswith("add"):
                    commit_type = "feat"
                elif msg_lower.startswith("fix") or msg_lower.startswith("bug"):
                    commit_type = "fix"
                elif msg_lower.startswith("docs"):
                    commit_type = "docs"
                elif msg_lower.startswith("refactor"):
                    commit_type = "refactor"
                elif msg_lower.startswith("chore"):
                    commit_type = "chore"
                elif msg_lower.startswith("test"):
                    commit_type = "test"
                elif msg_lower.startswith("perf"):
                    commit_type = "perf"
                else:
                    commit_type = "other"

                result.append(
                    OverviewCommitSchema(
                        sha=c.get("sha", ""),
                        message=message,
                        author=c.get("commit", {}).get("author", {}).get("name", "Unknown"),
                        date=c.get("commit", {}).get("author", {}).get("date", ""),
                        type=commit_type,
                    )
                )
            return result
        except Exception:
            return []
