"""
Structured Logging Configuration.

Provides structured logging with JSON formatting for Cloud Logging integration.
"""
import logging
import sys
from typing import Any

import structlog
from google.cloud import logging as cloud_logging
from structlog.types import EventDict, Processor

from app.config import settings


def add_app_context(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add application context to log events.

    Args:
        logger: Logger instance
        method_name: Method name
        event_dict: Event dictionary

    Returns:
        EventDict: Event dictionary with app context
    """
    event_dict["app_name"] = settings.app_name
    event_dict["app_version"] = settings.app_version
    return event_dict


def add_severity_level(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add severity level for Cloud Logging.

    Maps Python log levels to Cloud Logging severity levels.

    Args:
        logger: Logger instance
        method_name: Method name
        event_dict: Event dictionary

    Returns:
        EventDict: Event dictionary with severity
    """
    level = event_dict.get("level", "").upper()

    # Map to Cloud Logging severity levels
    severity_map = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    }

    event_dict["severity"] = severity_map.get(level, "DEFAULT")
    return event_dict


def drop_color_message_key(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Remove color_message key from event dict.

    Args:
        logger: Logger instance
        method_name: Method name
        event_dict: Event dictionary

    Returns:
        EventDict: Event dictionary without color_message
    """
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging(enable_cloud_logging: bool = False) -> None:
    """
    Configure structured logging.

    Sets up structlog with JSON formatting and optional Cloud Logging integration.

    Args:
        enable_cloud_logging: Enable Google Cloud Logging (default: False)

    Example:
        ```python
        # In main.py
        configure_logging(enable_cloud_logging=True)

        # In any module
        from app.utils.logger import get_logger
        logger = get_logger(__name__)

        logger.info("User logged in", user_id="123", email="user@example.com")
        logger.error("Failed to process request", error=str(e), request_id="abc")
        ```
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    # Build processor chain
    processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_app_context,
        add_severity_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        drop_color_message_key,
    ]

    # Add development-friendly processor in debug mode
    if settings.debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # Use JSON in production
        processors.append(structlog.processors.JSONRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure Cloud Logging if enabled
    if enable_cloud_logging:
        try:
            client = cloud_logging.Client()
            client.setup_logging()
            logging.info("Cloud Logging configured")
        except Exception as e:
            logging.warning(f"Failed to configure Cloud Logging: {e}")


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        BoundLogger: Structured logger instance

    Example:
        ```python
        logger = get_logger(__name__)

        # Simple logging
        logger.info("Processing request")

        # With context
        logger.info("User created", user_id="123", email="user@example.com")

        # Error logging
        try:
            risky_operation()
        except Exception as e:
            logger.error("Operation failed", error=str(e), exc_info=True)
        ```
    """
    return structlog.get_logger(name)


class LoggerContextMiddleware:
    """
    FastAPI middleware to add request context to logs.

    Adds request_id and other context to all log messages within a request.

    Example:
        ```python
        from fastapi import FastAPI
        from app.utils.logger import LoggerContextMiddleware

        app = FastAPI()
        app.add_middleware(LoggerContextMiddleware)
        ```
    """

    def __init__(self, app):
        """Initialize middleware."""
        self.app = app

    async def __call__(self, scope, receive, send):
        """Process request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Generate request ID
        import uuid

        request_id = str(uuid.uuid4())

        # Bind context to structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=scope.get("path"),
            method=scope.get("method"),
        )

        # Add request_id to response headers
        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_request_id)


def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables to logger.

    Context variables will be included in all subsequent log messages
    in the current context (e.g., request).

    Args:
        **kwargs: Context variables to bind

    Example:
        ```python
        from app.utils.logger import bind_context, get_logger

        logger = get_logger(__name__)

        # Bind user context
        bind_context(user_id="123", tenant_id="abc")

        # All logs now include user_id and tenant_id
        logger.info("Processing request")
        # Output: {"event": "Processing request", "user_id": "123", "tenant_id": "abc", ...}
        ```
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """
    Unbind context variables.

    Args:
        *keys: Context variable keys to unbind

    Example:
        ```python
        unbind_context("user_id", "tenant_id")
        ```
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """
    Clear all context variables.

    Example:
        ```python
        clear_context()
        ```
    """
    structlog.contextvars.clear_contextvars()
