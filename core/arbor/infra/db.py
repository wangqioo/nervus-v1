"""
Nervus SQLite 数据库引擎
━━━━━━━━━━━━━━━━━━━━━━━━━
替换原 PostgreSQL + Redis + NATS，单文件数据库。
所有表在首次 connect() 时自动创建。

用法:
    from infra.db import db
    await db.connect(db_path="/path/to/nervus.db")
    rows = await db.fetch("SELECT * FROM notifications WHERE is_read = ?", 0)
    await db.disconnect()
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("nervus.infra.db")


class Database:
    """SQLite 数据库单例 — 线程安全，async 友好"""

    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None
        self._db_path: str = ""

    # ── 生命周期 ──────────────────────────────────────────────────────────

    async def connect(self, db_path: str = "") -> None:
        """初始化 SQLite 数据库并创建所有表"""
        db_path = db_path or "data/nervus.db"
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        await self._run(self._create_tables)
        logger.info("SQLite DB ready: %s", db_path)

    async def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("SQLite DB closed")

    @property
    def connected(self) -> bool:
        return self._conn is not None

    # ── 查询 API ─────────────────────────────────────────────────────────

    async def execute(self, sql: str, *params: Any) -> int:
        """执行 SQL，返回影响行数"""
        return await self._run(self._do_execute, sql, params)

    async def fetch(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        """查询多行，返回 dict 列表"""
        return await self._run(self._do_fetch, sql, params)

    async def fetchrow(self, sql: str, *params: Any) -> dict[str, Any] | None:
        """查询单行，返回 dict 或 None"""
        rows = await self.fetch(sql, *params)
        return rows[0] if rows else None

    async def fetchval(self, sql: str, *params: Any) -> Any:
        """查询标量值"""
        row = await self.fetchrow(sql, *params)
        if row is None:
            return None
        return list(row.values())[0]

    # ── 键值存储（替代 Redis） ─────────────────────────────────────────

    async def kv_get(self, key: str) -> str | None:
        """获取键值（自动处理 TTL 过期）"""
        row = await self.fetchrow(
            "SELECT value FROM context WHERE key = ? AND (ttl IS NULL OR ttl > ?)",
            key, int(time.time()),
        )
        return row["value"] if row else None

    async def kv_set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """设置键值（可选 TTL）"""
        expiry = int(time.time()) + ttl_seconds if ttl_seconds else None
        await self.execute(
            "INSERT OR REPLACE INTO context (key, value, ttl) VALUES (?, ?, ?)",
            key, value, expiry,
        )

    async def kv_delete(self, key: str) -> None:
        await self.execute("DELETE FROM context WHERE key = ?", key)

    async def kv_keys(self, pattern: str) -> list[str]:
        """匹配键名（% 通配符）"""
        sql_pattern = pattern.replace("*", "%")
        rows = await self.fetch("SELECT key FROM context WHERE key LIKE ?", sql_pattern)
        return [r["key"] for r in rows]

    # ── 内部 ──────────────────────────────────────────────────────────────

    async def _run(self, fn, *args) -> Any:
        """在后台线程运行同步 sqlite3 操作"""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, fn, *args)

    def _check_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call await db.connect() first")
        return self._conn

    def _do_execute(self, sql: str, params: tuple) -> int:
        conn = self._check_conn()
        try:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise

    def _do_fetch(self, sql: str, params: tuple) -> list[dict[str, Any]]:
        conn = self._check_conn()
        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def _create_tables(self) -> None:
        conn = self._check_conn()
        conn.executescript("""
            -- 键值存储（替代 Redis）
            CREATE TABLE IF NOT EXISTS context (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                ttl         INTEGER,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            -- 模型 API 密钥（替代 Redis）
            CREATE TABLE IF NOT EXISTS model_api_keys (
                model_id    TEXT PRIMARY KEY,
                api_key     TEXT NOT NULL,
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            -- 通知
            CREATE TABLE IF NOT EXISTS notifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                type        TEXT NOT NULL DEFAULT 'global_popup',
                title       TEXT,
                body        TEXT,
                metadata    TEXT DEFAULT '{}',
                is_read     INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            -- 执行日志
            CREATE TABLE IF NOT EXISTS execution_logs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_id         TEXT,
                trigger_subject TEXT,
                trigger_payload TEXT DEFAULT '{}',
                routing_mode    TEXT DEFAULT 'fast',
                steps_executed  TEXT DEFAULT '[]',
                status          TEXT,
                duration_ms     INTEGER,
                error           TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            -- 平台事件
            CREATE TABLE IF NOT EXISTS platform_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subject     TEXT,
                payload     TEXT DEFAULT '{}',
                source_app  TEXT DEFAULT 'system',
                created_at  TEXT DEFAULT (datetime('now'))
            );

            -- 知识条目
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                type        TEXT,
                title       TEXT,
                content     TEXT,
                summary     TEXT,
                source_url  TEXT,
                source_app  TEXT,
                tags        TEXT DEFAULT '[]',
                embedding   TEXT,
                timestamp   TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            -- App 注册表
            CREATE TABLE IF NOT EXISTS app_registry (
                app_id          TEXT PRIMARY KEY,
                name            TEXT,
                version         TEXT,
                description     TEXT,
                manifest        TEXT DEFAULT '{}',
                endpoint_url    TEXT,
                status          TEXT DEFAULT 'offline',
                last_heartbeat  TEXT,
                registered_at   TEXT DEFAULT (datetime('now'))
            );

            -- 索引
            CREATE INDEX IF NOT EXISTS idx_notifications_read    ON notifications (is_read);
            CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications (created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_exec_logs_created     ON execution_logs (created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_exec_logs_status      ON execution_logs (status);
            CREATE INDEX IF NOT EXISTS idx_platform_events_subject ON platform_events (subject);
            CREATE INDEX IF NOT EXISTS idx_platform_events_created ON platform_events (created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_knowledge_type        ON knowledge_items (type);
            CREATE INDEX IF NOT EXISTS idx_knowledge_timestamp   ON knowledge_items (timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_app_registry_status   ON app_registry (status);
        """)
        conn.commit()


# ── 全局单例 ────────────────────────────────────────────────────────────
db = Database()
