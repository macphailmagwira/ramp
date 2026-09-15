import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX
from src.config.logging_config import configure_logging
from src.middleware.cors import setup_cors
from src.middleware.rate_limit import setup_rate_limiting
from src.middleware.request_logging import RequestLoggingMiddleware
from src.middleware.user_context import UserContextMiddleware
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse

from .api.v1_router import router
from .common.error_handlers import generic_exception_handler
from .config import settings

# ------------------------------
# Configure logging
# ------------------------------
configure_logging()

logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.{__name__}")
logger.info("Starting StitchSense API Main")
logger.info(f"Environment: {settings.ENVIRONMENT}")


# ------------------------
# FastAPI app setup
# ------------------------
app = FastAPI(
    title="Ramp API Main",
    description="Main API for Ramp platform features.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.include_router(router)

# ------------------------------
# Rate Limiting Setup
# ------------------------------c
setup_rate_limiting(app)


# Exception handlers
app.add_exception_handler(Exception, generic_exception_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Parse the errors to a custom format
    custom_errors = []
    for error in exc.errors():
        custom_errors.append(
            {
                "field": " -> ".join([str(loc) for loc in error["loc"]]),
                "message": error["msg"],
                "input": error.get("input"),
            }
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": custom_errors},
    )


# Middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(UserContextMiddleware)

# Setup CORS last so it is the OUTERMOST middleware and its headers wrap
# every response (including those short-circuited by inner auth middleware).
setup_cors(app, settings.CORS_ORIGINS)


@app.get("/")
async def read_root():
    return {"message": "Welcome to Ramp API Main"}


# from strawberry.fastapi import GraphQLRouter  # uncomment if you actually use this
# from .graphql.schema import schema           # adjust path to your schema


# If you actually have GraphQL set up, uncomment and fix imports
# graphql_app = GraphQLRouter(schema)
# app.include_router(graphql_app, prefix="/graphql")
# graphql_app = GraphQLRouter(schema)
