import uuid
from typing import List

from fastapi import APIRouter, Depends
from starlette import status

from src.auth.jwt import create_access_token
from src.features.user.schema import (
    LoginResponseSchema,
    UserCreateSchema,
    UserLoginSchema,
    UserMemberCreateSchema,
    UserProfileUpdateSchema,
    UserWithGitHubSchema,
)
from src.features.user.service import UserService
from src.middleware.user_context import get_current_user

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=LoginResponseSchema,
    operation_id="signupUser"
)
async def signup(user_data: UserCreateSchema, service: UserService = Depends()):
    """Create a new user and return an auth token."""
    user_schema = await service.signup(user_data)
    token = create_access_token(str(user_schema.id), email=user_schema.email)
    return LoginResponseSchema(user=user_schema, token=token)


@user_router.post(
    "/login",
    response_model=LoginResponseSchema,
    operation_id="loginUser"
)
async def login(user_data: UserLoginSchema, service: UserService = Depends()):
    """Authenticate user and return an auth token."""
    user_schema = await service.authenticate(user_data.email, user_data.password)
    token = create_access_token(str(user_schema.id), email=user_schema.email)
    return LoginResponseSchema(user=user_schema, token=token)


@user_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=UserWithGitHubSchema,
    operation_id="createUser"
)
async def create_user(
    user_data: UserMemberCreateSchema,
    current_user=Depends(get_current_user),
    service: UserService = Depends(),
):
    """Add a member to the current user's account (admins only)."""
    return await service.create_member(current_user.id, user_data)


@user_router.get(
    "",
    response_model=List[UserWithGitHubSchema],
    operation_id="listUsers"
)
async def list_users(
    current_user=Depends(get_current_user),
    service: UserService = Depends(),
):
    """List users in the current user's account."""
    return await service.list_users(current_user.account_id)


@user_router.get(
    "/me",
    response_model=UserWithGitHubSchema,
    operation_id="getCurrentUser",
)
async def get_current_user_profile(
    current_user=Depends(get_current_user),
    service: UserService = Depends(),
):
    """Get the authenticated user's profile and GitHub connection status."""
    return await service.get_user(current_user.id, current_user)


@user_router.get(
    "/{user_id}",
    response_model=UserWithGitHubSchema,
    operation_id="getUser"
)
async def get_user(
    user_id: uuid.UUID,
    current_user=Depends(get_current_user),
    service: UserService = Depends(),
):
    """Get a user by ID in the current user's account."""
    return await service.get_user(user_id, current_user)


@user_router.patch(
    "/{user_id}",
    response_model=UserWithGitHubSchema,
    operation_id="updateUser"
)
async def update_user(
    user_id: uuid.UUID,
    user_data: UserProfileUpdateSchema,
    current_user=Depends(get_current_user),
    service: UserService = Depends(),
):
    """Update a user in the current user's account (self or admin only)."""
    return await service.update_profile(user_id, user_data, current_user)


@user_router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteUser"
)
async def delete_user(
    user_id: uuid.UUID,
    current_user=Depends(get_current_user),
    service: UserService = Depends(),
):
    """Delete a user in the current user's account (admins only)."""
    await service.delete_user(user_id, current_user)
