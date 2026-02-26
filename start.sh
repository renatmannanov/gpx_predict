#!/bin/bash
set -e

echo "=== Fixing alembic_version column width (if needed) ==="
python -c "
import os, sqlalchemy
url = os.environ.get('DATABASE_URL', '')
if url:
    engine = sqlalchemy.create_engine(url)
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text(
            \"ALTER TABLE IF EXISTS alembic_version ALTER COLUMN version_num TYPE varchar(128)\"
        ))
        conn.commit()
    engine.dispose()
    print('alembic_version column widened to varchar(128)')
" 2>/dev/null || echo "Note: alembic_version fix skipped (table may not exist yet)"

echo "=== Running database migrations ==="
cd /app/backend
python -m alembic upgrade head
echo "=== Migrations complete ==="

echo "=== Starting FastAPI on port ${PORT} ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
