import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.routers import lookup, validation, schemas
from app.exceptions import PeppolAPIException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Peppol Tools API",
    version="1.0.0",
    description="XML transformation, validation, and Peppol lookup services",
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Global exception handlers
@app.exception_handler(PeppolAPIException)
async def peppol_exception_handler(request: Request, exc: PeppolAPIException):
    """Handle custom Peppol API exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "type": type(exc).__name__},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "type": "InternalError"},
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for prod
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers - v1 API (versioned)
app.include_router(lookup.router, prefix="/api/v1/lookup", tags=["lookup"])
app.include_router(validation.router, prefix="/api/v1/validation", tags=["validation"])
app.include_router(schemas.router, prefix="/api/v1/schemas", tags=["schemas"])

# Legacy routes (backward compatibility) - will be deprecated
app.include_router(lookup.router, prefix="/api/lookup", tags=["lookup-legacy"], include_in_schema=False)
app.include_router(validation.router, prefix="/api/validation", tags=["validation-legacy"], include_in_schema=False)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "name": "Peppol Tools API",
        "version": "1.0.0",
        "api_version": "v1",
        "docs": "/docs",
        "endpoints": {
            "lookup": "/api/v1/lookup",
            "validation": "/api/v1/validation",
            "schemas": "/api/v1/schemas",
            "health": "/health",
        },
    }


# Global rate limits can be applied per-router or per-endpoint
# Example usage in routers:
# from slowapi import Limiter
# limiter = Limiter(key_func=get_remote_address)
# @router.post("/")
# @limiter.limit("10/minute")
# async def my_endpoint(request: Request, ...):
