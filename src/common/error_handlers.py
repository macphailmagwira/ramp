import logging

from fastapi.responses import JSONResponse

logger = logging.getLogger(f"api.{__name__}")


async def generic_exception_handler(request, exc):
    logger.error(f"Unhandled error: {exc}", exc_info=True)

    return JSONResponse(status_code=500, content={"error": "INTERNAL_SERVER_ERROR"})
