import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session
from src.features.storybook.schema import (
    StorybookFileContentResponse,
    StorybookGenerateRequest,
    StorybookResponse,
)
from src.features.storybook.service import StorybookService


logger = logging.getLogger("api-main.ai.storybook.router")

storybook_router = APIRouter(tags=["ai-storybook"])


@storybook_router.post(
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
        return StorybookResponse(book=await StorybookService(db).generate(request.connected_repo_id))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate storybook | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@storybook_router.get(
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
        return StorybookResponse(book=await StorybookService(db).get(connected_repo_id))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch storybook | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@storybook_router.post(
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
        return StorybookResponse(book=await StorybookService(db).refresh(connected_repo_id))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to refresh storybook | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@storybook_router.get(
    "/storybook/{connected_repo_id}/file-content",
    response_model=StorybookFileContentResponse,
    operation_id="getStorybookFileContent",
    summary="Fetch the full indexed content of a file referenced by the storybook",
)
async def get_storybook_file_content_endpoint(
    connected_repo_id: UUID,
    path: str = Query(..., description="File path within the repository, as referenced by the storybook"),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await StorybookService(db).get_file_content(connected_repo_id, path)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch storybook file content | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))
