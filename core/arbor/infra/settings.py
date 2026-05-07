"""
Arbor Core 配置 — 单进程模式，无外部服务 URL
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    """单进程 Arbor Core 配置"""

    # ── 存储路径 ───────────────────────────────────────────────────────
    config_dir: str = field(default_factory=lambda: os.getenv("CONFIG_DIR", "config"))
    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "data"))
    flows_dir: str = field(default_factory=lambda: os.getenv("FLOWS_DIR", "flows"))
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "data/nervus.db"))

    # ── 网络 ───────────────────────────────────────────────────────────
    app_port: int = field(default_factory=lambda: int(os.getenv("APP_PORT", "8090")))
    llm_url: str = field(default_factory=lambda: os.getenv("LLM_URL", "http://localhost:8080"))

    # ── 旧外部服务 URL（保留以保持兼容，实际不再使用） ──────────────
    postgres_url: str = ""
    redis_url: str = ""
    nats_url: str = ""

    def __post_init__(self) -> None:
        # 确保目录存在
        for d in [self.config_dir, self.data_dir, self.flows_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()


# 全局配置实例
settings = Settings()
