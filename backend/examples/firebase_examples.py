"""
Firebase Integration Examples.

Demonstrates usage of Firebase Auth, Firestore, Secret Manager, and logging.
"""
import asyncio
from datetime import datetime

from app.config import settings
from app.models.user import Role, UserCreate, UserUpdate
from app.services.firebase_auth import get_firebase_auth_service
from app.services.secret_manager import get_secret_manager_service
from app.services.user_service import get_user_service
from app.utils.logger import bind_context, configure_logging, get_logger

# Configure logging
configure_logging(enable_cloud_logging=settings.enable_cloud_logging)
logger = get_logger(__name__)


async def example_firebase_auth():
    """
    Example: Firebase Authentication operations.

    Demonstrates:
    - Creating users
    - Verifying tokens
    - Updating user properties
    - Custom claims
    - Deleting users
    """
    logger.info("=== Firebase Auth Examples ===")

    auth_service = get_firebase_auth_service()

    try:
        # 1. Create user
        logger.info("Creating user...")
        user = await auth_service.create_user(
            email="example@test.com",
            password="SecurePassword123",
            display_name="Example User",
            email_verified=False,
        )
        logger.info("User created", uid=user["uid"], email=user["email"])

        # 2. Get user by UID
        logger.info("Getting user by UID...")
        retrieved_user = await auth_service.get_user_by_uid(user["uid"])
        logger.info("User retrieved", display_name=retrieved_user["display_name"])

        # 3. Get user by email
        logger.info("Getting user by email...")
        user_by_email = await auth_service.get_user_by_email("example@test.com")
        logger.info("User found by email", uid=user_by_email["uid"])

        # 4. Update user
        logger.info("Updating user...")
        updated_user = await auth_service.update_user(
            uid=user["uid"], display_name="Updated Name", email_verified=True
        )
        logger.info("User updated", display_name=updated_user["display_name"])

        # 5. Set custom claims (for role-based access control)
        logger.info("Setting custom claims...")
        await auth_service.set_custom_user_claims(
            uid=user["uid"], claims={"role": "admin", "permissions": ["read", "write"]}
        )
        logger.info("Custom claims set")

        # 6. Create custom token
        logger.info("Creating custom token...")
        custom_token = await auth_service.create_custom_token(uid=user["uid"], claims={"premium": True})
        logger.info("Custom token created", token_length=len(custom_token))

        # 7. Revoke refresh tokens (force re-authentication)
        logger.info("Revoking refresh tokens...")
        await auth_service.revoke_refresh_tokens(user["uid"])
        logger.info("Refresh tokens revoked")

        # Cleanup
        logger.info("Cleaning up...")
        await auth_service.delete_user(user["uid"])
        logger.info("User deleted successfully")

    except Exception as e:
        logger.error("Firebase auth example failed", error=str(e), exc_info=True)


async def example_user_service():
    """
    Example: User Service (Firestore) operations.

    Demonstrates:
    - Creating users with Firestore
    - Reading user data
    - Updating users
    - Listing users with pagination
    - Deleting users
    """
    logger.info("=== User Service Examples ===")

    user_service = get_user_service()

    try:
        # 1. Create user
        logger.info("Creating user in Firestore...")
        user_data = UserCreate(
            email="firestore@test.com",
            password="SecurePassword123",
            display_name="Firestore User",
            role=Role.USER,
            email_verified=False,
        )
        user = await user_service.create_user(user_data)
        logger.info("User created in Firestore", uid=user.uid, email=user.email)

        # 2. Get user by UID
        logger.info("Getting user from Firestore...")
        retrieved_user = await user_service.get_user(user.uid)
        logger.info(
            "User retrieved",
            uid=retrieved_user.uid,
            created_at=retrieved_user.created_at.isoformat(),
        )

        # 3. Get user by email
        logger.info("Getting user by email...")
        user_by_email = await user_service.get_user_by_email("firestore@test.com")
        logger.info("User found", uid=user_by_email.uid)

        # 4. Update user
        logger.info("Updating user...")
        update_data = UserUpdate(display_name="Updated Firestore User", email_verified=True)
        updated_user = await user_service.update_user(user.uid, update_data)
        logger.info("User updated", display_name=updated_user.display_name)

        # 5. Update last sign-in
        logger.info("Updating last sign-in...")
        await user_service.update_last_sign_in(user.uid)
        logger.info("Last sign-in updated")

        # 6. List users
        logger.info("Listing users...")
        users = await user_service.list_users(limit=10, offset=0)
        logger.info("Users listed", count=len(users))

        # Cleanup
        logger.info("Cleaning up...")
        await user_service.delete_user(user.uid)
        logger.info("User deleted successfully")

    except Exception as e:
        logger.error("User service example failed", error=str(e), exc_info=True)


async def example_secret_manager():
    """
    Example: Secret Manager operations.

    Demonstrates:
    - Getting secrets
    - Creating secrets
    - Updating secrets
    - Listing secrets
    - Deleting secrets
    """
    logger.info("=== Secret Manager Examples ===")

    if not settings.use_secret_manager:
        logger.warning("Secret Manager disabled, using environment variables")
        return

    secret_service = get_secret_manager_service()

    try:
        # 1. Create secret
        logger.info("Creating secret...")
        secret_id = "example_secret"
        await secret_service.create_secret(
            secret_id=secret_id, value="secret_value_123", labels={"env": "development"}
        )
        logger.info("Secret created", secret_id=secret_id)

        # 2. Get secret
        logger.info("Getting secret...")
        value = await secret_service.get_secret(secret_id)
        logger.info("Secret retrieved", length=len(value))

        # 3. Update secret
        logger.info("Updating secret...")
        await secret_service.update_secret(secret_id, "new_secret_value_456")
        logger.info("Secret updated")

        # 4. Get updated secret
        new_value = await secret_service.get_secret(secret_id)
        logger.info("Updated secret retrieved", length=len(new_value))

        # 5. List secrets
        logger.info("Listing secrets...")
        secrets = await secret_service.list_secrets()
        logger.info("Secrets listed", count=len(secrets))

        # 6. Clear cache
        logger.info("Clearing cache...")
        secret_service.clear_cache(secret_id)
        logger.info("Cache cleared")

        # Cleanup
        logger.info("Cleaning up...")
        await secret_service.delete_secret(secret_id)
        logger.info("Secret deleted successfully")

    except Exception as e:
        logger.error("Secret manager example failed", error=str(e), exc_info=True)


async def example_structured_logging():
    """
    Example: Structured logging with context.

    Demonstrates:
    - Basic logging
    - Context binding
    - Error logging
    - Different log levels
    """
    logger.info("=== Structured Logging Examples ===")

    # 1. Simple logging
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")

    # 2. Logging with context
    logger.info(
        "User logged in",
        user_id="user123",
        email="user@example.com",
        ip_address="192.168.1.1",
        timestamp=datetime.utcnow().isoformat(),
    )

    # 3. Bind context (included in all subsequent logs)
    bind_context(request_id="req-123", user_id="user456", tenant_id="tenant789")

    logger.info("Processing payment")  # Includes request_id, user_id, tenant_id
    logger.info("Payment completed", amount=100.00, currency="USD")

    # 4. Error logging with exception info
    try:
        raise ValueError("Something went wrong")
    except Exception as e:
        logger.error("Operation failed", error=str(e), error_type=type(e).__name__, exc_info=True)

    # 5. Performance logging
    import time

    start_time = time.time()
    # Simulate work
    await asyncio.sleep(0.1)
    duration = time.time() - start_time
    logger.info("Operation completed", duration_ms=int(duration * 1000), operation="data_fetch")


async def example_complete_workflow():
    """
    Example: Complete user registration and authentication workflow.

    Demonstrates:
    - User registration
    - Login simulation
    - Profile update
    - Role-based operations
    """
    logger.info("=== Complete Workflow Example ===")

    auth_service = get_firebase_auth_service()
    user_service = get_user_service()

    try:
        # 1. User Registration
        logger.info("Step 1: User Registration")
        user_data = UserCreate(
            email="workflow@test.com",
            password="WorkflowPassword123",
            display_name="Workflow User",
            role=Role.USER,
        )
        user = await user_service.create_user(user_data)
        logger.info("User registered", uid=user.uid)

        # 2. Simulate login - create custom token
        logger.info("Step 2: Login Simulation")
        custom_token = await auth_service.create_custom_token(uid=user.uid)
        logger.info("Custom token created for login")

        # 3. Get user profile
        logger.info("Step 3: Get User Profile")
        profile = await user_service.get_user(user.uid)
        logger.info("Profile retrieved", display_name=profile.display_name, role=profile.role.value)

        # 4. Update profile
        logger.info("Step 4: Update Profile")
        update_data = UserUpdate(display_name="Updated Workflow User", email_verified=True)
        updated_profile = await user_service.update_user(user.uid, update_data)
        logger.info("Profile updated", display_name=updated_profile.display_name)

        # 5. Promote to admin
        logger.info("Step 5: Promote to Admin")
        admin_update = UserUpdate(role=Role.ADMIN)
        admin_user = await user_service.update_user(user.uid, admin_update)
        logger.info("User promoted to admin", role=admin_user.role.value)

        # 6. Perform admin operation (list all users)
        logger.info("Step 6: Admin Operation - List Users")
        all_users = await user_service.list_users(limit=100)
        logger.info("Listed all users", total_users=len(all_users))

        # 7. Logout - revoke tokens
        logger.info("Step 7: Logout - Revoke Tokens")
        await auth_service.revoke_refresh_tokens(user.uid)
        logger.info("Tokens revoked")

        # Cleanup
        logger.info("Cleaning up...")
        await user_service.delete_user(user.uid)
        logger.info("User deleted successfully")

    except Exception as e:
        logger.error("Complete workflow failed", error=str(e), exc_info=True)


async def main():
    """Run all examples."""
    logger.info("Starting Firebase integration examples...")

    # Run examples
    await example_firebase_auth()
    print("\n" + "=" * 80 + "\n")

    await example_user_service()
    print("\n" + "=" * 80 + "\n")

    await example_secret_manager()
    print("\n" + "=" * 80 + "\n")

    await example_structured_logging()
    print("\n" + "=" * 80 + "\n")

    await example_complete_workflow()

    logger.info("All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
