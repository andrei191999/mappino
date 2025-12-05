"""
Google Cloud Secret Manager Service.

Provides secure secret management with GCP Secret Manager.
Falls back to environment variables when not in GCP.
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from google.cloud import secretmanager
from google.api_core import exceptions as gcp_exceptions

from app.config import settings
from app.exceptions import PeppolAPIException

logger = logging.getLogger(__name__)


class SecretManagerError(PeppolAPIException):
    """Raised when Secret Manager operation fails."""

    def __init__(self, detail: str):
        super().__init__(detail=f"Secret Manager error: {detail}", status_code=500)


class SecretNotFoundError(PeppolAPIException):
    """Raised when secret is not found."""

    def __init__(self, secret_id: str):
        super().__init__(detail=f"Secret not found: {secret_id}", status_code=404)


class SecretManagerService:
    """
    Google Cloud Secret Manager Service.

    Manages secrets using GCP Secret Manager with local caching.
    Falls back to environment variables when Secret Manager is disabled.

    Example:
        ```python
        secret_service = SecretManagerService()

        # Get secret
        api_key = await secret_service.get_secret("api_key")

        # Create secret
        await secret_service.create_secret("new_secret", "secret_value")

        # Update secret
        await secret_service.update_secret("api_key", "new_value")
        ```
    """

    def __init__(self, cache_ttl_minutes: int = 5):
        """
        Initialize Secret Manager Service.

        Args:
            cache_ttl_minutes: Cache TTL in minutes (default: 5)
        """
        self._client: Optional[secretmanager.SecretManagerServiceClient] = None
        self._cache: dict[str, tuple[str, datetime]] = {}
        self._cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._use_secret_manager = settings.use_secret_manager
        self._project_id = settings.gcp_project_id

        if self._use_secret_manager:
            self._init_client()

    def _init_client(self) -> None:
        """
        Initialize Secret Manager client.

        Raises:
            SecretManagerError: If initialization fails
        """
        try:
            self._client = secretmanager.SecretManagerServiceClient()
            logger.info("Secret Manager client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Secret Manager: {e}")
            raise SecretManagerError(f"Failed to initialize Secret Manager: {str(e)}")

    async def get_secret(self, secret_id: str, version: str = "latest") -> str:
        """
        Get secret value.

        Retrieves secret from cache if available, otherwise from Secret Manager
        or environment variables.

        Args:
            secret_id: Secret identifier
            version: Secret version (default: "latest")

        Returns:
            str: Secret value

        Raises:
            SecretNotFoundError: If secret not found
            SecretManagerError: If operation fails

        Example:
            ```python
            # Get latest version
            api_key = await secret_service.get_secret("api_key")

            # Get specific version
            old_key = await secret_service.get_secret("api_key", version="1")
            ```
        """
        # Check cache first
        if secret_id in self._cache:
            value, cached_at = self._cache[secret_id]
            if datetime.utcnow() - cached_at < self._cache_ttl:
                logger.debug(f"Retrieved secret from cache: {secret_id}")
                return value

        # If Secret Manager disabled, use environment variables
        if not self._use_secret_manager:
            value = os.getenv(secret_id)
            if value is None:
                raise SecretNotFoundError(secret_id)
            logger.debug(f"Retrieved secret from environment: {secret_id}")
            return value

        # Get from Secret Manager
        try:
            name = f"projects/{self._project_id}/secrets/{secret_id}/versions/{version}"
            response = self._client.access_secret_version(request={"name": name})
            value = response.payload.data.decode("UTF-8")

            # Cache the value
            self._cache[secret_id] = (value, datetime.utcnow())

            logger.debug(f"Retrieved secret from Secret Manager: {secret_id}")
            return value

        except gcp_exceptions.NotFound:
            raise SecretNotFoundError(secret_id)
        except Exception as e:
            logger.error(f"Failed to get secret: {e}")
            raise SecretManagerError(f"Failed to get secret: {str(e)}")

    async def create_secret(self, secret_id: str, value: str, labels: dict | None = None) -> dict:
        """
        Create new secret.

        Args:
            secret_id: Secret identifier
            value: Secret value
            labels: Optional labels for the secret

        Returns:
            dict: Created secret metadata

        Raises:
            SecretManagerError: If creation fails

        Example:
            ```python
            await secret_service.create_secret(
                secret_id="api_key",
                value="secret_value",
                labels={"env": "production", "service": "api"}
            )
            ```
        """
        if not self._use_secret_manager:
            raise SecretManagerError("Secret Manager is disabled")

        try:
            parent = f"projects/{self._project_id}"

            # Create secret
            secret = self._client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {
                        "replication": {"automatic": {}},
                        "labels": labels or {},
                    },
                }
            )

            # Add secret version with value
            version = self._client.add_secret_version(
                request={
                    "parent": secret.name,
                    "payload": {"data": value.encode("UTF-8")},
                }
            )

            logger.info(f"Created secret: {secret_id}")
            return {
                "name": secret.name,
                "version": version.name,
                "created_at": secret.create_time,
            }

        except gcp_exceptions.AlreadyExists:
            raise SecretManagerError(f"Secret already exists: {secret_id}")
        except Exception as e:
            logger.error(f"Failed to create secret: {e}")
            raise SecretManagerError(f"Failed to create secret: {str(e)}")

    async def update_secret(self, secret_id: str, value: str) -> dict:
        """
        Update secret value by adding new version.

        This creates a new version of the secret with the updated value.

        Args:
            secret_id: Secret identifier
            value: New secret value

        Returns:
            dict: New version metadata

        Raises:
            SecretNotFoundError: If secret not found
            SecretManagerError: If update fails

        Example:
            ```python
            await secret_service.update_secret("api_key", "new_secret_value")
            ```
        """
        if not self._use_secret_manager:
            raise SecretManagerError("Secret Manager is disabled")

        try:
            parent = f"projects/{self._project_id}/secrets/{secret_id}"

            # Add new secret version
            version = self._client.add_secret_version(
                request={
                    "parent": parent,
                    "payload": {"data": value.encode("UTF-8")},
                }
            )

            # Invalidate cache
            if secret_id in self._cache:
                del self._cache[secret_id]

            logger.info(f"Updated secret: {secret_id}")
            return {
                "name": version.name,
                "created_at": version.create_time,
            }

        except gcp_exceptions.NotFound:
            raise SecretNotFoundError(secret_id)
        except Exception as e:
            logger.error(f"Failed to update secret: {e}")
            raise SecretManagerError(f"Failed to update secret: {str(e)}")

    async def delete_secret(self, secret_id: str) -> bool:
        """
        Delete secret and all its versions.

        Args:
            secret_id: Secret identifier

        Returns:
            bool: True if deleted successfully

        Raises:
            SecretNotFoundError: If secret not found
            SecretManagerError: If deletion fails
        """
        if not self._use_secret_manager:
            raise SecretManagerError("Secret Manager is disabled")

        try:
            name = f"projects/{self._project_id}/secrets/{secret_id}"
            self._client.delete_secret(request={"name": name})

            # Invalidate cache
            if secret_id in self._cache:
                del self._cache[secret_id]

            logger.info(f"Deleted secret: {secret_id}")
            return True

        except gcp_exceptions.NotFound:
            raise SecretNotFoundError(secret_id)
        except Exception as e:
            logger.error(f"Failed to delete secret: {e}")
            raise SecretManagerError(f"Failed to delete secret: {str(e)}")

    async def list_secrets(self) -> list[dict]:
        """
        List all secrets in the project.

        Returns:
            list[dict]: List of secret metadata

        Raises:
            SecretManagerError: If operation fails
        """
        if not self._use_secret_manager:
            raise SecretManagerError("Secret Manager is disabled")

        try:
            parent = f"projects/{self._project_id}"
            secrets = []

            for secret in self._client.list_secrets(request={"parent": parent}):
                secrets.append(
                    {
                        "name": secret.name,
                        "created_at": secret.create_time,
                        "labels": dict(secret.labels),
                    }
                )

            return secrets

        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            raise SecretManagerError(f"Failed to list secrets: {str(e)}")

    def clear_cache(self, secret_id: str | None = None) -> None:
        """
        Clear secret cache.

        Args:
            secret_id: Optional secret ID to clear (clears all if None)
        """
        if secret_id:
            if secret_id in self._cache:
                del self._cache[secret_id]
                logger.debug(f"Cleared cache for secret: {secret_id}")
        else:
            self._cache.clear()
            logger.debug("Cleared all secret cache")


# Singleton instance
_secret_manager_service: Optional[SecretManagerService] = None


def get_secret_manager_service() -> SecretManagerService:
    """
    Get singleton Secret Manager Service instance.

    Returns:
        SecretManagerService: Shared service instance
    """
    global _secret_manager_service
    if _secret_manager_service is None:
        _secret_manager_service = SecretManagerService()
    return _secret_manager_service
