#!/bin/bash
# new-app.sh — Nervus 新 App 脚手架
# Usage: bash scripts/new-app.sh <app-id> <port>
# Example: bash scripts/new-app.sh habit-tracker 8017

set -e

APP_ID="$1"
PORT="$2"

if [ -z "$APP_ID" ] || [ -z "$PORT" ]; then
  echo "Usage: $0 <app-id> <port>"
  echo "Example: $0 habit-tracker 8017"
  exit 1
fi

# Derive names
CONTAINER="nervus-app-$(echo "$APP_ID" | sed 's/-tracker$//' | cut -c1-12)"
APP_DIR="apps/$APP_ID"

if [ -d "$APP_DIR" ]; then
  echo "Error: $APP_DIR already exists"
  exit 1
fi

echo "Creating $APP_DIR (port $PORT)..."
mkdir -p "$APP_DIR"

# ── manifest.json ─────────────────────────────────────────
cat > "$APP_DIR/manifest.json" << EOF
{
  "schema_version": "0.1",
  "id": "$APP_ID",
  "name": "$APP_ID",
  "type": "nervus",
  "version": "0.1.0",
  "description": "TODO: describe this app",
  "icon": "🔧",
  "route": "/api/$APP_ID",
  "service": {
    "container": "$CONTAINER",
    "internal_url": "http://$CONTAINER:$PORT",
    "port": $PORT
  },
  "capabilities": {
    "actions": [],
    "consumes": [],
    "emits": [],
    "models": [],
    "writes": []
  }
}
EOF

# ── requirements.txt ──────────────────────────────────────
cat > "$APP_DIR/requirements.txt" << 'EOF'
fastapi
uvicorn[standard]
httpx
EOF

# ── Dockerfile ────────────────────────────────────────────
cat > "$APP_DIR/Dockerfile" << EOF
FROM python:3.11-slim
WORKDIR /app
COPY sdk/python /app/nervus-sdk
COPY $APP_DIR/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \\
 && pip install --no-cache-dir /app/nervus-sdk -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY $APP_DIR/manifest.json /app/manifest.json
COPY $APP_DIR/. .
RUN mkdir -p /data
EXPOSE $PORT
CMD ["python", "main.py"]
EOF

# ── main.py ───────────────────────────────────────────────
cat > "$APP_DIR/main.py" << EOF
"""
$APP_ID — TODO: describe this app
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, "/app/nervus-sdk")
from nervus_sdk import NervusApp, Context, emit
from nervus_sdk.models import Event

nervus = NervusApp("$APP_ID")

DB_PATH = os.getenv("DB_PATH", "/data/$APP_ID.db")


def get_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                id         TEXT PRIMARY KEY,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)


init_db()


# ── REST API ──────────────────────────────────────────────

@nervus._api.get("/items")
async def list_items(limit: int = 50):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM items ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@nervus._api.post("/items")
async def create_item(body: dict):
    import uuid
    item_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO items (id, content, created_at) VALUES (?, ?, ?)",
            (item_id, body.get("content", ""), now)
        )
    return {"id": item_id, "status": "created"}


# ── State snapshot ────────────────────────────────────────

@nervus.state
async def get_state():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM items").fetchone()["c"]
    return {"total_items": total}


if __name__ == "__main__":
    nervus.run(port=int(os.getenv("APP_PORT", "$PORT")))
EOF

echo ""
echo "Done! Files created:"
ls "$APP_DIR/"
echo ""
echo "Next steps:"
echo "  1. Edit $APP_DIR/manifest.json  (name, icon, description, capabilities)"
echo "  2. Edit $APP_DIR/main.py        (business logic)"
echo "  3. Add service block to docker-compose.yml"
echo "  4. Add routes to core/caddy/Caddyfile (both HTTPS and :8900 blocks)"
echo "  5. docker compose build app-$APP_ID && docker compose up -d app-$APP_ID"
echo "  6. docker restart nervus-caddy"
echo ""
echo "  See docs/porting-guide.md for full details."
