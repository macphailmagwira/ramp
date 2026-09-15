import uuid
from typing import List, Optional

import logging
import asyncio
from fastapi import APIRouter, Depends, Query, HTTPException

from fastapi.responses import RedirectResponse
from starlette import status

from src.features.github.schema import (
    ArchitectureGraphSchema,
    ConnectedRepositoryRetrieveSchema,
    ConnectRepositoryRequestSchema,
    FlowGraphSchema,
    GitHubBranchSchema,
    GitHubCommitSchema,
    GitHubFileContentSchema,
    GitHubFileSchema,
    GitHubOAuthLoginResponseSchema,
    GitHubRepoListSchema, FlowGraphSchema,
    OverviewResponseSchema,
    ScanStatusResponseSchema,
)
from src.features.github.services.architecture_service import ArchitectureService
from src.features.github.services.flow_service import FlowService
from src.features.github.services.service import (
    GitHubOAuthService,
    GitHubRepositoryAccessService,
    GitHubRepositoryService,
)
from src.features.github.services.overview_service import OverviewService
from src.middleware.user_context import get_current_user
from src.config import settings
from jose import JWTError
from src.auth.jwt import decode_access_token



from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db
from src.features.github.schema import ArchitectureGraphSchema
from src.features.github.services.architecture_service import ArchitectureService
from src.middleware.user_context import get_current_user

logger = logging.getLogger("github.router")

github_router = APIRouter(prefix="/github", tags=["github"])


# ---------------------------------------------------------------------------
# 1. GitHub OAuth Login — redirect user to GitHub authorization page
# ---------------------------------------------------------------------------


@github_router.get(
    "/oauth/login",
    status_code=status.HTTP_302_FOUND,
    operation_id="githubOAuthLogin",
    summary="Redirect to GitHub OAuth authorization page",
)
async def github_oauth_login(
    state: Optional[str] = Query(None, description="Optional CSRF state token"),
    service: GitHubOAuthService = Depends(),
):
    logger.info("GitHub OAuth login initiated. state=%s", state)
    """
    Redirects the user to GitHub's OAuth authorization page.
    After the user grants access, GitHub redirects back to the configured
    GITHUB_REDIRECT_URI with a short-lived authorization code.
    """
    authorization_url = service.get_authorization_url(state=state)
    return RedirectResponse(url=authorization_url)


# ---------------------------------------------------------------------------
# 2. GitHub OAuth Callback — exchange code for token
# ---------------------------------------------------------------------------




@github_router.get(
    "/oauth/callback",
    operation_id="githubOAuthCallback",
)
async def github_oauth_callback(
    code: str = Query(...),
    state: str = Query(..., description="Ramp auth JWT passed through from /oauth/login"),
    service: GitHubOAuthService = Depends(),
):
    # A browser top-level redirect from GitHub cannot carry a Bearer header,
    # so the Ramp user identity is carried in the `state` param as a signed JWT.
    try:
        claims = decode_access_token(state)
        user_id = uuid.UUID(claims["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired state token. Restart the GitHub connect flow.",
        )

    logger.info("GitHub OAuth callback received. code=%s, user_id=%s", code, user_id)
    await service.handle_callback(code=code, user_id=user_id)

    return RedirectResponse(url=f"{settings.FRONTEND_URL}?github=connected")




@github_router.delete(
    "/oauth/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="githubOAuthDisconnect",
    summary="Disconnect GitHub account",
)
async def github_oauth_disconnect(
    current_user=Depends(get_current_user),
    service: GitHubOAuthService = Depends(),
):
    """Remove the stored GitHub OAuth token for the current user."""
    logger.info("GitHub OAuth disconnect requested for user_id=%s", current_user.id)
    await service.disconnect(user_id=current_user.id)


# ---------------------------------------------------------------------------
# 3. Fetch User Repositories from GitHub API
# ---------------------------------------------------------------------------


@github_router.get(
    "/repositories",
    response_model=GitHubRepoListSchema,
    operation_id="listGitHubRepositories",
    summary="List user's GitHub repositories",
)
async def list_github_repositories(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(30, ge=1, le=100, description="Results per page"),
    visibility: str = Query("all", description="Filter: all | public | private"),
    current_user=Depends(get_current_user),
    service: GitHubRepositoryService = Depends(),
):
    logger.info("Listing GitHub repositories for user_id=%s: page=%s, per_page=%s, visibility=%s", current_user.id, page, per_page, visibility)
    """
    Returns the list of GitHub repositories accessible to the current user.
    Requires a connected GitHub account (OAuth flow must be completed first).
    Powers the Select Repository screen.
    """
    return await service.list_user_repositories(
        user_id=current_user.id,
        page=page,
        per_page=per_page,
        visibility=visibility,
    )


# ---------------------------------------------------------------------------
# 4. Connected Repositories — connect / list / disconnect
# ---------------------------------------------------------------------------


@github_router.post(
    "/connected-repositories",
    response_model=ConnectedRepositoryRetrieveSchema,
    status_code=status.HTTP_201_CREATED,
    operation_id="connectRepository",
    summary="Connect a repository to Ramp",
)
async def connect_repository(
    request: ConnectRepositoryRequestSchema,
    current_user=Depends(get_current_user),
    service: GitHubRepositoryService = Depends(),
):
    logger.info("Connecting repository for user_id=%s: owner=%s, name=%s", current_user.id, request.owner, request.name)
    """
    Connect a GitHub repository to Ramp for the current user.
    Stores repository metadata (owner, name, provider, connection details).
    Prevents duplicate connections for the same user + repo combination.
    """
    return await service.connect_repository(
        user_id=current_user.id,
        request=request,
    )


@github_router.get(
    "/connected-repositories",
    response_model=List[ConnectedRepositoryRetrieveSchema],
    operation_id="listConnectedRepositories",
    summary="List repositories connected by the current user",
)
async def list_connected_repositories(
    current_user=Depends(get_current_user),
    service: GitHubRepositoryService = Depends(),
):
    logger.info("Listing connected repositories for user_id=%s", current_user.id)
    """Returns all active repository connections for the current user."""
    return await service.list_connected_repositories(user_id=current_user.id)


@github_router.delete(
    "/connected-repositories/{repo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="disconnectRepository",
    summary="Disconnect a connected repository",
)
async def disconnect_repository(
    repo_id: uuid.UUID,
    current_user=Depends(get_current_user),
    service: GitHubRepositoryService = Depends(),
):
    """Soft-deletes a connected repository record."""
    logger.info("Disconnecting repository %s for user_id=%s", repo_id, current_user.id)
    await service.disconnect_repository(repo_id=repo_id, user_id=current_user.id)


# ---------------------------------------------------------------------------
# 5. Repository Access — branches, commits, files
# ---------------------------------------------------------------------------


@github_router.get(
    "/repo/{owner}/{repo}/branches",
    response_model=List[GitHubBranchSchema],
    operation_id="listRepoBranches",
    summary="List branches in a connected repository",
)
async def list_repo_branches(
    owner: str,
    repo: str,
    current_user=Depends(get_current_user),
    service: GitHubRepositoryAccessService = Depends(),
):
    logger.info("Listing branches for repo %s/%s, user_id=%s", owner, repo, current_user.id)
    """Lists all branches in the specified repository."""
    return await service.list_branches(user_id=current_user.id, owner=owner, repo=repo)


@github_router.get(
    "/repo/{owner}/{repo}/commits",
    response_model=List[GitHubCommitSchema],
    operation_id="listRepoCommits",
    summary="List recent commits in a repository",
)
async def list_repo_commits(
    owner: str,
    repo: str,
    branch: Optional[str] = Query(None, description="Branch name or commit SHA"),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    current_user=Depends(get_current_user),
    service: GitHubRepositoryAccessService = Depends(),
):
    logger.info("Listing commits for repo %s/%s, branch=%s, page=%s, per_page=%s, user_id=%s", owner, repo, branch, page, per_page, current_user.id)
    """Returns recent commits for the given repository and optional branch."""
    return await service.list_commits(
        user_id=current_user.id,
        owner=owner,
        repo=repo,
        branch=branch,
        per_page=per_page,
        page=page,
    )


@github_router.get(
    "/repo/{owner}/{repo}/files",
    response_model=List[GitHubFileSchema],
    operation_id="listRepoFiles",
    summary="List files and directories at a path",
)
async def list_repo_files(
    owner: str,
    repo: str,
    path: str = Query("", description="Directory path (empty = root)"),
    ref: Optional[str] = Query(None, description="Branch, tag, or commit SHA"),
    current_user=Depends(get_current_user),
    service: GitHubRepositoryAccessService = Depends(),
):
    logger.info("Listing files for repo %s/%s, path=%s, ref=%s, user_id=%s", owner, repo, path, ref, current_user.id)
    """
    Lists files and directories at the given path within a repository.
    Use path="" for the root directory.
    """
    return await service.list_files(
        user_id=current_user.id, owner=owner, repo=repo, path=path, ref=ref
    )


@github_router.get(
    "/repo/{owner}/{repo}/file-content",
    response_model=GitHubFileContentSchema,
    operation_id="getRepoFileContent",
    summary="Get the decoded content of a file",
)
async def get_repo_file_content(
    owner: str,
    repo: str,
    path: str = Query(..., description="File path within the repository"),
    ref: Optional[str] = Query(None, description="Branch, tag, or commit SHA"),
    current_user=Depends(get_current_user),
    service: GitHubRepositoryAccessService = Depends(),
):
    """
    Fetches and returns the decoded content of a specific file.
    Base64-encoded content from GitHub is automatically decoded to UTF-8.
    """
    logger.info("Fetching file content for repo %s/%s, path=%s, ref=%s, user_id=%s", owner, repo, path, ref, current_user.id)
    return await service.get_file_content(
        user_id=current_user.id, owner=owner, repo=repo, path=path, ref=ref
    )





@github_router.get(
    "/{repo_id}/architecture",
    response_model=ArchitectureGraphSchema,
    operation_id="getRepositoryArchitecture",
)
async def get_architecture(
    repo_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ArchitectureService(db)
    return await service.get_graph(repo_id)





@github_router.get(
    "/{repo_id}/flow",
    response_model=FlowGraphSchema,
    operation_id="getRepositoryFlow",
)
async def get_repository_flow(
    repo_id: uuid.UUID,
    entry_function: Optional[str] = Query(None),
    entry_file: Optional[str] = Query(None),
    feature_name: Optional[str] = Query(None),
    max_depth: int = Query(10, ge=1, le=20),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info("Generating flow for repo_id=%s, entry_function=%s, entry_file=%s, feature_name=%s, max_depth=%s, user_id=%s", repo_id, entry_function, entry_file, feature_name, max_depth, current_user.id)
    service = FlowService(db)
    return await service.get_flow(
        connected_repo_id=repo_id,
        entry_function=entry_function,
        entry_file=entry_file,
        feature_name=feature_name,
        max_depth=max_depth,
    )


# ---------------------------------------------------------------------------
# 6. Overview — aggregated repo stats and recent commits
# ---------------------------------------------------------------------------


@github_router.get(
    "/{repo_id}/overview",
    response_model=OverviewResponseSchema,
    operation_id="getRepositoryOverview",
    summary="Get overview data for a connected repository",
)
async def get_repository_overview(
    repo_id: uuid.UUID,
    since: Optional[str] = Query(None, description="Start date (ISO 8601, e.g. 2025-01-01)"),
    until: Optional[str] = Query(None, description="End date (ISO 8601, e.g. 2025-12-31)"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns aggregated overview data: stats from architecture/flow graphs and recent commits."""
    logger.info("Fetching overview for repo_id=%s, since=%s, until=%s, user_id=%s", repo_id, since, until, current_user.id)
    service = OverviewService(db)
    return await service.get_overview(repo_id, current_user.id, since, until)


# ---------------------------------------------------------------------------
# 7. Scan status polling & rescan
# ---------------------------------------------------------------------------


@github_router.get(
    "/{repo_id}/scan-status",
    response_model=ScanStatusResponseSchema,
    operation_id="getScanStatus",
    summary="Get scan progress for a connected repository",
)
async def get_scan_status(
    repo_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns the current scan status and progress percentage."""
    from src.features.github.models import ConnectedRepository
    from sqlalchemy import select
    from fastapi import HTTPException

    result = await db.execute(
        select(ConnectedRepository).where(
            ConnectedRepository.id == repo_id,
            ConnectedRepository.user_id == current_user.id,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")

    step_map = {
        "pending": "Waiting to start",
        "cloning": "Cloning repository",
        "indexing_files": "Reading repository structure",
        "mapping_deps": "Mapping dependencies",
        "extracting_symbols": "Detecting services",
        "building_call_graph": "Building call graph",
        "generating_docs": "Creating documentation",
        "complete": "Scan complete",
        "failed": "Scan failed",
    }

    return ScanStatusResponseSchema(
        status=repo.scan_status,
        progress=repo.scan_progress,
        current_step=step_map.get(repo.scan_status, repo.scan_status),
    )


@github_router.post(
    "/{repo_id}/rescan",
    response_model=ScanStatusResponseSchema,
    operation_id="rescanRepository",
    summary="Trigger a re-scan of a connected repository",
)
async def rescan_repository(
    repo_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Triggers a new scan for an already-connected repository."""
    from src.features.github.models import ConnectedRepository
    from src.features.github.services.service import GitHubRepositoryService
    from src.features.github.repository import GitHubOAuthTokenRepository
    from sqlalchemy import select
    from fastapi import HTTPException

    result = await db.execute(
        select(ConnectedRepository).where(
            ConnectedRepository.id == repo_id,
            ConnectedRepository.user_id == current_user.id,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")

    token_repo = GitHubOAuthTokenRepository(db)
    token = await token_repo.get_by_user_id(user_id=current_user.id)
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token not found.")

    repo.scan_status = "pending"
    repo.scan_progress = 0
    await db.commit()

    from src.features.github.tasks import scan_repository_task
    scan_repository_task.delay( # type: ignore[attr-defined]
        connected_repo_id=str(repo.id),
        user_id=str(current_user.id),
        clone_url=repo.clone_url,
        access_token=token.access_token,
        default_branch=repo.default_branch,
    )
    

    return ScanStatusResponseSchema(
        status="pending",
        progress=0,
        current_step="Waiting to start",
    )


@github_router.get(
    "/{repo_id}/sync-status",
    operation_id="getSyncStatus",
    summary="Check if repository has new commits since last scan",
)
async def get_sync_status(
    repo_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if the remote repository has commits that haven't been scanned yet."""
    from src.features.github.models import ConnectedRepository
    from src.features.github.services.service import GitHubRepositoryService
    from src.features.github.repository import GitHubOAuthTokenRepository
    from sqlalchemy import select
    from fastapi import HTTPException

    result = await db.execute(
        select(ConnectedRepository).where(
            ConnectedRepository.id == repo_id,
            ConnectedRepository.user_id == current_user.id,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")

    token_repo = GitHubOAuthTokenRepository(db)
    token = await token_repo.get_by_user_id(user_id=current_user.id)
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token not found.")

    access_service = GitHubRepositoryAccessService(token_repository=token_repo)
    try:
        comparison = await access_service.get_repo_comparison(
            user_id=current_user.id,
            owner=repo.owner,
            repo=repo.name,
            base=repo.default_branch,
            head=repo.default_branch,
        )
        behind_by = comparison.get("behind_by", 0)
        return {"is_behind": behind_by > 0, "behind_by": behind_by}
    except Exception:
        return {"is_behind": False, "behind_by": 0}


