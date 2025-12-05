# ===========================================
# Mappino API - Docker Build
# ===========================================
# Multi-stage build for smaller final image
#
# Build:
#   docker build -t mappino-api .
#
# Run:
#   docker run -p 8000:8000 mappino-api
#
# With environment file:
#   docker run -p 8000:8000 --env-file .env mappino-api

# ===========================================
# Stage 1: Builder
# ===========================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ===========================================
# Stage 2: Runtime
# ===========================================
FROM python:3.11-slim as runtime

# Labels
LABEL org.opencontainers.image.title="Mappino API"
LABEL org.opencontainers.image.description="XML transformation, validation, and Peppol lookup services"
LABEL org.opencontainers.image.version="1.0.0"

# Create non-root user for security
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code
COPY app/ ./app/

# Create directories for data and schemas (will be mounted as volumes in production)
RUN mkdir -p /app/schemas/xsd /app/schemas/schematron /app/schemas/rules \
    /app/mappers/user_uploads /app/data/codelists /app/data/output \
    && chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
# Using uvicorn with production settings
CMD ["python", "-m", "uvicorn", "app.main:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--workers", "2", \
    "--proxy-headers", \
    "--forwarded-allow-ips", "*"]
