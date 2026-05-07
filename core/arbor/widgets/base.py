"""
Widget 基类 — 卡片式应用模板
每个 Widget = 一个 SQLite 文件 + CRUD 路由 + AI 可调用的 read/write 接口
"""

from __future__ import annotations

import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter

DATA_DIR = Path("data/widgets")


def _make_id() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(tz=timezone.utc).date().isoformat()


@dataclass
class ConfirmIntent:
    """确认面板数据结构"""
    widget_id: str
    action: str                              # create / update / delete
    summary: str                             # 人类可读的描述
    detail: dict[str, Any] = field(default_factory=dict)
    requires_confirm: bool = True


class Widget(ABC):
    """卡片基类 — 子类只需实现 init_db + handle_read + execute_write"""

    id: str = ""
    name: str = ""
    icon: str = ""

    def __init__(self) -> None:
        self.router = APIRouter(prefix=f"/api/widgets/{self.id}", tags=[f"Widget: {self.name}"])
        self._register_routes()

    # ── 数据库 ────────────────────────────────────────────────

    @property
    def db_path(self) -> Path:
        return DATA_DIR / f"{self.id}.db"

    def get_db(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @abstractmethod
    def init_db(self) -> None:
        """子类实现建表"""
        ...

    # ── AI 调度接口 ────────────────────────────────────────────

    @abstractmethod
    def handle_read(self, intent: str, params: dict) -> dict:
        """读操作：直接返回数据"""
        ...

    def prepare_write(self, intent: str, params: dict) -> ConfirmIntent:
        """写操作准备：返回确认数据，默认实现可被子类覆盖"""
        return ConfirmIntent(
            widget_id=self.id,
            action=intent,
            summary=f"写入 {self.name} 卡片",
            detail=params,
        )

    @abstractmethod
    def execute_write(self, intent: str, params: dict) -> dict:
        """写操作执行：确认后调用"""
        ...

    # ── 仪表盘状态 ────────────────────────────────────────────

    def get_state(self) -> dict:
        """返回仪表盘用摘要数据"""
        return {}

    # ── 路由注册 ──────────────────────────────────────────────

    def _register_routes(self) -> None:
        """子类在 __init__ 中手动注册路由"""
        raise NotImplementedError
