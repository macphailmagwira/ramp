from fastapi import APIRouter

from src.common.router import router as common_router
from src.features.account.router import account_router
from src.features.ai.router import ai_router
from src.features.docs.router import docs_router
from src.features.github.router import github_router
from src.features.inbox.router import inbox_router
from src.features.user.router import user_router

router = APIRouter(prefix="/api/v1")
router.include_router(account_router, tags=["accounts"])
router.include_router(user_router,      tags=["users"])
router.include_router(common_router,    tags=["common"])
router.include_router(github_router,    tags=["github"])
router.include_router(ai_router, tags=["ai"])
router.include_router(docs_router, tags=["docs"])
router.include_router(inbox_router, tags=["inbox"])

