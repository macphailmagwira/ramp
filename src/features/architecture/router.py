import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session
from src.features.architecture.repository import ArchitectureResultRepository
from src.features.architecture.schema import ArchitectureGraphResponse
from src.features.architecture.service import generate_architecture_for_repo

logger = logging.getLogger("api-main.ai.architecture.router")

architecture_router = APIRouter(tags=["ai-architecture"])


@architecture_router.get(
    "/architecture-story/{connected_repo_id}",
    response_model=ArchitectureGraphResponse,
    operation_id="getArchitectureStory",
    summary="Fetch the stored architecture story for a connected repo",
)
async def get_architecture_story(
    connected_repo_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        row = await ArchitectureResultRepository(db).get_latest(connected_repo_id)
        if not row:
            raise HTTPException(status_code=404, detail="Architecture not found for this repository.")
        return ArchitectureGraphResponse(**json.loads(row.graph))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch architecture story | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@architecture_router.post(
    "/architecture-story/{connected_repo_id}",
    response_model=ArchitectureGraphResponse,
    operation_id="generateArchitectureStory",
    summary="Ensure an architecture story exists for a connected repo (cached if already stored), persist it, and return it",
)
async def generate_architecture_story_endpoint(
    connected_repo_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await generate_architecture_for_repo(db, connected_repo_id, regenerate=False)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate architecture story | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@architecture_router.post(
    "/architecture-story/{connected_repo_id}/regenerate",
    response_model=ArchitectureGraphResponse,
    operation_id="regenerateArchitectureStory",
    summary="Rebuild the architecture story for a connected repo from scratch, persist it, and return it",
)
async def regenerate_architecture_story(
    connected_repo_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await generate_architecture_for_repo(db, connected_repo_id, regenerate=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to regenerate architecture story | error=%s", str(e))
        raise HTTPException(status_code=500, detail=str(e))
