from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from typing import List

from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX

logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.middleware.cors")


def setup_cors(app: FastAPI, allowed_origins: List[str]) -> None:
    """
    Configure CORS middleware for the FastAPI application.
    
    Args:
        app: FastAPI application instance
        allowed_origins: List of allowed origin URLs
    """
    
    logger.info(f"Setting up CORS with origins: {allowed_origins}")
    
    # Validate 
    if not allowed_origins:
        logger.warning("No CORS origins configured! This may block cross-origin requests.")
    
    # Check for wildcard in production
    if "*" in allowed_origins:
        logger.warning(
            "⚠️  WILDCARD CORS origin '*' detected! "
            "This is insecure for production and should only be used in development."
        )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-CSRF-Token",
            "X-Request-ID",
        ],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
        max_age=3600,  # Cache preflight requests for 1 hour
    )
    
    logger.info("✓ CORS middleware configured successfully")
