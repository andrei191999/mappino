"""
Firebase Authentication Service.

Provides Firebase Admin SDK integration for user authentication and management.
Supports both explicit credentials and Application Default Credentials (ADC).
"""
import logging
from typing import Optional

import firebase_admin
from firebase_admin import auth, credentials, initialize_app
from firebase_admin.exceptions import FirebaseError

from app.config import settings
from app.exceptions import PeppolAPIException

logger = logging.getLogger(__name__)


class FirebaseAuthError(PeppolAPIException):
    """Raised when Firebase authentication operation fails."""

    def __init__(self, detail: str):
        super().__init__(detail=f"Firebase auth error: {detail}", status_code=401)


class FirebasePermissionError(PeppolAPIException):
    """Raised when user lacks required permissions."""

    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(detail=detail, status_code=403)


class FirebaseNotFoundError(PeppolAPIException):
    """Raised when Firebase resource not found."""

    def __init__(self, detail: str):
        super().__init__(detail=f"Firebase resource not found: {detail}", status_code=404)


class FirebaseAuthService:
    """
    Firebase Authentication Service.

    Provides methods for user authentication, token verification, and user management
    using Firebase Admin SDK.

    Example:
        ```python
        auth_service = FirebaseAuthService()

        # Verify ID token
        user_data = await auth_service.verify_token(id_token)

        # Create user
        user = await auth_service.create_user(
            email="user@example.com",
            password="secure_password",
            display_name="John Doe"
        )
        ```
    """

    def __init__(self):
        """Initialize Firebase Admin SDK."""
        self._initialized = False
        self._init_firebase()

    def _init_firebase(self) -> None:
        """
        Initialize Firebase Admin SDK with credentials.

        Supports two modes:
        1. Explicit credentials file (firebase_credentials_path)
        2. Application Default Credentials (ADC) - auto-detected in GCP

        Raises:
            FirebaseAuthError: If initialization fails
        """
        if self._initialized:
            return

        try:
            # Check if already initialized
            if firebase_admin._apps:
                logger.info("Firebase Admin SDK already initialized")
                self._initialized = True
                return

            # Option 1: Explicit credentials file
            if settings.firebase_credentials_path:
                logger.info(f"Initializing Firebase with credentials: {settings.firebase_credentials_path}")
                cred = credentials.Certificate(settings.firebase_credentials_path)
                initialize_app(cred)
            # Option 2: Application Default Credentials (ADC)
            else:
                logger.info("Initializing Firebase with Application Default Credentials")
                initialize_app()

            self._initialized = True
            logger.info("Firebase Admin SDK initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise FirebaseAuthError(f"Failed to initialize Firebase: {str(e)}")

    async def verify_token(self, id_token: str) -> dict:
        """
        Verify Firebase ID token.

        Args:
            id_token: Firebase ID token from client

        Returns:
            dict: Decoded token containing user data
                {
                    "uid": "user_id",
                    "email": "user@example.com",
                    "email_verified": True,
                    "name": "John Doe",
                    "picture": "https://...",
                    "iss": "https://securetoken.google.com/project-id",
                    "aud": "project-id",
                    "auth_time": 1234567890,
                    "sub": "user_id",
                    "iat": 1234567890,
                    "exp": 1234571490,
                    "firebase": {
                        "identities": {...},
                        "sign_in_provider": "password"
                    }
                }

        Raises:
            FirebaseAuthError: If token is invalid or expired
        """
        try:
            decoded_token = auth.verify_id_token(id_token)
            logger.debug(f"Token verified for user: {decoded_token.get('uid')}")
            return decoded_token
        except auth.InvalidIdTokenError:
            raise FirebaseAuthError("Invalid ID token")
        except auth.ExpiredIdTokenError:
            raise FirebaseAuthError("ID token has expired")
        except auth.RevokedIdTokenError:
            raise FirebaseAuthError("ID token has been revoked")
        except FirebaseError as e:
            logger.error(f"Token verification failed: {e}")
            raise FirebaseAuthError(f"Token verification failed: {str(e)}")

    async def create_user(
        self,
        email: str,
        password: str,
        display_name: str | None = None,
        photo_url: str | None = None,
        email_verified: bool = False,
        disabled: bool = False,
    ) -> dict:
        """
        Create a new Firebase user.

        Args:
            email: User email address
            password: User password (min 6 characters)
            display_name: Optional display name
            photo_url: Optional profile photo URL
            email_verified: Whether email is verified (default: False)
            disabled: Whether account is disabled (default: False)

        Returns:
            dict: Created user data
                {
                    "uid": "generated_uid",
                    "email": "user@example.com",
                    "email_verified": False,
                    "display_name": "John Doe",
                    "photo_url": "https://...",
                    "disabled": False,
                    "metadata": {
                        "creation_timestamp": 1234567890,
                        "last_sign_in_timestamp": None,
                        "last_refresh_timestamp": None
                    },
                    "provider_data": [...]
                }

        Raises:
            FirebaseAuthError: If user creation fails
        """
        try:
            user_record = auth.create_user(
                email=email,
                password=password,
                display_name=display_name,
                photo_url=photo_url,
                email_verified=email_verified,
                disabled=disabled,
            )
            logger.info(f"Created user: {user_record.uid}")
            return self._user_record_to_dict(user_record)
        except auth.EmailAlreadyExistsError:
            raise FirebaseAuthError(f"User with email {email} already exists")
        except FirebaseError as e:
            logger.error(f"User creation failed: {e}")
            raise FirebaseAuthError(f"Failed to create user: {str(e)}")

    async def get_user_by_uid(self, uid: str) -> dict:
        """
        Get user by UID.

        Args:
            uid: Firebase user ID

        Returns:
            dict: User data

        Raises:
            FirebaseNotFoundError: If user not found
            FirebaseAuthError: If operation fails
        """
        try:
            user_record = auth.get_user(uid)
            return self._user_record_to_dict(user_record)
        except auth.UserNotFoundError:
            raise FirebaseNotFoundError(f"User with UID {uid} not found")
        except FirebaseError as e:
            logger.error(f"Failed to get user by UID: {e}")
            raise FirebaseAuthError(f"Failed to get user: {str(e)}")

    async def get_user_by_email(self, email: str) -> dict:
        """
        Get user by email address.

        Args:
            email: User email address

        Returns:
            dict: User data

        Raises:
            FirebaseNotFoundError: If user not found
            FirebaseAuthError: If operation fails
        """
        try:
            user_record = auth.get_user_by_email(email)
            return self._user_record_to_dict(user_record)
        except auth.UserNotFoundError:
            raise FirebaseNotFoundError(f"User with email {email} not found")
        except FirebaseError as e:
            logger.error(f"Failed to get user by email: {e}")
            raise FirebaseAuthError(f"Failed to get user: {str(e)}")

    async def update_user(
        self,
        uid: str,
        email: str | None = None,
        password: str | None = None,
        display_name: str | None = None,
        photo_url: str | None = None,
        email_verified: bool | None = None,
        disabled: bool | None = None,
    ) -> dict:
        """
        Update user properties.

        Args:
            uid: Firebase user ID
            email: New email address (optional)
            password: New password (optional)
            display_name: New display name (optional)
            photo_url: New photo URL (optional)
            email_verified: New email verified status (optional)
            disabled: New disabled status (optional)

        Returns:
            dict: Updated user data

        Raises:
            FirebaseNotFoundError: If user not found
            FirebaseAuthError: If update fails
        """
        try:
            # Build update kwargs (only include provided values)
            update_kwargs = {}
            if email is not None:
                update_kwargs["email"] = email
            if password is not None:
                update_kwargs["password"] = password
            if display_name is not None:
                update_kwargs["display_name"] = display_name
            if photo_url is not None:
                update_kwargs["photo_url"] = photo_url
            if email_verified is not None:
                update_kwargs["email_verified"] = email_verified
            if disabled is not None:
                update_kwargs["disabled"] = disabled

            user_record = auth.update_user(uid, **update_kwargs)
            logger.info(f"Updated user: {uid}")
            return self._user_record_to_dict(user_record)
        except auth.UserNotFoundError:
            raise FirebaseNotFoundError(f"User with UID {uid} not found")
        except FirebaseError as e:
            logger.error(f"Failed to update user: {e}")
            raise FirebaseAuthError(f"Failed to update user: {str(e)}")

    async def delete_user(self, uid: str) -> bool:
        """
        Delete user by UID.

        Args:
            uid: Firebase user ID

        Returns:
            bool: True if deleted successfully

        Raises:
            FirebaseNotFoundError: If user not found
            FirebaseAuthError: If deletion fails
        """
        try:
            auth.delete_user(uid)
            logger.info(f"Deleted user: {uid}")
            return True
        except auth.UserNotFoundError:
            raise FirebaseNotFoundError(f"User with UID {uid} not found")
        except FirebaseError as e:
            logger.error(f"Failed to delete user: {e}")
            raise FirebaseAuthError(f"Failed to delete user: {str(e)}")

    async def create_custom_token(self, uid: str, claims: dict | None = None) -> str:
        """
        Create custom token for user.

        Custom tokens can be used to sign in users on the client side.

        Args:
            uid: Firebase user ID
            claims: Optional custom claims to include in token

        Returns:
            str: Custom token (JWT)

        Raises:
            FirebaseAuthError: If token creation fails

        Example:
            ```python
            # Create token with custom claims
            token = await auth_service.create_custom_token(
                uid="user123",
                claims={"role": "admin", "premium": True}
            )
            # Client can use this token to sign in
            ```
        """
        try:
            custom_token = auth.create_custom_token(uid, developer_claims=claims)
            logger.debug(f"Created custom token for user: {uid}")
            return custom_token.decode("utf-8")
        except FirebaseError as e:
            logger.error(f"Failed to create custom token: {e}")
            raise FirebaseAuthError(f"Failed to create custom token: {str(e)}")

    async def set_custom_user_claims(self, uid: str, claims: dict) -> None:
        """
        Set custom claims on user.

        Custom claims are included in ID tokens and can be used for role-based access control.

        Args:
            uid: Firebase user ID
            claims: Custom claims dict (max 1000 bytes serialized)

        Raises:
            FirebaseNotFoundError: If user not found
            FirebaseAuthError: If operation fails

        Example:
            ```python
            # Set admin role
            await auth_service.set_custom_user_claims(
                uid="user123",
                claims={"role": "admin", "permissions": ["read", "write"]}
            )
            ```
        """
        try:
            auth.set_custom_user_claims(uid, claims)
            logger.info(f"Set custom claims for user: {uid}")
        except auth.UserNotFoundError:
            raise FirebaseNotFoundError(f"User with UID {uid} not found")
        except FirebaseError as e:
            logger.error(f"Failed to set custom claims: {e}")
            raise FirebaseAuthError(f"Failed to set custom claims: {str(e)}")

    async def revoke_refresh_tokens(self, uid: str) -> None:
        """
        Revoke all refresh tokens for user.

        This will force the user to re-authenticate.

        Args:
            uid: Firebase user ID

        Raises:
            FirebaseNotFoundError: If user not found
            FirebaseAuthError: If operation fails
        """
        try:
            auth.revoke_refresh_tokens(uid)
            logger.info(f"Revoked refresh tokens for user: {uid}")
        except auth.UserNotFoundError:
            raise FirebaseNotFoundError(f"User with UID {uid} not found")
        except FirebaseError as e:
            logger.error(f"Failed to revoke refresh tokens: {e}")
            raise FirebaseAuthError(f"Failed to revoke refresh tokens: {str(e)}")

    def _user_record_to_dict(self, user_record) -> dict:
        """
        Convert UserRecord to dictionary.

        Args:
            user_record: Firebase UserRecord object

        Returns:
            dict: User data as dictionary
        """
        return {
            "uid": user_record.uid,
            "email": user_record.email,
            "email_verified": user_record.email_verified,
            "display_name": user_record.display_name,
            "photo_url": user_record.photo_url,
            "disabled": user_record.disabled,
            "metadata": {
                "creation_timestamp": user_record.user_metadata.creation_timestamp,
                "last_sign_in_timestamp": user_record.user_metadata.last_sign_in_timestamp,
                "last_refresh_timestamp": user_record.user_metadata.last_refresh_timestamp,
            },
            "provider_data": [
                {
                    "uid": provider.uid,
                    "email": provider.email,
                    "provider_id": provider.provider_id,
                }
                for provider in user_record.provider_data
            ],
            "custom_claims": user_record.custom_claims or {},
        }


# Singleton instance
_firebase_auth_service: Optional[FirebaseAuthService] = None


def get_firebase_auth_service() -> FirebaseAuthService:
    """
    Get singleton Firebase Auth Service instance.

    Returns:
        FirebaseAuthService: Shared service instance
    """
    global _firebase_auth_service
    if _firebase_auth_service is None:
        _firebase_auth_service = FirebaseAuthService()
    return _firebase_auth_service
