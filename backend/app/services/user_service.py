"""
User Service for Firestore operations.

Provides CRUD operations for user data in Firestore.
"""
import logging
from datetime import datetime
from typing import Optional

import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1 import AsyncClient

from app.config import settings
from app.exceptions import PeppolAPIException
from app.models.user import UserCreate, UserInDB, UserUpdate
from app.services.firebase_auth import get_firebase_auth_service

logger = logging.getLogger(__name__)


class UserServiceError(PeppolAPIException):
    """Raised when user service operation fails."""

    def __init__(self, detail: str):
        super().__init__(detail=f"User service error: {detail}", status_code=500)


class UserNotFoundError(PeppolAPIException):
    """Raised when user is not found in database."""

    def __init__(self, identifier: str):
        super().__init__(detail=f"User not found: {identifier}", status_code=404)


class UserAlreadyExistsError(PeppolAPIException):
    """Raised when attempting to create user that already exists."""

    def __init__(self, email: str):
        super().__init__(detail=f"User already exists: {email}", status_code=409)


class UserService:
    """
    User Service for Firestore operations.

    Manages user data in Firestore with CRUD operations.
    Works in conjunction with FirebaseAuthService for authentication.

    Example:
        ```python
        user_service = UserService()

        # Create user
        user_data = UserCreate(
            email="user@example.com",
            password="secure_password",
            display_name="John Doe"
        )
        user = await user_service.create_user(user_data)

        # Get user
        user = await user_service.get_user(uid="user123")

        # Update user
        update_data = UserUpdate(display_name="Jane Doe")
        user = await user_service.update_user(uid="user123", user_data=update_data)
        ```
    """

    COLLECTION_NAME = "users"

    def __init__(self):
        """Initialize User Service with Firestore client."""
        self._db: Optional[AsyncClient] = None
        self._init_firestore()

    def _init_firestore(self) -> None:
        """
        Initialize Firestore client.

        Raises:
            UserServiceError: If initialization fails
        """
        try:
            if not firebase_admin._apps:
                # Initialize Firebase if not already done
                get_firebase_auth_service()

            # Get async Firestore client
            self._db = firestore.async_client()
            logger.info("Firestore client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")
            raise UserServiceError(f"Failed to initialize Firestore: {str(e)}")

    async def create_user(self, user_data: UserCreate) -> UserInDB:
        """
        Create new user in Firestore.

        This method creates both Firebase Auth user and Firestore document.

        Args:
            user_data: User creation data

        Returns:
            UserInDB: Created user with database fields

        Raises:
            UserAlreadyExistsError: If user already exists
            UserServiceError: If creation fails
        """
        try:
            # Check if user already exists
            existing_user = await self.get_user_by_email(user_data.email, raise_if_not_found=False)
            if existing_user:
                raise UserAlreadyExistsError(user_data.email)

            # Create Firebase Auth user
            auth_service = get_firebase_auth_service()
            firebase_user = await auth_service.create_user(
                email=user_data.email,
                password=user_data.password,
                display_name=user_data.display_name,
                photo_url=user_data.photo_url,
                email_verified=user_data.email_verified,
            )

            # Set custom claims for role
            await auth_service.set_custom_user_claims(
                uid=firebase_user["uid"], claims={"role": user_data.role.value}
            )

            # Create Firestore document
            now = datetime.utcnow()
            user_doc = {
                "uid": firebase_user["uid"],
                "email": user_data.email,
                "display_name": user_data.display_name,
                "photo_url": user_data.photo_url,
                "role": user_data.role.value,
                "created_at": now,
                "updated_at": now,
                "disabled": False,
                "email_verified": user_data.email_verified,
                "last_sign_in": None,
            }

            doc_ref = self._db.collection(self.COLLECTION_NAME).document(firebase_user["uid"])
            await doc_ref.set(user_doc)

            logger.info(f"Created user in Firestore: {firebase_user['uid']}")
            return UserInDB(**user_doc)

        except (UserAlreadyExistsError, UserServiceError):
            raise
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            raise UserServiceError(f"Failed to create user: {str(e)}")

    async def get_user(self, uid: str, raise_if_not_found: bool = True) -> UserInDB | None:
        """
        Get user by UID.

        Args:
            uid: Firebase user ID
            raise_if_not_found: If True, raise exception when not found (default: True)

        Returns:
            UserInDB: User data or None if not found and raise_if_not_found=False

        Raises:
            UserNotFoundError: If user not found and raise_if_not_found=True
            UserServiceError: If operation fails
        """
        try:
            doc_ref = self._db.collection(self.COLLECTION_NAME).document(uid)
            doc = await doc_ref.get()

            if not doc.exists:
                if raise_if_not_found:
                    raise UserNotFoundError(uid)
                return None

            user_data = doc.to_dict()
            return UserInDB(**user_data)

        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get user: {e}")
            raise UserServiceError(f"Failed to get user: {str(e)}")

    async def get_user_by_email(self, email: str, raise_if_not_found: bool = True) -> UserInDB | None:
        """
        Get user by email address.

        Args:
            email: User email address
            raise_if_not_found: If True, raise exception when not found (default: True)

        Returns:
            UserInDB: User data or None if not found and raise_if_not_found=False

        Raises:
            UserNotFoundError: If user not found and raise_if_not_found=True
            UserServiceError: If operation fails
        """
        try:
            query = self._db.collection(self.COLLECTION_NAME).where("email", "==", email).limit(1)
            docs = await query.get()

            if not docs:
                if raise_if_not_found:
                    raise UserNotFoundError(email)
                return None

            user_data = docs[0].to_dict()
            return UserInDB(**user_data)

        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get user by email: {e}")
            raise UserServiceError(f"Failed to get user by email: {str(e)}")

    async def update_user(self, uid: str, user_data: UserUpdate) -> UserInDB:
        """
        Update user data.

        Updates both Firebase Auth and Firestore document.

        Args:
            uid: Firebase user ID
            user_data: Update data (only provided fields will be updated)

        Returns:
            UserInDB: Updated user data

        Raises:
            UserNotFoundError: If user not found
            UserServiceError: If update fails
        """
        try:
            # Verify user exists
            await self.get_user(uid)

            # Update Firebase Auth user
            auth_service = get_firebase_auth_service()
            update_kwargs = {}
            if user_data.email is not None:
                update_kwargs["email"] = user_data.email
            if user_data.display_name is not None:
                update_kwargs["display_name"] = user_data.display_name
            if user_data.photo_url is not None:
                update_kwargs["photo_url"] = user_data.photo_url
            if user_data.disabled is not None:
                update_kwargs["disabled"] = user_data.disabled
            if user_data.email_verified is not None:
                update_kwargs["email_verified"] = user_data.email_verified

            if update_kwargs:
                await auth_service.update_user(uid, **update_kwargs)

            # Update custom claims if role changed
            if user_data.role is not None:
                await auth_service.set_custom_user_claims(uid=uid, claims={"role": user_data.role.value})

            # Update Firestore document
            firestore_updates = {}
            if user_data.email is not None:
                firestore_updates["email"] = user_data.email
            if user_data.display_name is not None:
                firestore_updates["display_name"] = user_data.display_name
            if user_data.photo_url is not None:
                firestore_updates["photo_url"] = user_data.photo_url
            if user_data.role is not None:
                firestore_updates["role"] = user_data.role.value
            if user_data.disabled is not None:
                firestore_updates["disabled"] = user_data.disabled
            if user_data.email_verified is not None:
                firestore_updates["email_verified"] = user_data.email_verified

            firestore_updates["updated_at"] = datetime.utcnow()

            doc_ref = self._db.collection(self.COLLECTION_NAME).document(uid)
            await doc_ref.update(firestore_updates)

            logger.info(f"Updated user: {uid}")
            return await self.get_user(uid)

        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to update user: {e}")
            raise UserServiceError(f"Failed to update user: {str(e)}")

    async def delete_user(self, uid: str) -> bool:
        """
        Delete user from Firebase Auth and Firestore.

        Args:
            uid: Firebase user ID

        Returns:
            bool: True if deleted successfully

        Raises:
            UserNotFoundError: If user not found
            UserServiceError: If deletion fails
        """
        try:
            # Verify user exists
            await self.get_user(uid)

            # Delete from Firebase Auth
            auth_service = get_firebase_auth_service()
            await auth_service.delete_user(uid)

            # Delete from Firestore
            doc_ref = self._db.collection(self.COLLECTION_NAME).document(uid)
            await doc_ref.delete()

            logger.info(f"Deleted user: {uid}")
            return True

        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete user: {e}")
            raise UserServiceError(f"Failed to delete user: {str(e)}")

    async def list_users(self, limit: int = 100, offset: int = 0) -> list[UserInDB]:
        """
        List users with pagination.

        Args:
            limit: Maximum number of users to return (default: 100, max: 1000)
            offset: Number of users to skip (default: 0)

        Returns:
            list[UserInDB]: List of users

        Raises:
            UserServiceError: If operation fails
        """
        try:
            # Enforce max limit
            limit = min(limit, 1000)

            query = (
                self._db.collection(self.COLLECTION_NAME)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .offset(offset)
            )

            docs = await query.get()
            users = [UserInDB(**doc.to_dict()) for doc in docs]

            logger.debug(f"Listed {len(users)} users (limit={limit}, offset={offset})")
            return users

        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            raise UserServiceError(f"Failed to list users: {str(e)}")

    async def update_last_sign_in(self, uid: str) -> None:
        """
        Update user's last sign-in timestamp.

        Args:
            uid: Firebase user ID

        Raises:
            UserNotFoundError: If user not found
            UserServiceError: If update fails
        """
        try:
            doc_ref = self._db.collection(self.COLLECTION_NAME).document(uid)
            await doc_ref.update({"last_sign_in": datetime.utcnow()})
            logger.debug(f"Updated last sign-in for user: {uid}")
        except Exception as e:
            logger.error(f"Failed to update last sign-in: {e}")
            raise UserServiceError(f"Failed to update last sign-in: {str(e)}")


# Singleton instance
_user_service: Optional[UserService] = None


def get_user_service() -> UserService:
    """
    Get singleton User Service instance.

    Returns:
        UserService: Shared service instance
    """
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service
