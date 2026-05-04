from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Callable, Awaitable

from pydantic import BaseModel, Field


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject: str
    payload: dict[str, Any] = {}
    source_app: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str | None = None


class AppService(BaseModel):
    container: str = ""
    internal_url: str = ""
    port: int | None = None


class AppCapabilities(BaseModel):
    actions: list[dict[str, Any]] = Field(default_factory=list)
    consumes: list[str] = Field(default_factory=list)
    emits: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    writes: list[str] = Field(default_factory=list)


class AppManifest(BaseModel):
    schema_version: str = "0.1"
    id: str
    name: str
    type: str = "nervus"
    version: str = "0.1.0"
    description: str = ""
    icon: str = "🧩"
    route: str = ""
    service: AppService = Field(default_factory=AppService)
    capabilities: AppCapabilities = Field(default_factory=AppCapabilities)


class AppConfig(BaseModel):
    app_id: str
    port: int = 8000
    internal_url: str = ""
    nats_url: str = "nats://localhost:4222"
    redis_url: str = "redis://localhost:6379"
    postgres_url: str = "postgresql://nervus:nervus_secret@localhost:5432/nervus"
    arbor_url: str = "http://localhost:8090"

    @classmethod
    def from_env(cls, app_id: str) -> "AppConfig":
        import os
        port = int(os.getenv("APP_PORT", "8000"))
        internal_url = os.getenv("APP_INTERNAL_URL", f"http://{app_id}:{port}")
        return cls(
            app_id=app_id,
            port=port,
            internal_url=internal_url,
            nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            postgres_url=os.getenv("POSTGRES_URL", "postgresql://nervus:nervus_secret@localhost:5432/nervus"),
            arbor_url=os.getenv("ARBOR_URL", "http://localhost:8090"),
        )


# type alias kept for compatibility within SDK
EventHandler = Callable[[Event], Awaitable[Any]]

# Backward-compatibility alias so old code (Manifest) still works
Manifest = AppManifest
