import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session
from src.features.ai.schema import (
    ArchitectureStoryRequest,
    ArchitectureStoryResponse,
    FlowStoryRequest,
    FlowStoryResponse,
    DiscoverFlowsRequest,
    DiscoverFlowsResponse,
    EnrichFlowRequest,
    StorybookGenerateRequest,
    StorybookResponse,
)
from src.features.ai.service import generate_architecture_story
from src.features.ai.flow_story_service import generate_flow_story
from src.features.ai.flow_discovery_service import discover_flows, enrich_flow
from src.features.ai.storybook_service import StorybookService


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


# ── Storybook ────────────────────────────────────────────────────────────────
@ai_router.post(
    "/storybook",
    response_model=StorybookResponse,
    operation_id="generateStorybook",
    summary="Generate a storybook for a connected repo, persist it, and return it",
)
async def generate_storybook_endpoint(
    request: StorybookGenerateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await StorybookService(db).generate(request.connected_repo_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate storybook | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@ai_router.get(
    "/storybook/{connected_repo_id}",
    response_model=StorybookResponse,
    operation_id="getStorybook",
    summary="Fetch the stored storybook for a connected repo",
)
async def get_storybook_endpoint(
    connected_repo_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await StorybookService(db).get(connected_repo_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch storybook | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@ai_router.post(
    "/storybook/{connected_repo_id}/refresh",
    response_model=StorybookResponse,
    operation_id="refreshStorybook",
    summary="Re-scan the stored repo, then regenerate and persist the storybook",
)
async def refresh_storybook_endpoint(
    connected_repo_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await StorybookService(db).refresh(connected_repo_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to refresh storybook | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))