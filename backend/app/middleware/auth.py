"""
Authentication Middleware.

Provides FastAPI dependencies for authentication and authorization.
"""
import logging
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.user import Role, UserInDB
from app.services.firebase_auth import FirebaseAuthError, get_firebase_auth_service
from app.services.user_service import get_user_service

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserInDB:
    """
    Get current authenticated user from Bearer token.

    This dependency extracts and verifies the Firebase ID token from the
    Authorization header, then retrieves the user from Firestore.

    Args:
        credentials: HTTP Bearer credentials from Authorization header

    Returns:
        UserInDB: Current authenticated user

    Raises:
        HTTPException: 401 if token is invalid or user not found

    Example:
        ```python
        @app.get("/api/v1/profile")
        async def get_profile(current_user: UserInDB = Depends(get_current_user)):
            return current_user
        ```
    """
    try:
        # Verify Firebase ID token
        auth_service = get_firebase_auth_service()
        token_data = await auth_service.verify_token(credentials.credentials)

        # Get user from Firestore
        user_service = get_user_service()
        user = await user_service.get_user(token_data["uid"], raise_if_not_found=False)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found in database",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if account is disabled
        if user.disabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Update last sign-in timestamp (non-blocking)
        try:
            await user_service.update_last_sign_in(user.uid)
        except Exception as e:
            logger.warning(f"Failed to update last sign-in: {e}")

        return user

    except FirebaseAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(*allowed_roles: Role) -> Callable:
    """
    Create dependency that requires user to have specific role(s).

    This is a dependency factory that creates a FastAPI dependency
    requiring the user to have one of the specified roles.

    Args:
        *allowed_roles: Roles that are allowed access

    Returns:
        Callable: FastAPI dependency function

    Raises:
        HTTPException: 403 if user doesn't have required role

    Example:
        ```python
        # Require admin role
        @app.delete("/api/v1/users/{uid}")
        async def delete_user(
            uid: str,
            current_user: UserInDB = Depends(require_role(Role.ADMIN))
        ):
            return {"message": "User deleted"}

        # Require admin or superadmin role
        @app.post("/api/v1/settings")
        async def update_settings(
            settings: dict,
            current_user: UserInDB = Depends(require_role(Role.ADMIN, Role.SUPERADMIN))
        ):
            return {"message": "Settings updated"}
        ```
    """

    async def role_checker(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
        """Check if user has required role."""
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {', '.join(r.value for r in allowed_roles)}",
            )
        return current_user

    return role_checker


def optional_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
) -> UserInDB | None:
    """
    Optional authentication dependency.

    Returns user if authenticated, None otherwise.
    Does not raise exception if no credentials provided.

    Args:
        credentials: Optional HTTP Bearer credentials

    Returns:
        UserInDB | None: Current user or None

    Example:
        ```python
        @app.get("/api/v1/public")
        async def public_endpoint(current_user: UserInDB | None = Depends(optional_auth)):
            if current_user:
                return {"message": f"Hello {current_user.display_name}"}
            return {"message": "Hello guest"}
        ```
    """
    if not credentials:
        return None

    try:
        # Verify Firebase ID token
        auth_service = get_firebase_auth_service()
        token_data = auth_service.verify_token(credentials.credentials)

        # Get user from Firestore
        user_service = get_user_service()
        user = user_service.get_user(token_data["uid"], raise_if_not_found=False)

        return user

    except Exception as e:
        logger.debug(f"Optional auth failed: {e}")
        return None
