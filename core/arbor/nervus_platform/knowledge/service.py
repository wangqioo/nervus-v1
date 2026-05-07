from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from infra.db import db
from executor.embedding_pipeline import enqueue_knowledge_item
from .schemas import KnowledgeItem, KnowledgeSearchRequest, KnowledgeWriteRequest

logger = logging.getLogger("nervus.platform.knowledge")


class KnowledgeService:
    def __init__(self) -> None:
        self._model_service: Any = None

    def set_model_service(self, svc: Any) -> None:
        """注入 ModelService，用于向量语义搜索"""
        self._model_service = svc

    async def write(self, req: KnowledgeWriteRequest) -> KnowledgeItem | None:
        ts = (req.timestamp or datetime.now(tz=timezone.utc)).isoformat()
        tags_json = json.dumps(req.tags or [])
        try:
            row = await db.fetchrow(
                """INSERT INTO knowledge_items
                   (type, title, content, summary, source_url, source_app, tags, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   RETURNING id, type, title, summary, source_url, source_app, tags, timestamp, created_at""",
                req.type, req.title, req.content, req.summary,
                req.source_url, req.source_app, tags_json, ts,
            )
        except Exception as exc:
            logger.error("Knowledge write failed: %s", exc)
            return None

        if row is None:
            return None
        item = _row_to_item(row)
        embed_text = f"{req.title} {req.summary} {req.content}"[:2000]
        enqueue_knowledge_item(str(item.id), embed_text)
        return item

    async def search(self, req: KnowledgeSearchRequest) -> list[KnowledgeItem]:
        # 向量语义搜索路径
        if req.semantic and self._model_service is not None:
            try:
                return await self._semantic_search(req)
            except Exception as exc:
                logger.warning("向量搜索失败，降级为关键词搜索: %s", exc)

        # 关键词搜索降级路径
        return await self._keyword_search(req)

    async def _semantic_search(self, req: KnowledgeSearchRequest) -> list[KnowledgeItem]:
        """使用 Python 余弦相似度搜索（SQLite 无 pgvector）"""
        embedding = await self._model_service.embed(req.query)

        # 获取所有有 embedding 的条目
        conditions = ["embedding IS NOT NULL AND embedding != ''"]
        params: list[Any] = []
        if req.type:
            conditions.append("type = ?")
            params.append(req.type)
        if req.tags:
            tags_pattern = "%" + req.tags[0] + "%"
            conditions.append("tags LIKE ?")
            params.append(tags_pattern)

        where = " AND ".join(conditions)
        rows = await db.fetch(
            f"SELECT id, type, title, summary, source_url, source_app, tags, timestamp, created_at, embedding FROM knowledge_items WHERE {where}",
            *params,
        )

        # Python 端余弦相似度计算
        scored: list[tuple[KnowledgeItem, float]] = []
        for row in rows:
            emb_str = row.get("embedding", "")
            if not emb_str:
                continue
            try:
                row_embed = json.loads(emb_str)
            except (json.JSONDecodeError, TypeError):
                continue
            score = _cosine_similarity(embedding, row_embed)
            scored.append((_row_to_item(row), score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored[:req.limit]]

    async def _keyword_search(self, req: KnowledgeSearchRequest) -> list[KnowledgeItem]:
        """关键词 LIKE 文本搜索（SQLite LIKE 对 ASCII 大小写不敏感）"""
        conditions = ["(title LIKE ? OR content LIKE ? OR summary LIKE ?)"]
        pattern = f"%{req.query}%"
        params: list[Any] = [pattern, pattern, pattern]

        if req.type:
            conditions.append("type = ?")
            params.append(req.type)
        if req.tags:
            tags_pattern = "%" + req.tags[0] + "%"
            conditions.append("tags LIKE ?")
            params.append(tags_pattern)

        params.append(req.limit)
        where = " AND ".join(conditions)
        rows = await db.fetch(
            f"SELECT id, type, title, summary, source_url, source_app, tags, timestamp, created_at FROM knowledge_items WHERE {where} ORDER BY created_at DESC LIMIT ?",
            *params,
        )
        return [_row_to_item(r) for r in rows]


def _row_to_item(row: dict[str, Any]) -> KnowledgeItem:
    tags_raw = row.get("tags", "[]")
    if isinstance(tags_raw, str):
        try:
            tags = json.loads(tags_raw)
        except (json.JSONDecodeError, TypeError):
            tags = []
    else:
        tags = list(tags_raw or [])
    return KnowledgeItem(
        id=str(row["id"]),
        type=row["type"] or "",
        title=row["title"] or "",
        summary=row.get("summary") or "",
        source_url=row.get("source_url") or "",
        source_app=row.get("source_app") or "",
        tags=tags,
        timestamp=row.get("timestamp"),
        created_at=row.get("created_at"),
    )


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
