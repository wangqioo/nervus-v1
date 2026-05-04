"""
语义路由引擎 — 通过 ModelService 调用 LLM，< 2s
约 9% 场景，事件需结合上下文才能决策
"""

from __future__ import annotations
import json
import logging

from nervus_platform.apps.registry import AppRegistry
from nervus_platform.models.service import ModelService
from nervus_platform.models.schemas import ChatRequest, ChatMessage
from executor.flow_executor import FlowExecutor

logger = logging.getLogger("nervus.arbor.semantic_router")

ROUTING_PROMPT = """你是 Nervus 神经路由系统。你需要分析一个事件并决定如何处理。

当前用户状态（Context Graph）：
{context}

收到的事件：
主题：{subject}
数据：{payload}

已注册的 App 列表：
{apps}

请分析这个事件，判断：
1. 这个事件的语义是什么？
2. 哪些 App 可能需要处理这个事件？
3. 应该调用哪个 App 的哪个 Action？

以 JSON 格式返回，格式如下：
{{
  "semantic": "事件语义的一句话描述",
  "targets": [
    {{
      "app_id": "app的ID",
      "action": "action名称（可选）",
      "reason": "为什么路由到这里"
    }}
  ],
  "confidence": 0.0到1.0之间
}}"""


class SemanticRouter:
    def __init__(self, registry: AppRegistry, executor: FlowExecutor,
                 model_service: ModelService | None = None):
        self.registry = registry
        self.executor = executor
        self._model_service = model_service

    def set_model_service(self, svc: ModelService) -> None:
        self._model_service = svc


    async def route(self, subject: str, event_data: dict) -> bool:
        """
        语义路由：调用 ModelService LLM 推理决策。
        返回 True 表示已处理，False 表示无法处理。
        """
        if self._model_service is None:
            logger.warning("SemanticRouter: ModelService 未设置，跳过语义路由")
            return False

        context = await self._get_context_snapshot()
        apps_summary = self._get_apps_summary()

        prompt = ROUTING_PROMPT.format(
            context=json.dumps(context, ensure_ascii=False, indent=2),
            subject=subject,
            payload=json.dumps(event_data.get("payload", {}), ensure_ascii=False),
            apps=apps_summary,
        )

        req = ChatRequest(
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=0.1,
            max_tokens=512,
            extra={"response_format": {"type": "json_object"}},
        )

        try:
            result = await self._model_service.chat(req)
            if result.error:
                logger.error("语义路由推理失败: %s", result.error)
                return False
            decision = json.loads(result.content)
        except Exception as e:
            logger.error("语义路由推理失败: %s", e)
            return False

        targets = decision.get("targets", [])
        confidence = decision.get("confidence", 0)
        semantic = decision.get("semantic", "")

        logger.info("语义路由决策: %s，置信度 %s，目标 %s",
                    semantic, confidence, [t["app_id"] for t in targets])

        if not targets or confidence < 0.5:
            return False

        for target in targets:
            app_id = target.get("app_id")
            action = target.get("action")

            if action:
                try:
                    await self.registry.call_action(app_id, action, event_data.get("payload", {}))
                except Exception as e:
                    logger.error("语义路由执行失败 %s/%s: %s", app_id, action, e)
            else:
                subs = self.registry.find_subscribers(subject)
                for sub in subs:
                    if sub["app_id"] == app_id:
                        try:
                            await self.registry.send_intake(app_id, sub["handler"], event_data)
                        except Exception as e:
                            logger.error("语义路由 intake 失败 %s: %s", app_id, e)

        return True

    async def _get_context_snapshot(self) -> dict:
        try:
            from infra import redis_client
            if redis_client.client is None:
                return {}
            keys = await redis_client.client.keys("context:user:*")
            if not keys:
                return {}
            values = await redis_client.client.mget(*keys)
            result = {}
            for key, val in zip(keys, values):
                short = key[len("context:user:"):]
                if val:
                    try:
                        result[short] = json.loads(val)
                    except Exception:
                        result[short] = val
            return result
        except Exception:
            return {}

    def _get_apps_summary(self) -> str:
        lines = []
        for app in self.registry.list_apps():
            consumes = app.manifest.capabilities.consumes
            actions = [a.get("name", "") for a in app.manifest.capabilities.actions]
            lines.append(f"- {app.id} ({app.name}): 订阅={consumes}, actions={actions}")
        return "\n".join(lines) if lines else "（无已注册 App）"
