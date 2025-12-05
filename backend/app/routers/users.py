"""
User Management Router.

Provides endpoints for user CRUD operations with Firebase authentication.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.middleware.auth import get_current_user, require_role
from app.models.user import (
    Role,
    UserCreate,
    UserInDB,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import UserNotFoundError, get_user_service

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: UserInDB = Depends(require_role(Role.ADMIN, Role.SUPERADMIN)),
):
    """
    Create new user.

    Requires ADMIN or SUPERADMIN role.

    **Request Body:**
    ```json
    {
        "email": "user@example.com",
        "password": "SecurePass123",
        "display_name": "John Doe",
        "photo_url": "https://example.com/photo.jpg",
        "role": "user",
        "email_verified": false
    }
    ```

    **Response:**
    ```json
    {
        "uid": "generated_uid",
        "email": "user@example.com",
        "display_name": "John Doe",
        "photo_url": "https://example.com/photo.jpg",
        "role": "user",
        "created_at": "2025-12-03T10:00:00Z",
        "email_verified": false,
        "disabled": false
    }
    ```
    """
    user_service = get_user_service()
    user = await user_service.create_user(user_data)
    return UserResponse.from_user_in_db(user)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: UserInDB = Depends(get_current_user)):
    """
    Get current user profile.

    Returns profile of authenticated user from Bearer token.

    **Response:**
    ```json
    {
        "uid": "user_uid",
        "email": "user@example.com",
        "display_name": "John Doe",
        "photo_url": "https://example.com/photo.jpg",
        "role": "user",
        "created_at": "2025-12-03T10:00:00Z",
        "email_verified": true,
        "disabled": false
    }
    ```
    """
    return UserResponse.from_user_in_db(current_user)


@router.get("/{uid}", response_model=UserResponse)
async def get_user(
    uid: str,
    current_user: UserInDB = Depends(require_role(Role.ADMIN, Role.SUPERADMIN)),
):
    """
    Get user by UID.

    Requires ADMIN or SUPERADMIN role.

    **Path Parameters:**
    - `uid`: Firebase user ID

    **Response:**
    ```json
    {
        "uid": "user_uid",
        "email": "user@example.com",
        "display_name": "John Doe",
        "photo_url": "https://example.com/photo.jpg",
        "role": "user",
        "created_at": "2025-12-03T10:00:00Z",
        "email_verified": true,
        "disabled": false
    }
    ```
    """
    user_service = get_user_service()
    try:
        user = await user_service.get_user(uid)
        return UserResponse.from_user_in_db(user)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/", response_model=List[UserResponse])
async def list_users(
    limit: int = 100,
    offset: int = 0,
    current_user: UserInDB = Depends(require_role(Role.ADMIN, Role.SUPERADMIN)),
):
    """
    List users with pagination.

    Requires ADMIN or SUPERADMIN role.

    **Query Parameters:**
    - `limit`: Maximum number of users to return (default: 100, max: 1000)
    - `offset`: Number of users to skip (default: 0)

    **Response:**
    ```json
    [
        {
            "uid": "user1_uid",
            "email": "user1@example.com",
            "display_name": "User One",
            "role": "user",
            "created_at": "2025-12-03T10:00:00Z",
            "email_verified": true,
            "disabled": false
        },
        {
            "uid": "user2_uid",
            "email": "user2@example.com",
            "display_name": "User Two",
            "role": "admin",
            "created_at": "2025-12-02T09:00:00Z",
            "email_verified": true,
            "disabled": false
        }
    ]
    ```
    """
    user_service = get_user_service()
    users = await user_service.list_users(limit=limit, offset=offset)
    return [UserResponse.from_user_in_db(user) for user in users]


@router.patch("/{uid}", response_model=UserResponse)
async def update_user(
    uid: str,
    user_data: UserUpdate,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Update user.

    Users can update their own profile.
    ADMIN/SUPERADMIN can update any user.

    **Path Parameters:**
    - `uid`: Firebase user ID

    **Request Body:**
    ```json
    {
        "display_name": "New Name",
        "photo_url": "https://example.com/new_photo.jpg",
        "disabled": false
    }
    ```

    **Response:**
    ```json
    {
        "uid": "user_uid",
        "email": "user@example.com",
        "display_name": "New Name",
        "photo_url": "https://example.com/new_photo.jpg",
        "role": "user",
        "created_at": "2025-12-03T10:00:00Z",
        "email_verified": true,
        "disabled": false
    }
    ```
    """
    # Check permissions: users can only update themselves, admins can update anyone
    if current_user.uid != uid and current_user.role not in [Role.ADMIN, Role.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update this user",
        )

    # Only admins can change role
    if user_data.role is not None and current_user.role not in [Role.ADMIN, Role.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can change user roles",
        )

    user_service = get_user_service()
    try:
        user = await user_service.update_user(uid, user_data)
        return UserResponse.from_user_in_db(user)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{uid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    uid: str,
    current_user: UserInDB = Depends(require_role(Role.ADMIN, Role.SUPERADMIN)),
):
    """
    Delete user.

    Requires ADMIN or SUPERADMIN role.

    **Path Parameters:**
    - `uid`: Firebase user ID

    **Response:**
    - 204 No Content on success
    - 404 Not Found if user doesn't exist
    """
    user_service = get_user_service()
    try:
        await user_service.delete_user(uid)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
