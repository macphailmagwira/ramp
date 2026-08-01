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



class FlowStoryStepRequest(BaseModel):
    id: str
    label: str
    node_type: str          # function | method | class | file
    file_path: Optional[str] = None
    is_async: bool = False
    line_start: Optional[int] = None


class FlowStoryEdgeRequest(BaseModel):
    source: str             # node id
    target: str             # node id
    edge_type: str          # calls | file_import



class DiscoverFlowsRequest(BaseModel):
    repo_id: str
    function_nodes: list[FlowStoryStepRequest]
    function_edges: list[FlowStoryEdgeRequest]
 
 
class DiscoveredFlowSummary(BaseModel):
    id: str
    name: str
    description: str
    # just names for the sidebar — no full step data yet
    function_count: int
 
 
class DiscoverFlowsResponse(BaseModel):
    flows: list[DiscoveredFlowSummary]
 
 
# ── Enrich: get full narrative for one flow ───────────────────────────────────
 
class EnrichFlowRequest(BaseModel):
    repo_id: str
    flow_name: str                          # which flow to enrich
    function_nodes: list[FlowStoryStepRequest]   # the FULL graph
    function_edges: list[FlowStoryEdgeRequest]   # the FULL graph
 



class FlowNodeSchema(BaseModel):
    id: str
    label: str
    node_type: str
    file_path: Optional[str] = None
    file_id: Optional[str] = None
    is_async: bool = False
    line_start: Optional[int] = None
    source_code: Optional[str] = None          # ← NEW: actual function source
 
 
class FlowEdgeSchema(BaseModel):
    source: str
    target: str
    edge_type: str
 
 
class FlowStoryRequest(BaseModel):
    feature_name: Optional[str] = None
    function_nodes: list[FlowNodeSchema]
    function_edges: list[FlowEdgeSchema]
 
 
class FlowStoryStep(BaseModel):
    id: str
    name: str
    description: str
    type: str
    file: Optional[str] = None
    line: Optional[int] = None
    is_async: bool = False
    insight: Optional[str] = None
 
 
class FlowStoryResponse(BaseModel):
    name: str
    description: str
    entry_point: Optional[str] = None
    risks: list[str] = []                      # ← NEW: risks/gotchas section
    steps: list[FlowStoryStep]
 