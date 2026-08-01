import base64
import uuid
from typing import List, Optional
from urllib.parse import urlencode

import httpx
from fastapi import Depends, HTTPException

from src.config import settings
from src.features.github.models import ConnectedRepository, GitHubOAuthToken
from src.features.github.repository import (
    ConnectedRepositoryRepository,
    GitHubOAuthTokenRepository,
)

from src.features.github.schema import (
    ConnectRepositoryRequestSchema,
    GitHubBranchSchema,
    GitHubCommitSchema,
    GitHubFileContentSchema,
    GitHubFileSchema,
    GitHubOAuthLoginResponseSchema,
    GitHubOAuthTokenCreateSchema,
    GitHubOAuthTokenRetrieveSchema,
    GitHubRepoListSchema,
    GitHubRepoSchema,
    ConnectedRepositoryRetrieveSchema,
)

from src.features.github.tasks import scan_repository_task


from src.config.constants import GITHUB_AUTHORIZE_URL, GITHUB_TOKEN_URL, GITHUB_API_BASE




# ---------------------------------------------------------------------------
# OAuth Flow Service
# ---------------------------------------------------------------------------


class GitHubOAuthService:
    def __init__(
        self,
        token_repository: GitHubOAuthTokenRepository = Depends(GitHubOAuthTokenRepository),
    ):
        self.token_repo = token_repository

    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Build the GitHub OAuth authorization URL to redirect the user to.
        Scopes: repo (full repository access) + read:user (profile info).
        """
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
            "scope": "repo read:user user:email",
            "allow_signup": "true",
        }
        if state:
            params["state"] = state

        return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> dict:
        """
        Exchange a short-lived authorization code for a GitHub access token.
        Returns the raw token response dict from GitHub.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.GITHUB_REDIRECT_URI,
                },
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Failed to exchange GitHub authorization code for access token.",
            )

        data = response.json()
        if "error" in data:
            raise HTTPException(
                status_code=400,
                detail=f"GitHub OAuth error: {data.get('error_description', data['error'])}",
            )

        return data

    async def get_github_user(self, access_token: str) -> dict:
        """Fetch the authenticated GitHub user's profile."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Failed to fetch GitHub user profile.",
            )

        return response.json()

    async def handle_callback(
        self, code: str, user_id: uuid.UUID
    ) -> GitHubOAuthLoginResponseSchema:
        """
        Full OAuth callback flow:
        1. Exchange code for token
        2. Fetch GitHub user profile
        3. Upsert token in DB
        4. Return token + GitHub user info
        """
        token_data = await self.exchange_code_for_token(code)
        access_token = token_data["access_token"]

        github_user = await self.get_github_user(access_token)

        token_create = GitHubOAuthTokenCreateSchema(
            user_id=user_id,
            access_token=access_token,
            token_type=token_data.get("token_type", "bearer"),
            scope=token_data.get("scope"),
            github_user_id=str(github_user.get("id")),
            github_username=github_user.get("login"),
        )

        saved_token = await self.token_repo.upsert(token_create)

        return GitHubOAuthLoginResponseSchema(
            github_username=saved_token.github_username,
            github_user_id=saved_token.github_user_id,
            token=GitHubOAuthTokenRetrieveSchema.model_validate(saved_token),
        )

    async def get_token_for_user(self, user_id: uuid.UUID) -> GitHubOAuthToken:
        """Retrieve stored token or raise 401 if not connected."""
        token = await self.token_repo.get_by_user_id(user_id=user_id)
        if not token:
            raise HTTPException(
                status_code=401,
                detail="GitHub account not connected. Please complete OAuth flow first.",
            )
        return token

    async def disconnect(self, user_id: uuid.UUID) -> None:
        """Remove the stored GitHub token for a user."""
        await self.token_repo.delete_by_user_id(user_id)


# ---------------------------------------------------------------------------
# Repository List Service
# ---------------------------------------------------------------------------


class GitHubRepositoryService:
    def __init__(
        self,
        token_repository: GitHubOAuthTokenRepository = Depends(GitHubOAuthTokenRepository),
        repo_repository: ConnectedRepositoryRepository = Depends(ConnectedRepositoryRepository),
    ):
        self.token_repo = token_repository
        self.repo_repo = repo_repository

    async def _get_access_token(self, user_id: uuid.UUID) -> str:
        token = await self.token_repo.get_by_user_id(user_id=user_id)
        if not token:
            raise HTTPException(
                status_code=401,
                detail="GitHub account not connected. Please complete OAuth flow first.",
            )
        return token.access_token

    def _build_headers(self, access_token: str) -> dict:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def list_user_repositories(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        per_page: int = 30,
        visibility: str = "all",  # "all" | "public" | "private"
    ) -> GitHubRepoListSchema:
        """
        Fetch the user's GitHub repositories using their stored OAuth token.
        Supports pagination and visibility filtering.
        """
        access_token = await self._get_access_token(user_id)

        params = {
            "visibility": visibility,
            "affiliation": "owner,collaborator,organization_member",
            "sort": "updated",
            "direction": "desc",
            "per_page": per_page,
            "page": page,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/user/repos",
                headers=self._build_headers(access_token),
                params=params,
            )

        if response.status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="GitHub token is invalid or expired. Please reconnect your GitHub account.",
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Failed to fetch repositories from GitHub.",
            )

        raw_repos = response.json()
        repos = [
            GitHubRepoSchema(
                id=r["id"],
                name=r["name"],
                full_name=r["full_name"],
                owner=r["owner"]["login"],
                description=r.get("description"),
                is_private=r["private"],
                clone_url=r["clone_url"],
                default_branch=r.get("default_branch", "main"),
                updated_at=r.get("updated_at"),
                language=r.get("language"),
                stargazers_count=r.get("stargazers_count", 0),
                forks_count=r.get("forks_count", 0),
            )
            for r in raw_repos
        ]

        return GitHubRepoListSchema(repositories=repos, total=len(repos))

    async def connect_repository(
    self,
    user_id: uuid.UUID,
    request: ConnectRepositoryRequestSchema,
) -> ConnectedRepository:
        access_token = await self._get_access_token(user_id)  

        existing = await self.repo_repo.get_by_user_and_repo(user_id, request.full_name)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=400,
                    detail=f"Repository '{request.full_name}' is already connected.",
                )
            existing.is_active = True
            await self.repo_repo.db.commit()
            await self.repo_repo.db.refresh(existing)
            repo = existing
        else:
            repo = await self.repo_repo.create(data=request, user_id=user_id)

        scan_repository_task.delay( # type: ignore[attr-defined]
            connected_repo_id=str(repo.id),
            user_id=str(user_id),
            clone_url=repo.clone_url,
            access_token=access_token,
            default_branch=repo.default_branch,
        )

        return repo
    


    async def disconnect_repository(self, repo_id: uuid.UUID, user_id: uuid.UUID) -> None:
            """Soft-delete a connected repository."""
            repo = await self.repo_repo.get_by_id(repo_id=repo_id)
            if not repo:
                raise HTTPException(status_code=404, detail="Connected repository not found.")
            if repo.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to disconnect this repository.")

            await self.repo_repo.soft_delete(repo_id)

        
    async def list_connected_repositories(
            self, user_id: uuid.UUID
        ) -> List[ConnectedRepository]:
            return list(await self.repo_repo.get_by_user_id(user_id))


# ---------------------------------------------------------------------------
# Repository Access Service  (files, commits, branches)
# ---------------------------------------------------------------------------


class GitHubRepositoryAccessService:
    """
    Low-level service for reading repository content via the GitHub API.
    Used by downstream features (code scanning, architecture analysis, etc.).
    """

    def __init__(
        self,
        token_repository: GitHubOAuthTokenRepository = Depends(GitHubOAuthTokenRepository),
    ):
        self.token_repo = token_repository

    async def _get_headers(self, user_id: uuid.UUID) -> dict:
        token = await self.token_repo.get_by_user_id(user_id=user_id)
        if not token:
            raise HTTPException(
                status_code=401,
                detail="GitHub account not connected.",
            )
        return {
            "Authorization": f"Bearer {token.access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def list_branches(
        self, user_id: uuid.UUID, owner: str, repo: str
    ) -> List[GitHubBranchSchema]:
        """List all branches in a repository."""
        headers = await self._get_headers(user_id)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/branches",
                headers=headers,
            )

        _raise_for_github_error(response, owner, repo)

        return [
            GitHubBranchSchema(
                name=b["name"],
                sha=b["commit"]["sha"],
                protected=b.get("protected", False),
            )
            for b in response.json()
        ]

    async def list_commits(
        self,
        user_id: uuid.UUID,
        owner: str,
        repo: str,
        branch: Optional[str] = None,
        per_page: int = 30,
        page: int = 1,
    ) -> List[GitHubCommitSchema]:
        """List recent commits in a repository."""
        headers = await self._get_headers(user_id)
        params: dict = {"per_page": per_page, "page": page}
        if branch:
            params["sha"] = branch

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits",
                headers=headers,
                params=params,
            )

        _raise_for_github_error(response, owner, repo)

        return [
            GitHubCommitSchema(
                sha=c["sha"],
                message=c["commit"]["message"].split("\n")[0],  # First line only
                author_name=c["commit"]["author"]["name"],
                author_email=c["commit"]["author"]["email"],
                date=c["commit"]["author"]["date"],
                url=c["html_url"],
            )
            for c in response.json()
        ]

    async def list_files(
        self,
        user_id: uuid.UUID,
        owner: str,
        repo: str,
        path: str = "",
        ref: Optional[str] = None,
    ) -> List[GitHubFileSchema]:
        """
        List files and directories at a given path in the repository.
        Use path="" for the root. Use ref to specify a branch or commit SHA.
        """
        headers = await self._get_headers(user_id)
        params = {}
        if ref:
            params["ref"] = ref

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}",
                headers=headers,
                params=params,
            )

        _raise_for_github_error(response, owner, repo)

        contents = response.json()
        if not isinstance(contents, list):
            raise HTTPException(status_code=400, detail="Path points to a file, not a directory.")

        return [
            GitHubFileSchema(
                name=item["name"],
                path=item["path"],
                type=item["type"],
                size=item.get("size"),
                sha=item["sha"],
                download_url=item.get("download_url"),
            )
            for item in contents
        ]

    async def get_file_content(
        self,
        user_id: uuid.UUID,
        owner: str,
        repo: str,
        path: str,
        ref: Optional[str] = None,
    ) -> GitHubFileContentSchema:
        """Get content of a specific file in the repository."""
        headers = await self._get_headers(user_id)
        params = {}
        if ref:
            params["ref"] = ref

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}",
                headers=headers,
                params=params,
            )

        _raise_for_github_error(response, owner, repo)

        data = response.json()
        if isinstance(data, list):
            raise HTTPException(status_code=400, detail="Path points to a directory, not a file.")

        raw_content = data.get("content", "")
        encoding = data.get("encoding", "base64")

        if encoding == "base64":
            decoded = base64.b64decode(raw_content).decode("utf-8", errors="replace")
        else:
            decoded = raw_content

        return GitHubFileContentSchema(
            path=data["path"],
            name=data["name"],
            content=decoded,
            encoding=encoding,
            size=data["size"],
            sha=data["sha"],
        )

    async def get_repo_comparison(
        self,
        user_id: uuid.UUID,
        owner: str,
        repo: str,
        base: str,
        head: str,
    ) -> dict:
        """Compare two refs to check if local is behind remote."""
        headers = await self._get_headers(user_id)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/compare/{base}...{head}",
                headers=headers,
            )

        _raise_for_github_error(response, owner, repo)
        return response.json()

    async def get_repo_comparison(
        self,
        user_id: uuid.UUID,
        owner: str,
        repo: str,
        base: str,
        head: str,
    ) -> dict:
        """Compare two refs to check if local is behind remote."""
        headers = await self._get_headers(user_id)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/compare/{base}...{head}",
                headers=headers,
            )

        _raise_for_github_error(response, owner, repo)
        return response.json()

        _raise_for_github_error(response, owner, repo)

        data = response.json()
        if isinstance(data, list):
            raise HTTPException(status_code=400, detail="Path points to a directory, not a file.")

        raw_content = data.get("content", "")
        encoding = data.get("encoding", "base64")

        if encoding == "base64":
            decoded = base64.b64decode(raw_content).decode("utf-8", errors="replace")
        else:
            decoded = raw_content

        return GitHubFileContentSchema(
            path=data["path"],
            name=data["name"],
            content=decoded,
            encoding=encoding,
            size=data["size"],
            sha=data["sha"],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _raise_for_github_error(response: httpx.Response, owner: str, repo: str) -> None:
    """Translate common GitHub API error codes into meaningful HTTP exceptions."""
    if response.status_code == 200:
        return
    if response.status_code == 401:
        raise HTTPException(
            status_code=401,
            detail="GitHub token is invalid or expired. Please reconnect your GitHub account.",
        )
    if response.status_code == 403:
        raise HTTPException(
            status_code=403,
            detail="Access denied by GitHub. Check repository permissions.",
        )
    if response.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{owner}/{repo}' not found or you do not have access.",
        )
    raise HTTPException(
        status_code=502,
        detail=f"Unexpected response from GitHub API: {response.status_code}",
    )