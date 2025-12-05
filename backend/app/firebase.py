"""
Firebase Admin SDK integration.

Provides:
- Firebase Admin SDK initialization
- Auth token verification middleware
- Firestore client access (optional)

Usage:
    from app.firebase import verify_firebase_token, get_firestore_client

    # In FastAPI endpoint with dependency injection
    @router.get("/protected")
    async def protected_route(user: dict = Depends(get_current_user)):
        return {"user_id": user["uid"]}

    # Manual token verification
    user = verify_firebase_token(token)
"""
import logging
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# Firebase Admin SDK (lazy initialization)
_firebase_app = None
_firestore_client = None


def _initialize_firebase():
    """Initialize Firebase Admin SDK (lazy)."""
    global _firebase_app

    if _firebase_app is not None:
        return _firebase_app

    from app.config import get_settings

    settings = get_settings()

    if not settings.firebase_enabled:
        logger.info("Firebase is disabled in settings")
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials

        # Check if already initialized
        try:
            _firebase_app = firebase_admin.get_app()
            return _firebase_app
        except ValueError:
            pass  # Not initialized yet

        # Initialize with credentials
        if settings.firebase_credentials_path:
            # Use service account file
            cred = credentials.Certificate(settings.firebase_credentials_path)
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info(
                f"Firebase initialized with credentials from: {settings.firebase_credentials_path}"
            )
        elif settings.google_application_credentials:
            # Use GOOGLE_APPLICATION_CREDENTIALS
            cred = credentials.Certificate(settings.google_application_credentials)
            _firebase_app = firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized with GOOGLE_APPLICATION_CREDENTIALS")
        else:
            # Use Application Default Credentials (works in GCP)
            _firebase_app = firebase_admin.initialize_app()
            logger.info("Firebase initialized with Application Default Credentials")

        return _firebase_app

    except ImportError:
        logger.warning(
            "firebase-admin not installed. Install with: pip install firebase-admin"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        return None


def get_firebase_app():
    """Get Firebase app instance (initializes if needed)."""
    return _initialize_firebase()


def get_firestore_client():
    """
    Get Firestore client instance.

    Returns None if Firebase is not configured or Firestore is unavailable.
    """
    global _firestore_client

    if _firestore_client is not None:
        return _firestore_client

    app = get_firebase_app()
    if not app:
        return None

    try:
        from firebase_admin import firestore

        _firestore_client = firestore.client()
        return _firestore_client
    except Exception as e:
        logger.error(f"Failed to get Firestore client: {e}")
        return None


def verify_firebase_token(token: str) -> Optional[dict]:
    """
    Verify a Firebase ID token.

    Args:
        token: Firebase ID token from client

    Returns:
        Decoded token (dict) with user info if valid, None otherwise

    The decoded token contains:
        - uid: User ID
        - email: User email (if available)
        - name: Display name (if available)
        - picture: Profile picture URL (if available)
        - email_verified: Whether email is verified
        - firebase: Firebase-specific claims
    """
    app = get_firebase_app()
    if not app:
        logger.warning("Firebase not initialized, cannot verify token")
        return None

    try:
        from firebase_admin import auth

        # Verify the token
        decoded_token = auth.verify_id_token(token)
        return decoded_token

    except Exception as e:
        logger.debug(f"Token verification failed: {e}")
        return None


# ===========================================
# FastAPI Dependencies for Auth
# ===========================================

# HTTP Bearer scheme for Swagger UI
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """
    FastAPI dependency to get current authenticated user.

    Usage:
        @router.get("/me")
        async def get_me(user: dict = Depends(get_current_user)):
            return {"uid": user["uid"], "email": user.get("email")}

    Raises:
        HTTPException 401 if not authenticated
        HTTPException 403 if token is invalid
    """
    from app.config import get_settings

    settings = get_settings()

    # If Firebase is disabled, return anonymous user (for development)
    if not settings.firebase_enabled:
        return {
            "uid": "anonymous",
            "email": None,
            "anonymous": True,
        }

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user = verify_firebase_token(token)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired token",
        )

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[dict]:
    """
    FastAPI dependency to optionally get current user.

    Returns None if not authenticated (no 401 error).

    Usage:
        @router.get("/data")
        async def get_data(user: Optional[dict] = Depends(get_optional_user)):
            if user:
                return {"data": "personalized", "user": user["uid"]}
            return {"data": "anonymous"}
    """
    from app.config import get_settings

    settings = get_settings()

    if not settings.firebase_enabled:
        return None

    if not credentials:
        return None

    return verify_firebase_token(credentials.credentials)


def require_email_verified(user: dict = Depends(get_current_user)) -> dict:
    """
    Dependency that requires email to be verified.

    Usage:
        @router.post("/sensitive")
        async def sensitive_action(user: dict = Depends(require_email_verified)):
            ...
    """
    if not user.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )
    return user


# ===========================================
# Firestore Helpers
# ===========================================


async def get_user_document(uid: str) -> Optional[dict]:
    """
    Get user document from Firestore.

    Args:
        uid: Firebase user ID

    Returns:
        User document as dict, or None if not found
    """
    db = get_firestore_client()
    if not db:
        return None

    try:
        doc = db.collection("users").document(uid).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Failed to get user document: {e}")
        return None


async def update_user_document(uid: str, data: dict) -> bool:
    """
    Update user document in Firestore.

    Args:
        uid: Firebase user ID
        data: Data to update/merge

    Returns:
        True if successful
    """
    db = get_firestore_client()
    if not db:
        return False

    try:
        db.collection("users").document(uid).set(data, merge=True)
        return True
    except Exception as e:
        logger.error(f"Failed to update user document: {e}")
        return False


# ===========================================
# Initialization check
# ===========================================


@lru_cache()
def is_firebase_available() -> bool:
    """Check if Firebase is available and configured."""
    return get_firebase_app() is not None
