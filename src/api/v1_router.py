from fastapi import APIRouter
from src.common.router import router as common_router
from src.features.user.router import user_router
from src.features.github.router import github_router
from src.features.ai.router import ai_router


router = APIRouter(prefix="/api/v1")
router.include_router(user_router,      tags=["users"])
router.include_router(common_router,    tags=["common"])
router.include_router(github_router,    tags=["github"])
router.include_router(ai_router, tags=["ai"])

