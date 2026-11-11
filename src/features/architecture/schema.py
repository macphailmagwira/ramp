from typing import List, Optional

from pydantic import BaseModel


class ArchNode(BaseModel):
    id: str
    label: str
    type: str
    description: str = ""
    file_path: Optional[str] = None
    insight: Optional[str] = None
    children: List["ArchNode"] = []
    edges: List[List[str]] = []


ArchNode.model_rebuild()


class ArchitectureStoryRequest(BaseModel):
    repo_id: str
    files: List[str]
    edges: List[dict]


class ArchitectureGraphResponse(BaseModel):
    summary: str
    root: ArchNode
