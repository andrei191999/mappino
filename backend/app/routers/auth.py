"""
Authentication Router

Provides endpoints for:
- User registration
- User profile management
- Admin user management
- Token verification

Note: Most authentication is handled client-side via Firebase Auth SDK.
These endpoints are for server-side operations and profile management.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.services.firebase_auth import (
    firebase_auth,
    DecodedToken,
    UserDocument,
    UserUpdateData,
)
from app.middleware.auth import (
    get_current_user,
    require_admin,
    require_verified_email,
)
from app.exceptions import AuthenticationError, ValidationError


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)


# ============================================
# Request/Response Models
# ============================================

class UserRegistrationRequest(BaseModel):
    """Request model for user registration"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    displayName: Optional[str] = None


class UserRegistrationResponse(BaseModel):
    """Response model for user registration"""
    uid: str
    email: str
    displayName: Optional[str] = None
    message: str


class UserProfileResponse(BaseModel):
    """Response model for user profile"""
    uid: str
    email: str
    displayName: Optional[str] = None
    photoURL: Optional[str] = None
    emailVerified: bool
    role: str
    createdAt: str
    updatedAt: str


class UserUpdateRequest(BaseModel):
    """Request model for updating user profile"""
    displayName: Optional[str] = None
    photoURL: Optional[str] = None


class SetRoleRequest(BaseModel):
    """Request model for setting user role"""
    uid: str
    role: str = Field(..., pattern="^(user|admin)$")


class TokenVerificationRequest(BaseModel):
    """Request model for token verification"""
    idToken: str


class TokenVerificationResponse(BaseModel):
    """Response model for token verification"""
    valid: bool
    uid: Optional[str] = None
    email: Optional[str] = None
    emailVerified: Optional[bool] = None


class UserListResponse(BaseModel):
    """Response model for user list"""
    users: List[dict]
    nextPageToken: Optional[str] = None


# ============================================
# Public Endpoints (No Authentication)
# ============================================

@router.post(
    "/register",
    response_model=UserRegistrationResponse,
    status_code=status.HTTP_201_CREATED
)
async def register_user(request: UserRegistrationRequest):
    """
    Register a new user

    Creates user in Firebase Auth and Firestore.

    Note: In production, you may want to disable this endpoint
    and handle registration client-side via Firebase Auth SDK.
    """
    try:
        # Create user in Firebase Auth
        user_record = await firebase_auth.create_user(
            email=request.email,
            password=request.password,
            display_name=request.displayName,
            email_verified=False
        )

        # Create user document in Firestore
        user_doc = await firebase_auth.create_user_document(
            uid=user_record.uid,
            email=request.email,
            display_name=request.displayName,
            email_verified=False,
            role="user"
        )

        return UserRegistrationResponse(
            uid=user_record.uid,
            email=request.email,
            displayName=request.displayName,
            message="User registered successfully. Please verify your email."
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post(
    "/verify-token",
    response_model=TokenVerificationResponse
)
async def verify_token(request: TokenVerificationRequest):
    """
    Verify Firebase ID token

    Useful for testing token validity without making authenticated requests.
    """
    try:
        decoded_token = await firebase_auth.verify_id_token(request.idToken)

        return TokenVerificationResponse(
            valid=True,
            uid=decoded_token.uid,
            email=decoded_token.email,
            emailVerified=decoded_token.email_verified
        )

    except AuthenticationError:
        return TokenVerificationResponse(valid=False)
    except Exception:
        return TokenVerificationResponse(valid=False)


# ============================================
# Authenticated Endpoints
# ============================================

@router.get(
    "/profile",
    response_model=UserProfileResponse
)
async def get_profile(user: DecodedToken = Depends(get_current_user)):
    """
    Get current user profile

    Returns user profile from Firestore.
    Requires valid Firebase ID token.
    """
    try:
        user_doc = await firebase_auth.get_user_document(user.uid)

        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )

        return UserProfileResponse(
            uid=user_doc.uid,
            email=user_doc.email,
            displayName=user_doc.displayName,
            photoURL=user_doc.photoURL,
            emailVerified=user_doc.emailVerified,
            role=user_doc.role,
            createdAt=user_doc.createdAt.isoformat(),
            updatedAt=user_doc.updatedAt.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}"
        )


@router.put(
    "/profile",
    response_model=UserProfileResponse
)
async def update_profile(
    request: UserUpdateRequest,
    user: DecodedToken = Depends(get_current_user)
):
    """
    Update current user profile

    Updates displayName and/or photoURL in both Firebase Auth and Firestore.
    Requires valid Firebase ID token.
    """
    try:
        # Update Firebase Auth
        if request.displayName is not None or request.photoURL is not None:
            await firebase_auth.update_user(
                uid=user.uid,
                display_name=request.displayName,
                photo_url=request.photoURL
            )

        # Update Firestore document
        update_data = UserUpdateData(
            displayName=request.displayName,
            photoURL=request.photoURL
        )

        user_doc = await firebase_auth.update_user_document(user.uid, update_data)

        return UserProfileResponse(
            uid=user_doc.uid,
            email=user_doc.email,
            displayName=user_doc.displayName,
            photoURL=user_doc.photoURL,
            emailVerified=user_doc.emailVerified,
            role=user_doc.role,
            createdAt=user_doc.createdAt.isoformat(),
            updatedAt=user_doc.updatedAt.isoformat()
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


@router.delete(
    "/profile",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_account(user: DecodedToken = Depends(require_verified_email)):
    """
    Delete current user account

    Deletes user from both Firebase Auth and Firestore.
    Requires email verification for security.
    """
    try:
        # Delete Firestore document
        await firebase_auth.delete_user_document(user.uid)

        # Delete from Firebase Auth
        await firebase_auth.delete_user(user.uid)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete account: {str(e)}"
        )


# ============================================
# Admin Endpoints
# ============================================

@router.get(
    "/admin/users",
    response_model=UserListResponse
)
async def list_users(
    limit: int = 100,
    pageToken: Optional[str] = None,
    user: DecodedToken = Depends(require_admin)
):
    """
    List all users (Admin only)

    Returns paginated list of users from Firebase Auth.
    """
    try:
        users, next_token = await firebase_auth.list_users(
            limit=limit,
            page_token=pageToken
        )

        user_list = [
            {
                "uid": u.uid,
                "email": u.email,
                "displayName": u.display_name,
                "emailVerified": u.email_verified,
                "disabled": u.disabled,
                "creationTimestamp": u.user_metadata.creation_timestamp,
            }
            for u in users
        ]

        return UserListResponse(
            users=user_list,
            nextPageToken=next_token
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )


@router.post(
    "/admin/set-role",
    status_code=status.HTTP_200_OK
)
async def set_user_role(
    request: SetRoleRequest,
    user: DecodedToken = Depends(require_admin)
):
    """
    Set user role (Admin only)

    Sets user role to 'user' or 'admin' in both Firestore and custom claims.
    """
    try:
        await firebase_auth.set_user_role(request.uid, request.role)

        return {
            "message": f"User role set to {request.role}",
            "uid": request.uid,
            "role": request.role
        }

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set user role: {str(e)}"
        )


@router.delete(
    "/admin/users/{uid}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_user(
    uid: str,
    user: DecodedToken = Depends(require_admin)
):
    """
    Delete user by UID (Admin only)

    Deletes user from both Firebase Auth and Firestore.
    """
    try:
        # Prevent admin from deleting themselves
        if uid == user.uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )

        # Delete Firestore document
        await firebase_auth.delete_user_document(uid)

        # Delete from Firebase Auth
        await firebase_auth.delete_user(uid)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )


@router.get(
    "/admin/users/{uid}",
    response_model=UserProfileResponse
)
async def get_user_profile(
    uid: str,
    user: DecodedToken = Depends(require_admin)
):
    """
    Get user profile by UID (Admin only)

    Returns user profile from Firestore.
    """
    try:
        user_doc = await firebase_auth.get_user_document(uid)

        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )

        return UserProfileResponse(
            uid=user_doc.uid,
            email=user_doc.email,
            displayName=user_doc.displayName,
            photoURL=user_doc.photoURL,
            emailVerified=user_doc.emailVerified,
            role=user_doc.role,
            createdAt=user_doc.createdAt.isoformat(),
            updatedAt=user_doc.updatedAt.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user profile: {str(e)}"
        )
