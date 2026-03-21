import logging
from fastapi import APIRouter, HTTPException
from src.features.ai.schema import ArchitectureStoryRequest, ArchitectureStoryResponse
from src.features.ai.service import generate_architecture_story
from src.features.ai.schema import FlowStoryRequest, FlowStoryResponse
from src.features.ai.flow_story_service import generate_flow_story
from src.features.ai.flow_discovery_service import discover_flows, enrich_flow
from src.features.ai.schema import (
    ArchitectureStoryRequest,
    ArchitectureStoryResponse,
    FlowStoryRequest,
    FlowStoryResponse,
    DiscoverFlowsRequest,
    DiscoverFlowsResponse,
    EnrichFlowRequest,
)
from src.features.ai.flow_story_service import generate_flow_story
from src.features.ai.flow_discovery_service import discover_flows, enrich_flow


logger = logging.getLogger("api-main.ai.router")

ai_router = APIRouter(prefix="/ai", tags=["ai"])


@ai_router.post(
    "/architecture-story",
    response_model=ArchitectureStoryResponse,
    operation_id="generateArchitectureStory",
)
async def architecture_story(request: ArchitectureStoryRequest):
    try:
        return await generate_architecture_story(
            files=request.files,
            edges=request.edges,
        )
    except Exception as e:
        logger.exception("Failed to generate architecture story | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    

 
@ai_router.post(
    "/flow-story",
    response_model=FlowStoryResponse,
    operation_id="generateFlowStory",
    summary="Generate a narrative flow story from a raw function call graph",
)
async def flow_story(request: FlowStoryRequest):
    try:
        return await generate_flow_story(request)
    except Exception as e:
        logger.exception("Failed to generate flow story | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))
     
@ai_router.post(
    "/discover-flows",
    response_model=DiscoverFlowsResponse,
    operation_id="discoverFlows",
)
async def discover_flows_endpoint(request: DiscoverFlowsRequest):
    try:
        return await discover_flows(request)
    except Exception as e:
        logger.exception("Failed to discover flows | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@ai_router.post(
    "/enrich-flow",
    response_model=FlowStoryResponse,
    operation_id="enrichFlow",
)
async def enrich_flow_endpoint(request: EnrichFlowRequest):
    try:
        return await enrich_flow(request)
    except Exception as e:
        logger.exception("Failed to enrich flow | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))