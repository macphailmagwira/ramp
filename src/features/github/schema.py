import uuid
from datetime import datetime
from typing import Any, List, Optional,Literal
from pydantic import BaseModel, ConfigDict, Field



class GitHubOAuthTokenCreateSchema(BaseModel):
    user_id: uuid.UUID
    access_token: str
    token_type: str = "bearer"
    scope: Optional[str] = None
    github_user_id: Optional[str] = None
    github_username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GitHubOAuthTokenRetrieveSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    token_type: str
    scope: Optional[str] = None
    github_user_id: Optional[str] = None
    github_username: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GitHubRepoSchema(BaseModel):
    id: int
    name: str
    full_name: str
    owner: str
    description: Optional[str] = None
    is_private: bool
    clone_url: str
    default_branch: str
    updated_at: Optional[str] = None
    language: Optional[str] = None
    stargazers_count: int = 0
    forks_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class GitHubRepoListSchema(BaseModel):
    repositories: List[GitHubRepoSchema]
    total: int

    model_config = ConfigDict(from_attributes=True)


class ConnectRepositoryRequestSchema(BaseModel):
    repo_id: str = Field(..., description="GitHub numeric repository ID")
    owner: str
    name: str
    full_name: str
    clone_url: Optional[str] = None
    default_branch: str = "main"
    is_private: bool = False
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ConnectedRepositoryRetrieveSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    repo_id: str
    owner: str
    name: str
    full_name: str
    clone_url: Optional[str] = None
    default_branch: str
    is_private: bool
    description: Optional[str] = None
    is_active: bool
    scan_status: str = "pending"
    scan_progress: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScanStatusResponseSchema(BaseModel):
    status: str
    progress: int
    current_step: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ScanStatusResponseSchema(BaseModel):
    status: str
    progress: int
    current_step: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GitHubOAuthLoginResponseSchema(BaseModel):
    github_username: Optional[str] = None
    github_user_id: Optional[str] = None
    token: GitHubOAuthTokenRetrieveSchema

    model_config = ConfigDict(from_attributes=True)


class GitHubBranchSchema(BaseModel):
    name: str
    sha: str
    protected: bool = False

    model_config = ConfigDict(from_attributes=True)


class GitHubCommitSchema(BaseModel):
    sha: str
    message: str
    author_name: str
    author_email: str
    date: str
    url: str

    model_config = ConfigDict(from_attributes=True)


class OverviewCommitSchema(BaseModel):
    sha: str
    message: str
    author: str
    date: str
    type: str  # 'feat', 'fix', or 'other'

    model_config = ConfigDict(from_attributes=True)


class OverviewStatsSchema(BaseModel):
    files: int
    folders: int
    functions: int
    dependencies: int


class OverviewResponseSchema(BaseModel):
    stats: OverviewStatsSchema
    recent_commits: List[OverviewCommitSchema]
    language: Optional[str] = None
    default_branch: str
    description: Optional[str] = None


class OverviewCommitSchema(BaseModel):
    sha: str
    message: str
    author: str
    date: str
    type: str  # 'feat', 'fix', or 'other'

    model_config = ConfigDict(from_attributes=True)


class OverviewStatsSchema(BaseModel):
    files: int
    folders: int
    functions: int
    dependencies: int


class OverviewResponseSchema(BaseModel):
    stats: OverviewStatsSchema
    recent_commits: List[OverviewCommitSchema]
    language: Optional[str] = None
    default_branch: str
    description: Optional[str] = None


class GitHubFileSchema(BaseModel):
    name: str
    path: str
    type: str
    size: Optional[int] = None
    sha: str
    download_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GitHubFileContentSchema(BaseModel):
    path: str
    name: str
    content: str
    encoding: str
    size: int
    sha: str

    model_config = ConfigDict(from_attributes=True)



class ArchNodeSchema(BaseModel):
    id: str
    type: Literal["folder", "file"]
    file_count: int = 0


class ArchEdgeSchema(BaseModel):
    source: str
    target: str
    weight: int = 1  # number of file-level deps between these folders


class ArchitectureGraphSchema(BaseModel):
    # Folder level
    nodes: List[ArchNodeSchema]
    edges: List[ArchEdgeSchema]
    # File level
    file_nodes: List[ArchNodeSchema]
    file_edges: List[ArchEdgeSchema]


 
class FlowNodeSchema(BaseModel):
    id: str
    label: str
    node_type: str             
    file_path: Optional[str] = None
    file_id: Optional[str] = None
    is_async: bool = False
    line_start: Optional[int] = None
 
 
class FlowEdgeSchema(BaseModel):
    source: str
    target: str
    edge_type: str              
 
 
class FlowGraphSchema(BaseModel):
    entry_point: Optional[str] = None
    function_nodes: list[dict[str, Any]]
    function_edges: list[dict[str, Any]]
    file_nodes: list[dict[str, Any]]
    file_edges: list[dict[str, Any]]
 



