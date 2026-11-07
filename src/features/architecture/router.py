import logging

from fastapi import APIRouter, HTTPException

from src.features.architecture.schema import (
    ArchitectureStoryRequest,
    ArchitectureStoryResponse,
)
from src.features.architecture.service import generate_architecture_story


logger = logging.getLogger("api-main.ai.architecture.router")

architecture_router = APIRouter(tags=["ai-architecture"])


@architecture_router.post(
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
