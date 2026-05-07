"""
SQLite 数据库适配器 — 替换 asyncpg PostgreSQL 客户端
保持与旧代码相似的 execute/fetch/fetchrow API

向上兼容:
    pool.execute(sql, *params) → 影响行数
    pool.fetch(sql, *params)    → list[dict]
    pool.fetchrow(sql, *params) → dict | None
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager
from typing import Any

from .db import db


_SQL_PARAM_RE = re.compile(r'\$\d+')


def _fix_sql(sql: str) -> str:
    """将 PostgreSQL $N 参数占位符转为 SQLite ?"""
    return _SQL_PARAM_RE.sub('?', sql)


class _ConnectionWrapper:
    """模拟 asyncpg.Connection 的轻量包装"""

    async def execute(self, sql: str, *params: Any) -> int:
        return await db.execute(_fix_sql(sql), *params)

    async def fetch(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        return await db.fetch(_fix_sql(sql), *params)

    async def fetchrow(self, sql: str, *params: Any) -> dict[str, Any] | None:
        return await db.fetchrow(_fix_sql(sql), *params)


class _PoolWrapper:
    """模拟 asyncpg.Pool 的轻量包装"""

    async def execute(self, sql: str, *params: Any) -> int:
        return await db.execute(_fix_sql(sql), *params)

    async def fetch(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        return await db.fetch(_fix_sql(sql), *params)

    async def fetchrow(self, sql: str, *params: Any) -> dict[str, Any] | None:
        return await db.fetchrow(_fix_sql(sql), *params)

    @asynccontextmanager
    async def acquire(self):
        """返回一个模拟的连接对象"""
        yield _ConnectionWrapper()


pool = _PoolWrapper()  # type: ignore[assignment]


async def connect(url: str = "") -> None:
    """连接到 SQLite 数据库（url 参数忽略，保持兼容）"""
    from pathlib import Path
    from .settings import settings
    await db.connect(settings.db_path)


async def disconnect() -> None:
    await db.disconnect()
