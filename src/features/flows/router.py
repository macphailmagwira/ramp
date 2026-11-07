import logging

from fastapi import APIRouter, HTTPException

from src.features.flows.flow_discovery_service import discover_flows, enrich_flow
from src.features.flows.flow_story_service import generate_flow_story
from src.features.flows.schema import (
    DiscoverFlowsRequest,
    DiscoverFlowsResponse,
    EnrichFlowRequest,
    FlowStoryRequest,
    FlowStoryResponse,
)


logger = logging.getLogger("api-main.ai.flows.router")

flows_router = APIRouter(tags=["ai-flows"])


@flows_router.post(
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


@flows_router.post(
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


@flows_router.post(
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
