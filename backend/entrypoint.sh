#!/bin/sh
# Entrypoint script for Cloud Run
# Uses PORT environment variable if set, otherwise defaults to 8000

PORT=${PORT:-8000}

exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 2 \
    --proxy-headers \
    --forwarded-allow-ips "*"
