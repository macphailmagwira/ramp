from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import logging

from src.config import settings
from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX

logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.middleware.rate_limit")


def get_identifier(request: Request) -> str:
    """
    Get unique identifier for rate limiting.
    Prioritizes authenticated user, falls back to IP address.
    """
    
    ip = get_remote_address(request)
    logger.debug(f"Rate limiting by IP: {ip}")
    return f"ip:{ip}"


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Custom handler for rate limit exceeded errors.
    Returns JSON response with retry information.
    """
    logger.warning(
        f"Rate limit exceeded for {get_identifier(request)} "
        f"on {request.url.path}"
    )
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
            "detail": str(exc),
            "retry_after": 60,
        },
        headers={
            "Retry-After": "60",
            "X-RateLimit-Limit": str(exc.limit),
            "X-RateLimit-Remaining": "0",
        }
    )


class MockLimiter:
    """Mock limiter for testing that doesn't perform any rate limiting"""
    
    def __init__(self):
        self.enabled = True  # SlowAPIMiddleware checks this attribute
    
    def limit(self, *args, **kwargs):
        """Mock limit decorator that does nothing"""
        def decorator(func):
            return func
        return decorator


def setup_rate_limiting(app) -> None:
    """
    Configure rate limiting for the FastAPI application.
    Automatically skips middleware setup in development mode.
    
    Args:
        app: FastAPI application instance
    """
    from fastapi import FastAPI
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    
    # Attach limiter to app state
    app.state.limiter = limiter
    
    # Only add rate limiting middleware and handler if NOT using mock limiter
    if not isinstance(limiter, MockLimiter):
        # Add rate limit exception handler
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
        
        # Add SlowAPI middleware
        app.add_middleware(SlowAPIMiddleware)
        
        logger.info("✓ Rate limiting configured with SlowAPI middleware")
    else:
        logger.info("✓ Rate limiting disabled (development mode - using mock limiter)")


# Initialize limiter based on environment
# Disable rate limiting for development environment
if settings.ENVIRONMENT.upper() == "DEVELOPMENT":
    logger.info(f"Using mock limiter for {settings.ENVIRONMENT} environment (rate limiting disabled)")
    limiter = MockLimiter()
elif settings.REDIS_URL:
    logger.info(f"Using Redis for rate limiting: {settings.REDIS_URL}")
    limiter = Limiter(
        key_func=get_identifier,
        storage_uri=settings.REDIS_URL,
        default_limits=["1000/hour"],
    )
else:
    logger.warning("Using in-memory storage for rate limiting (not suitable for production)")
    limiter = Limiter(
        key_func=get_identifier,
        default_limits=["1000/hour"],
    )