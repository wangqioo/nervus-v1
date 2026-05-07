"""
SQLite 键值存储适配器 — 替换 redis.asyncio 客户端

向上兼容:
    client.get(key)       → str | None
    client.set(key, val)  → bool
    client.setex(key, ttl, val) → bool
    client.keys(pattern)  → list[str]
    client.mget(*keys)    → list[str | None]
    client.delete(key)    → int
"""

from __future__ import annotations

from typing import Any

from .db import db


class _RedisCompatClient:
    """模拟 redis.asyncio 客户端的轻量包装"""

    async def get(self, key: str) -> str | None:
        return await db.kv_get(key)

    async def set(self, key: str, value: str, **kwargs: Any) -> bool:
        ttl = kwargs.get("ex")
        await db.kv_set(key, value, ttl)
        return True

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        return await self.set(key, value, ex=ttl)

    async def keys(self, pattern: str) -> list[str]:
        return await db.kv_keys(pattern)

    async def mget(self, *keys: str) -> list[str | None]:
        results = []
        for key in keys:
            val = await db.kv_get(key)
            results.append(val)
        return results

    async def delete(self, key: str) -> int:
        await db.kv_delete(key)
        return 1

    async def ping(self) -> bool:
        return db.connected


client = _RedisCompatClient()


# ── 模块级别名（支持 redis_client.set(key, val, ttl) 风格） ─────────

async def get(key: str) -> str | None:
    return await client.get(key)


async def set(key: str, value: str, ttl: int | None = None) -> bool:
    """支持 ttl 作为第三位置参数（兼容旧的 redis_client.set(key, val, ttl) 调用）"""
    return await client.set(key, value, ex=ttl)


async def keys(pattern: str) -> list[str]:
    return await client.keys(pattern)


async def mget(*keys: str) -> list[str | None]:
    return await client.mget(*keys)


async def delete(key: str) -> int:
    return await client.delete(key)


async def connect(url: str = "") -> None:
    """SQLite 无需连接池 — 仅日志"""
    import logging
    logging.getLogger("nervus.infra.redis").info("Redis client → SQLite kv store")


async def disconnect() -> None:
    pass
