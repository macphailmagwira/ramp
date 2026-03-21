import time
import json
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from src.auth.cognito import verify_cognito_jwt
from src.config.constants import PUBLIC_PATHS
from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        process_time = (time.time() - start_time) * 1000

        log_data = {
            "method": request.method,
            "url": request.url.path,
            "status_code": response.status_code,
            "process_time_ms": round(process_time, 2),
            "client_ip": request.client.host if request.client else None
        }

        print(json.dumps(log_data))          
        logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.{__name__}")
        logger.info(json.dumps(log_data))


        return response

 