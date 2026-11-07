import logging

from fastapi import APIRouter

from src.features.architecture.router import architecture_router
from src.features.flows.router import flows_router
from src.features.storybook.router import storybook_router


logger = logging.getLogger("api-main.ai.router")

ai_router = APIRouter(prefix="/ai", tags=["ai"])
ai_router.include_router(architecture_router)
ai_router.include_router(flows_router)
ai_router.include_router(storybook_router)
