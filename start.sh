#!/bin/bash
set -e

echo "=== Running database migrations ==="
cd /app/backend
python -m alembic upgrade head
echo "=== Migrations complete ==="

echo "=== Starting FastAPI on port ${PORT} ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
