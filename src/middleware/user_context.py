import logging

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX, PUBLIC_PATHS
from src.db.session import get_db
from src.features.user.models import User
from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.middleware")


class EnrichedUserContext:
    def __init__(self, cognito_data: dict, db_user=None):
        self.cognito_data = cognito_data
        self.db_user = db_user

    @property
    def id(self):
        return self.db_user.id if self.db_user else None

    @property
    def email(self) -> str:
        return self.db_user.email if self.db_user else self.cognito_data.get("email")

    @property
    def first_name(self) -> str:
        return self.db_user.first_name if self.db_user else None

    @property
    def last_name(self) -> str:
        return self.db_user.last_name if self.db_user else None

    def to_dict(self) -> dict:
        return {
            "user_id": str(self.id) if self.id else None,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
        }


class UserContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            request.state.user = None
            request.state.db = None
            return await call_next(request)

        # --- AUTH ENABLED: uncomment to enable JWT verification ---
        # from src.auth.cognito import verify_cognito_jwt
        # auth_header = request.headers.get("authorization")
        # if not auth_header or not auth_header.startswith("Bearer "):
        #     return JSONResponse(status_code=401, content={"detail": "Missing Authorization header"})
        # token = auth_header.split(" ")[1]
        # cognito_user = verify_cognito_jwt(token)
        # cognito_email = cognito_user.get("email")
        # --- END AUTH ENABLED ---

        # --- AUTH DISABLED: remove when enabling auth above ---
        cognito_user = {"sub": "dev-user", "email": "dev@example.com"}
        cognito_email = cognito_user["email"]
        # --- END AUTH DISABLED ---

        if (
            hasattr(request.app.state, "test_db_session")
            and request.app.state.test_db_session is not None
        ):
            db = request.app.state.test_db_session
            request.state.db = db
            should_close_db = False
        elif hasattr(request.state, "db") and request.state.db is not None:
            db = request.state.db
            should_close_db = False
        else:
            db_gen = get_db()
            db: AsyncSession = await db_gen.__anext__()
            request.state.db = db
            should_close_db = True

        try:
            result = await db.execute(
                select(User).where(User.email == cognito_email)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                logger.warning(f"User {cognito_email} not found in database")

            enriched_user = EnrichedUserContext(cognito_user, db_user)
            request.state.user = enriched_user
            logger.debug(f"User context: {enriched_user.to_dict()}")

            return await call_next(request)

        except HTTPException as e:
            logger.warning(f"Auth error: {e.detail}")
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        except SQLAlchemyError as e:
            logger.error(f"Database error: {str(e)}")
            return JSONResponse(status_code=500, content={"detail": "Internal database error"})
        except (ValueError, ValidationError) as e:
            logger.error(f"Validation error: {str(e)}")
            return JSONResponse(status_code=422, content={"detail": str(e)})
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        finally:
            if should_close_db:
                await db_gen.aclose()


def get_current_user(request: Request) -> EnrichedUserContext:
    user = request.state.user
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user