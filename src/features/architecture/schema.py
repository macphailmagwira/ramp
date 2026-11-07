from typing import List, Optional

from pydantic import BaseModel


class StoryStep(BaseModel):
    title: str
    description: str
    highlight_nodes: List[str]
    highlight_edges: List[List[str]]
    insight: Optional[str] = None


class ArchitectureStoryRequest(BaseModel):
    repo_id: str
    files: List[str]
    edges: List[dict]


class ArchitectureStoryResponse(BaseModel):
    steps: List[StoryStep]
    summary: str
