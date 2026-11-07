"""Service layer for the Storybook feature.

Responsibilities:
- generate: build a storybook from a connected repo's stored files, persist it, return it
- get: fetch the previously stored storybook
- refresh: re-scan the connected repo (updating the stored files), then regenerate
"""

import uuid

from fastapi import HTTPException

from src.features.storybook.repository import StorybookRepository
from src.features.github.repository import (
    ConnectedRepositoryRepository,
    GitHubOAuthTokenRepository,
    RepositoryFileRepository,
)
from src.features.github.services.scanner_service import RepoScannerService


class StorybookService:
    def __init__(self, db):
        self.db = db
        self.storybook_repo = StorybookRepository(db)
        self.repo_repo = ConnectedRepositoryRepository(db)
        self.token_repo = GitHubOAuthTokenRepository(db)
        self.file_repo = RepositoryFileRepository(db)

    async def _load_repo(self, connected_repo_id: uuid.UUID):
        repo = await self.repo_repo.get_by_id(repo_id=connected_repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Connected repository not found.")
        return repo

    async def _generate_and_persist(self, repo) -> dict:
        # Imported lazily: the LangGraph agent pulls in heavy deps (langgraph)
        # that are only needed at generation time, not at app startup.
        from src.features.storybook.agent.story_book_agent import generate_storybook

        rows = await self.file_repo.get_by_repo(repo.id)
        if not rows:
            raise HTTPException(
                status_code=400,
                detail="No indexed files for this repository. Connect/scan it first.",
            )
        book = await generate_storybook(files=rows)
        await self.storybook_repo.upsert_by_repo(repo.id, repo.user_id, book)
        return book

    async def generate(self, connected_repo_id: uuid.UUID) -> dict:
        repo = await self._load_repo(connected_repo_id)
        return await self._generate_and_persist(repo)

    async def get(self, connected_repo_id: uuid.UUID) -> dict:
        import json

        storybook = await self.storybook_repo.get_latest(connected_repo_id)
        if not storybook:
            raise HTTPException(status_code=404, detail="Storybook not found for this repository.")
        return json.loads(storybook.book)

    async def refresh(self, connected_repo_id: uuid.UUID) -> dict:
        """Re-scan the connected repo (updating the stored files) then regenerate."""
        repo = await self._load_repo(connected_repo_id)

        token = await self.token_repo.get_by_user_id(repo.user_id)
        if not token:
            raise HTTPException(
                status_code=400,
                detail="GitHub account not connected; cannot refresh repository files.",
            )

        scanner = RepoScannerService(self.db)
        await scanner.scan(
            connected_repo_id=repo.id,
            user_id=repo.user_id,
            clone_url=repo.clone_url,
            access_token=token.access_token,
            default_branch=repo.default_branch,
        )

        return await self._generate_and_persist(repo)
