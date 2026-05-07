"""
Embedding Pipeline — 异步向量化任务队列
事件发生时自动对内容进行 embedding，写入 SQLite
避免阻塞主流程，在后台低优先级处理
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from infra.db import db

logger = logging.getLogger("nervus.arbor.embedding")


class EmbedTaskType(str, Enum):
    LIFE_EVENT = "life_event"
    KNOWLEDGE_ITEM = "knowledge_item"


@dataclass
class EmbedTask:
    task_type: EmbedTaskType
    record_id: str          # DB 中的行 id
    text: str               # 要 embedding 的文本
    table: str              # knowledge_items 等
    priority: int = 5       # 1=最高，10=最低
    created_at: datetime = field(default_factory=datetime.utcnow)


class EmbeddingPipeline:
    """
    后台 embedding 任务队列。
    - 任务加入队列后立即返回，不阻塞业务流程
    - 按优先级顺序处理
    - 失败自动重试（最多 3 次）
    - 通过 ModelService 统一调用本地 embed 接口
    """

    def __init__(self) -> None:
        self._model_service: Any = None
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=1000)
        self._running = False
        self._processed = 0
        self._failed = 0

    def set_model_service(self, svc: Any) -> None:
        self._model_service = svc

    def enqueue(self, task: EmbedTask) -> bool:
        """将 embedding 任务加入队列（非阻塞）"""
        try:
            self._queue.put_nowait((task.priority, task))
            logger.debug(f"Embedding 任务入队: {task.table}/{task.record_id}")
            return True
        except asyncio.QueueFull:
            logger.warning("Embedding 队列已满，跳过此任务")
            return False

    async def start(self) -> None:
        """启动后台处理循环"""
        self._running = True
        logger.info("Embedding Pipeline 启动")
        asyncio.create_task(self._worker())

    async def stop(self) -> None:
        self._running = False

    async def _worker(self) -> None:
        """主处理循环"""
        retry_counts: dict[str, int] = {}

        while self._running:
            try:
                try:
                    _, task = await asyncio.wait_for(self._queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    continue

                task_key = f"{task.table}/{task.record_id}"
                retries = retry_counts.get(task_key, 0)

                try:
                    embedding = await self._generate_embedding(task.text)
                    await self._save_embedding(task.table, task.record_id, embedding)
                    self._processed += 1
                    retry_counts.pop(task_key, None)
                    logger.debug(f"Embedding 完成: {task_key}")

                except Exception as e:
                    if retries < 3:
                        retry_counts[task_key] = retries + 1
                        retry_task = EmbedTask(
                            task_type=task.task_type,
                            record_id=task.record_id,
                            text=task.text,
                            table=task.table,
                            priority=min(task.priority + 2, 10),
                        )
                        await asyncio.sleep(2 ** retries)
                        self.enqueue(retry_task)
                        logger.warning(f"Embedding 失败，第 {retries+1} 次重试: {task_key}: {e}")
                    else:
                        self._failed += 1
                        retry_counts.pop(task_key, None)
                        logger.error(f"Embedding 最终失败，放弃: {task_key}: {e}")

                self._queue.task_done()
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Embedding worker 异常: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _generate_embedding(self, text: str) -> list[float]:
        if self._model_service is not None:
            return await self._model_service.embed(text[:2000])

        raise RuntimeError(
            "EmbeddingPipeline: _model_service is None. "
            "Call init_pipeline(model_service=...) before use."
        )

    async def _save_embedding(self, table: str, record_id: str, embedding: list[float]) -> None:
        """将 embedding 写入 SQLite"""
        embedding_str = json.dumps(embedding)
        await db.execute(
            f"UPDATE {table} SET embedding = ? WHERE id = ?",
            embedding_str, record_id,
        )

    @property
    def stats(self) -> dict:
        return {
            "queue_size": self._queue.qsize(),
            "processed": self._processed,
            "failed": self._failed,
        }


# ── 全局实例 ────────────────────────────────────────

_pipeline: EmbeddingPipeline | None = None


def init_pipeline(model_service=None) -> EmbeddingPipeline:
    global _pipeline
    pipeline = EmbeddingPipeline()
    if model_service:
        pipeline.set_model_service(model_service)
    _pipeline = pipeline
    return _pipeline


def get_pipeline() -> EmbeddingPipeline | None:
    return _pipeline


def enqueue_life_event(record_id: str, text: str, priority: int = 5) -> None:
    if _pipeline:
        _pipeline.enqueue(EmbedTask(
            task_type=EmbedTaskType.LIFE_EVENT,
            record_id=record_id,
            text=text,
            table="life_events",
            priority=priority,
        ))


def enqueue_knowledge_item(record_id: str, text: str, priority: int = 5) -> None:
    if _pipeline:
        _pipeline.enqueue(EmbedTask(
            task_type=EmbedTaskType.KNOWLEDGE_ITEM,
            record_id=record_id,
            text=text,
            table="knowledge_items",
            priority=priority,
        ))
