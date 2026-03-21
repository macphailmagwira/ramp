import uuid
import asyncio
import logging

from src.core.celery_app import app
from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX
from src.db.session import AsyncSessionLocal
from src.features.github.services.scanner_service import RepoScannerService

logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.scanner.tasks")


@app.task(
    bind=True,
    name="scanner.scan_repository",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def scan_repository_task( 
    self,
    connected_repo_id: str,
    user_id: str,
    clone_url: str,
    access_token: str,
    default_branch: str = "main",
):
    logger.info(
        "Starting repo scan | repo=%s user=%s branch=%s",
        connected_repo_id, user_id, default_branch,
    )

    async def _process():
        logger.debug("Opening DB session for repo=%s", connected_repo_id)
        async with AsyncSessionLocal() as db:
            svc = RepoScannerService(db)

            logger.debug(
                "Handing off to RepoScannerService | repo=%s clone_url=%s",
                connected_repo_id, clone_url,
            )

            count = await svc.scan(
                connected_repo_id=uuid.UUID(connected_repo_id),
                user_id=uuid.UUID(user_id),
                clone_url=clone_url,
                access_token=access_token,
                default_branch=default_branch,
            )

            logger.debug("DB session closing for repo=%s", connected_repo_id)
            return count

    try:
        count = asyncio.run(_process())
        logger.info(
            "Repo scan complete | repo=%s user=%s files_indexed=%d",
            connected_repo_id, user_id, count,
        )
        return {"status": "success", "files_indexed": count}

    except Exception as exc:
        logger.exception(
            "Repo scan failed | repo=%s user=%s attempt=%d/%d error=%s",
            connected_repo_id, user_id,
            self.request.retries + 1, self.max_retries + 1,
            str(exc),
        )
        raise self.retry(exc=exc)