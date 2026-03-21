import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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
)
from src.features.github.services.architecture_service import ArchitectureService
from src.features.github.services.flow_service import FlowService
from src.features.github.services.service import (
    GitHubOAuthService,
    GitHubRepositoryAccessService,
    GitHubRepositoryService,
)
from src.middleware.user_context import get_current_user
from src.config import settings



from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import get_db
from src.features.github.schema import ArchitectureGraphSchema
from src.features.github.services.architecture_service import ArchitectureService
from src.middleware.user_context import get_current_user

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
    state: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    service: GitHubOAuthService = Depends(),
):
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="User not found in database.")
    
    await service.handle_callback(code=code, user_id=current_user.id)
    
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
    service = FlowService(db)
    return await service.get_flow(
        connected_repo_id=repo_id,
        entry_function=entry_function,
        entry_file=entry_file,
        feature_name=feature_name,
        max_depth=max_depth,
    )