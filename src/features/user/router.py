import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from src.features.user.schema import UserWithGitHubSchema, UserCreateSchema, UserProfileUpdateSchema
from src.features.user.service import UserService

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=UserWithGitHubSchema,
    operation_id="createUser"
)
async def create_user(user_data: UserCreateSchema, service: UserService = Depends()):
    """Create a new user."""
    return await service.create_user(user_data)


@user_router.get(
    "",
    response_model=List[UserWithGitHubSchema],
    operation_id="listUsers"
)
async def list_users(service: UserService = Depends()):
    """List all users."""
    return await service.list_users()


@user_router.get(
    "/{user_id}",
    response_model=UserWithGitHubSchema,
    operation_id="getUser"
)
async def get_user(user_id: uuid.UUID, service: UserService = Depends()):
    """Get a user by ID."""
    return await service.get_user(user_id)


@user_router.patch(
    "/{user_id}",
    response_model=UserWithGitHubSchema,
    operation_id="updateUser"
)
async def update_user(
    user_id: uuid.UUID,
    user_data: UserProfileUpdateSchema,
    service: UserService = Depends(),
):
    """Update a user."""
    return await service.update_profile(user_id, user_data)


@user_router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteUser"
)
async def delete_user(user_id: uuid.UUID, service: UserService = Depends()):
    """Delete a user."""
    await service.delete_user(user_id)