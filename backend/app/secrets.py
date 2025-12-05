"""
GCP Secret Manager integration with environment variable fallback.

Usage:
    from app.secrets import get_secret

    # Will try Secret Manager first (if enabled), then env vars
    api_key = get_secret("API_KEY")

    # Force env var only (skip Secret Manager)
    api_key = get_secret("API_KEY", use_secret_manager=False)
"""
import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import to avoid dependency when not using Secret Manager
_secret_manager_client = None


def _get_secret_manager_client():
    """Get or create Secret Manager client (lazy initialization)."""
    global _secret_manager_client

    if _secret_manager_client is None:
        try:
            from google.cloud import secretmanager

            _secret_manager_client = secretmanager.SecretManagerServiceClient()
            logger.info("Secret Manager client initialized")
        except ImportError:
            logger.warning(
                "google-cloud-secret-manager not installed. "
                "Install with: pip install google-cloud-secret-manager"
            )
            return None
        except Exception as e:
            logger.warning(f"Failed to initialize Secret Manager client: {e}")
            return None

    return _secret_manager_client


def get_secret(
    secret_name: str,
    project_id: Optional[str] = None,
    version: str = "latest",
    use_secret_manager: Optional[bool] = None,
    default: Optional[str] = None,
) -> Optional[str]:
    """
    Get a secret value from GCP Secret Manager or environment variables.

    Priority:
    1. If use_secret_manager=True, try Secret Manager first
    2. Fall back to environment variable
    3. Return default if neither found

    Args:
        secret_name: Name of the secret (also used as env var name)
        project_id: GCP project ID (defaults to config or GOOGLE_CLOUD_PROJECT)
        version: Secret version (default: "latest")
        use_secret_manager: Override config setting. None = use config
        default: Default value if secret not found

    Returns:
        Secret value or default

    Example:
        # These are equivalent if USE_SECRET_MANAGER=true
        api_key = get_secret("HELGER_API_KEY")

        # Force environment variable only
        api_key = get_secret("HELGER_API_KEY", use_secret_manager=False)

        # Specific project and version
        api_key = get_secret("API_KEY", project_id="my-project", version="2")
    """
    from app.config import get_settings

    settings = get_settings()

    # Determine if we should use Secret Manager
    if use_secret_manager is None:
        use_secret_manager = settings.use_secret_manager

    # Resolve project ID
    if project_id is None:
        project_id = settings.gcp_project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")

    # Try Secret Manager first (if enabled and configured)
    if use_secret_manager and project_id:
        client = _get_secret_manager_client()
        if client:
            try:
                # Build the resource name
                name = f"projects/{project_id}/secrets/{secret_name}/versions/{version}"

                # Access the secret
                response = client.access_secret_version(request={"name": name})
                secret_value = response.payload.data.decode("UTF-8")

                logger.debug(f"Retrieved secret '{secret_name}' from Secret Manager")
                return secret_value

            except Exception as e:
                logger.debug(
                    f"Secret '{secret_name}' not found in Secret Manager: {e}. "
                    "Falling back to environment variable."
                )

    # Fall back to environment variable
    env_value = os.environ.get(secret_name)
    if env_value is not None:
        logger.debug(f"Retrieved '{secret_name}' from environment variable")
        return env_value

    # Return default
    if default is not None:
        logger.debug(f"Using default value for '{secret_name}'")
        return default

    logger.warning(f"Secret '{secret_name}' not found in Secret Manager or environment")
    return None


@lru_cache(maxsize=100)
def get_secret_cached(
    secret_name: str,
    project_id: Optional[str] = None,
    version: str = "latest",
) -> Optional[str]:
    """
    Cached version of get_secret for frequently accessed secrets.

    Note: Cache does not expire automatically. Clear with:
        get_secret_cached.cache_clear()
    """
    return get_secret(secret_name, project_id, version)


def list_secrets(project_id: Optional[str] = None) -> list[str]:
    """
    List all available secrets in Secret Manager.

    Args:
        project_id: GCP project ID

    Returns:
        List of secret names
    """
    from app.config import get_settings

    settings = get_settings()

    if project_id is None:
        project_id = settings.gcp_project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")

    if not project_id:
        logger.warning("No project ID configured for Secret Manager")
        return []

    client = _get_secret_manager_client()
    if not client:
        return []

    try:
        parent = f"projects/{project_id}"
        secrets = []

        for secret in client.list_secrets(request={"parent": parent}):
            # Extract just the secret name from the full path
            name = secret.name.split("/")[-1]
            secrets.append(name)

        return secrets

    except Exception as e:
        logger.error(f"Failed to list secrets: {e}")
        return []


def create_secret(
    secret_name: str,
    secret_value: str,
    project_id: Optional[str] = None,
) -> bool:
    """
    Create a new secret in Secret Manager.

    Args:
        secret_name: Name for the new secret
        secret_value: The secret value
        project_id: GCP project ID

    Returns:
        True if successful, False otherwise
    """
    from app.config import get_settings

    settings = get_settings()

    if project_id is None:
        project_id = settings.gcp_project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")

    if not project_id:
        logger.error("No project ID configured for Secret Manager")
        return False

    client = _get_secret_manager_client()
    if not client:
        return False

    try:
        parent = f"projects/{project_id}"

        # Create the secret
        secret = client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_name,
                "secret": {"replication": {"automatic": {}}},
            }
        )

        # Add the secret version (actual value)
        client.add_secret_version(
            request={
                "parent": secret.name,
                "payload": {"data": secret_value.encode("UTF-8")},
            }
        )

        logger.info(f"Created secret '{secret_name}'")
        return True

    except Exception as e:
        logger.error(f"Failed to create secret '{secret_name}': {e}")
        return False
