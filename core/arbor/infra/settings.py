from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    postgres_url: str
    redis_url: str
    nats_url: str
    config_dir: str
    app_port: int
    llm_url: str
    flows_dir: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            postgres_url=os.getenv("POSTGRES_URL", "postgresql://nervus:nervus_secret@localhost:5432/nervus"),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            nats_url=os.getenv("NATS_URL", "nats://localhost:4222"),
            config_dir=os.getenv("NERVUS_CONFIG_DIR", "/app/config"),
            app_port=int(os.getenv("APP_PORT", os.getenv("ARBOR_PORT", "8090"))),
            llm_url=os.getenv("LLAMA_URL", "http://nervus-llama:8080"),
            flows_dir=os.getenv("NERVUS_FLOWS_DIR", "/app/config/flows"),
        )
