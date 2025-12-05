"""
Tests for Firebase integration.

Tests Firebase Auth, User Service, Secret Manager, and authentication middleware.
"""
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from firebase_admin import auth as firebase_auth

from app.middleware.auth import get_current_user, require_role
from app.models.user import Role, UserCreate, UserUpdate
from app.services.firebase_auth import (
    FirebaseAuthError,
    FirebaseAuthService,
    FirebaseNotFoundError,
)
from app.services.secret_manager import SecretManagerService, SecretNotFoundError
from app.services.user_service import (
    UserAlreadyExistsError,
    UserNotFoundError,
    UserService,
)


class TestFirebaseAuthService:
    """Test Firebase Auth Service."""

    @pytest.fixture
    def auth_service(self):
        """Get Firebase Auth Service instance."""
        with patch("app.services.firebase_auth.initialize_app"):
            service = FirebaseAuthService()
            service._initialized = True
            return service

    @pytest.mark.asyncio
    async def test_verify_token_success(self, auth_service):
        """Test successful token verification."""
        mock_decoded = {
            "uid": "test_uid",
            "email": "test@example.com",
            "email_verified": True,
        }

        with patch.object(firebase_auth, "verify_id_token", return_value=mock_decoded):
            result = await auth_service.verify_token("valid_token")

            assert result["uid"] == "test_uid"
            assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, auth_service):
        """Test token verification with invalid token."""
        with patch.object(
            firebase_auth, "verify_id_token", side_effect=firebase_auth.InvalidIdTokenError("Invalid token")
        ):
            with pytest.raises(FirebaseAuthError) as exc_info:
                await auth_service.verify_token("invalid_token")

            assert "Invalid ID token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_user_success(self, auth_service):
        """Test successful user creation."""
        mock_user_record = MagicMock()
        mock_user_record.uid = "new_uid"
        mock_user_record.email = "new@example.com"
        mock_user_record.email_verified = False
        mock_user_record.display_name = "New User"
        mock_user_record.photo_url = None
        mock_user_record.disabled = False
        mock_user_record.custom_claims = {}
        mock_user_record.user_metadata = MagicMock()
        mock_user_record.user_metadata.creation_timestamp = 1234567890
        mock_user_record.user_metadata.last_sign_in_timestamp = None
        mock_user_record.user_metadata.last_refresh_timestamp = None
        mock_user_record.provider_data = []

        with patch.object(firebase_auth, "create_user", return_value=mock_user_record):
            result = await auth_service.create_user(
                email="new@example.com", password="password123", display_name="New User"
            )

            assert result["uid"] == "new_uid"
            assert result["email"] == "new@example.com"
            assert result["display_name"] == "New User"

    @pytest.mark.asyncio
    async def test_create_user_already_exists(self, auth_service):
        """Test user creation when email already exists."""
        with patch.object(
            firebase_auth, "create_user", side_effect=firebase_auth.EmailAlreadyExistsError(
                "Email exists", cause=None, http_response=None
            )
        ):
            with pytest.raises(FirebaseAuthError) as exc_info:
                await auth_service.create_user(email="existing@example.com", password="password123")

            assert "already exists" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_user_by_uid_success(self, auth_service):
        """Test getting user by UID."""
        mock_user_record = MagicMock()
        mock_user_record.uid = "test_uid"
        mock_user_record.email = "test@example.com"
        mock_user_record.custom_claims = {}
        mock_user_record.user_metadata = MagicMock()
        mock_user_record.user_metadata.creation_timestamp = 1234567890
        mock_user_record.user_metadata.last_sign_in_timestamp = None
        mock_user_record.user_metadata.last_refresh_timestamp = None
        mock_user_record.provider_data = []

        with patch.object(firebase_auth, "get_user", return_value=mock_user_record):
            result = await auth_service.get_user_by_uid("test_uid")

            assert result["uid"] == "test_uid"
            assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_uid_not_found(self, auth_service):
        """Test getting user by UID when not found."""
        with patch.object(firebase_auth, "get_user", side_effect=firebase_auth.UserNotFoundError("User not found")):
            with pytest.raises(FirebaseNotFoundError):
                await auth_service.get_user_by_uid("nonexistent_uid")

    @pytest.mark.asyncio
    async def test_delete_user_success(self, auth_service):
        """Test successful user deletion."""
        with patch.object(firebase_auth, "delete_user", return_value=None):
            result = await auth_service.delete_user("test_uid")

            assert result is True

    @pytest.mark.asyncio
    async def test_create_custom_token(self, auth_service):
        """Test custom token creation."""
        mock_token = b"custom_token_bytes"

        with patch.object(firebase_auth, "create_custom_token", return_value=mock_token):
            result = await auth_service.create_custom_token(uid="test_uid", claims={"role": "admin"})

            assert result == "custom_token_bytes"


class TestUserService:
    """Test User Service."""

    @pytest.fixture
    def user_service(self):
        """Get User Service instance."""
        with patch("app.services.user_service.firebase_admin"):
            with patch("app.services.user_service.firestore"):
                service = UserService()
                service._db = MagicMock()
                return service

    @pytest.mark.asyncio
    async def test_create_user_success(self, user_service):
        """Test successful user creation."""
        user_data = UserCreate(
            email="test@example.com",
            password="password123",
            display_name="Test User",
            role=Role.USER,
        )

        # Mock Firebase Auth user creation
        mock_firebase_user = {"uid": "test_uid", "email": "test@example.com"}

        # Mock Firestore operations
        mock_doc_ref = MagicMock()
        mock_doc_ref.set = AsyncMock()
        user_service._db.collection.return_value.document.return_value = mock_doc_ref

        with patch("app.services.user_service.get_firebase_auth_service") as mock_auth:
            mock_auth_instance = MagicMock()
            mock_auth_instance.create_user = AsyncMock(return_value=mock_firebase_user)
            mock_auth_instance.set_custom_user_claims = AsyncMock()
            mock_auth.return_value = mock_auth_instance

            with patch.object(user_service, "get_user_by_email", return_value=None):
                result = await user_service.create_user(user_data)

                assert result.uid == "test_uid"
                assert result.email == "test@example.com"
                assert result.role == Role.USER

    @pytest.mark.asyncio
    async def test_create_user_already_exists(self, user_service):
        """Test user creation when user already exists."""
        user_data = UserCreate(
            email="existing@example.com",
            password="password123",
            display_name="Existing User",
        )

        # Mock existing user
        existing_user = MagicMock()
        existing_user.email = "existing@example.com"

        with patch.object(user_service, "get_user_by_email", return_value=existing_user):
            with pytest.raises(UserAlreadyExistsError):
                await user_service.create_user(user_data)

    @pytest.mark.asyncio
    async def test_get_user_success(self, user_service):
        """Test getting user by UID."""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "uid": "test_uid",
            "email": "test@example.com",
            "display_name": "Test User",
            "role": "user",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "disabled": False,
            "email_verified": True,
        }

        mock_doc_ref = MagicMock()
        mock_doc_ref.get = AsyncMock(return_value=mock_doc)
        user_service._db.collection.return_value.document.return_value = mock_doc_ref

        result = await user_service.get_user("test_uid")

        assert result.uid == "test_uid"
        assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, user_service):
        """Test getting user when not found."""
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_doc_ref = MagicMock()
        mock_doc_ref.get = AsyncMock(return_value=mock_doc)
        user_service._db.collection.return_value.document.return_value = mock_doc_ref

        with pytest.raises(UserNotFoundError):
            await user_service.get_user("nonexistent_uid")

    @pytest.mark.asyncio
    async def test_update_user_success(self, user_service):
        """Test successful user update."""
        update_data = UserUpdate(display_name="Updated Name")

        # Mock existing user
        existing_user = MagicMock()
        existing_user.uid = "test_uid"

        # Mock Firestore update
        mock_doc_ref = MagicMock()
        mock_doc_ref.update = AsyncMock()
        user_service._db.collection.return_value.document.return_value = mock_doc_ref

        with patch.object(user_service, "get_user", side_effect=[existing_user, existing_user]):
            with patch("app.services.user_service.get_firebase_auth_service") as mock_auth:
                mock_auth_instance = MagicMock()
                mock_auth_instance.update_user = AsyncMock()
                mock_auth.return_value = mock_auth_instance

                result = await user_service.update_user("test_uid", update_data)

                assert result.uid == "test_uid"

    @pytest.mark.asyncio
    async def test_delete_user_success(self, user_service):
        """Test successful user deletion."""
        mock_user = MagicMock()
        mock_user.uid = "test_uid"

        mock_doc_ref = MagicMock()
        mock_doc_ref.delete = AsyncMock()
        user_service._db.collection.return_value.document.return_value = mock_doc_ref

        with patch.object(user_service, "get_user", return_value=mock_user):
            with patch("app.services.user_service.get_firebase_auth_service") as mock_auth:
                mock_auth_instance = MagicMock()
                mock_auth_instance.delete_user = AsyncMock()
                mock_auth.return_value = mock_auth_instance

                result = await user_service.delete_user("test_uid")

                assert result is True


class TestSecretManagerService:
    """Test Secret Manager Service."""

    @pytest.fixture
    def secret_service(self):
        """Get Secret Manager Service instance."""
        with patch("app.services.secret_manager.secretmanager"):
            with patch("app.config.settings") as mock_settings:
                mock_settings.use_secret_manager = False
                mock_settings.gcp_project_id = "test-project"
                service = SecretManagerService()
                return service

    @pytest.mark.asyncio
    async def test_get_secret_from_env(self, secret_service):
        """Test getting secret from environment variable."""
        with patch.dict(os.environ, {"TEST_SECRET": "test_value"}):
            result = await secret_service.get_secret("TEST_SECRET")

            assert result == "test_value"

    @pytest.mark.asyncio
    async def test_get_secret_not_found_env(self, secret_service):
        """Test getting non-existent secret from environment."""
        with pytest.raises(SecretNotFoundError):
            await secret_service.get_secret("NONEXISTENT_SECRET")


class TestAuthMiddleware:
    """Test authentication middleware."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self):
        """Test successful user authentication."""
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid_token"

        mock_user = MagicMock()
        mock_user.uid = "test_uid"
        mock_user.disabled = False

        with patch("app.middleware.auth.get_firebase_auth_service") as mock_auth:
            mock_auth_instance = MagicMock()
            mock_auth_instance.verify_token = AsyncMock(return_value={"uid": "test_uid"})
            mock_auth.return_value = mock_auth_instance

            with patch("app.middleware.auth.get_user_service") as mock_user_service:
                mock_service = MagicMock()
                mock_service.get_user = AsyncMock(return_value=mock_user)
                mock_service.update_last_sign_in = AsyncMock()
                mock_user_service.return_value = mock_service

                result = await get_current_user(mock_credentials)

                assert result.uid == "test_uid"

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test authentication with invalid token."""
        from app.services.firebase_auth import FirebaseAuthError

        mock_credentials = MagicMock()
        mock_credentials.credentials = "invalid_token"

        with patch("app.middleware.auth.get_firebase_auth_service") as mock_auth:
            mock_auth_instance = MagicMock()
            mock_auth_instance.verify_token = AsyncMock(side_effect=FirebaseAuthError("Invalid token"))
            mock_auth.return_value = mock_auth_instance

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_disabled_account(self):
        """Test authentication with disabled account."""
        mock_credentials = MagicMock()
        mock_credentials.credentials = "valid_token"

        mock_user = MagicMock()
        mock_user.uid = "test_uid"
        mock_user.disabled = True

        with patch("app.middleware.auth.get_firebase_auth_service") as mock_auth:
            mock_auth_instance = MagicMock()
            mock_auth_instance.verify_token = AsyncMock(return_value={"uid": "test_uid"})
            mock_auth.return_value = mock_auth_instance

            with patch("app.middleware.auth.get_user_service") as mock_user_service:
                mock_service = MagicMock()
                mock_service.get_user = AsyncMock(return_value=mock_user)
                mock_user_service.return_value = mock_service

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(mock_credentials)

                assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_role_success(self):
        """Test role requirement with correct role."""
        mock_user = MagicMock()
        mock_user.role = Role.ADMIN

        role_checker = require_role(Role.ADMIN)

        with patch("app.middleware.auth.get_current_user", return_value=mock_user):
            result = await role_checker(mock_user)

            assert result.role == Role.ADMIN

    @pytest.mark.asyncio
    async def test_require_role_insufficient_permissions(self):
        """Test role requirement with insufficient permissions."""
        mock_user = MagicMock()
        mock_user.role = Role.USER

        role_checker = require_role(Role.ADMIN)

        with pytest.raises(HTTPException) as exc_info:
            await role_checker(mock_user)

        assert exc_info.value.status_code == 403
