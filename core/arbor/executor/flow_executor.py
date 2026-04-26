"""
Flow 执行引擎 — 按 JSON 配置顺序/并行执行步骤
"""

from __future__ import annotations
import json
import logging
import time
from datetime import datetime

import httpx

from platform.apps.registry import AppRegistry

logger = logging.getLogger("nervus.arbor.executor")


class FlowExecutor:
    def __init__(self, registry: AppRegistry):
        self.registry = registry

    async def execute(
        self,
        flow: dict,
        trigger_event: dict,
        context: dict | None = None,
    ) -> dict:
        """
        执行一个 Flow 配置。

        flow 格式：
        {
          "id": "photo-to-calorie",
          "trigger": "media.photo.classified",
          "condition": { "tags_contains": ["food"] },
          "steps": [
            { "app": "calorie-tracker", "action": "analyze_meal", "input": "$.photo_path" },
            { "context": "set", "field": "physical.last_meal", "value": "$.result.timestamp" },
            { "emit": "health.calorie.meal_logged", "payload": "$.result" }
          ]
        }
        """
        start = time.monotonic()
        flow_id = flow.get("id", "unknown")
        steps = flow.get("steps", [])
        state = {
            "event": trigger_event,
            "payload": trigger_event.get("payload", {}),
            "result": {},
            "context": context or {},
        }
        executed_steps = []
        status = "success"
        error = None

        logger.info(f"执行 Flow: {flow_id}，共 {len(steps)} 步")

        try:
            for i, step in enumerate(steps):
                step_result = await self._execute_step(step, state, flow_id, i)
                state["result"] = step_result
                executed_steps.append({"step": i, "type": self._step_type(step), "result": step_result})
        except Exception as e:
            status = "failed"
            error = str(e)
            logger.error(f"Flow {flow_id} 第 {len(executed_steps)} 步失败: {e}", exc_info=True)

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"Flow {flow_id} 执行完成: {status}，耗时 {duration_ms}ms")

        # 写入执行日志
        await self._log_execution(
            flow_id=flow_id,
            trigger_subject=trigger_event.get("subject", ""),
            trigger_payload=trigger_event.get("payload", {}),
            routing_mode=flow.get("_routing_mode", "fast"),
            steps_executed=executed_steps,
            status=status,
            duration_ms=duration_ms,
            error=error,
        )

        return {"flow_id": flow_id, "status": status, "duration_ms": duration_ms}

    async def _execute_step(self, step: dict, state: dict, flow_id: str, step_idx: int) -> dict:
        """执行单个步骤"""
        step_type = self._step_type(step)

        if step_type == "app_action":
            # 调用 App Action：{ "app": "calorie-tracker", "action": "analyze_meal", "input": "$.photo_path" }
            app_id = step["app"]
            action_name = step["action"]
            input_spec = step.get("input", {})
            params = self._resolve_params(input_spec, state)
            result = await self.registry.call_action(app_id, action_name, params)
            return result.get("result", result)

        elif step_type == "intake":
            # 向 App intake 接口发送事件：{ "intake": "calorie-tracker/photo_classified", "payload": "$.payload" }
            target = step["intake"]
            app_id, handler_path = target.split("/", 1)
            payload = self._resolve_value(step.get("payload", "$.payload"), state)
            event = {**state["event"], "payload": payload}
            result = await self.registry.send_intake(app_id, f"/intake/{handler_path}", event)
            return result.get("result", result)

        elif step_type == "context_set":
            # 写入 Context Graph：{ "context": "set", "field": "physical.last_meal", "value": "$.result.timestamp" }
            from infra import redis_client
            import json
            field = step["field"]
            value = self._resolve_value(step.get("value"), state)
            key = f"context:user:{field}"
            ttl_map = {"temporal.": 6*3600, "physical.": 24*3600, "cognitive.": 12*3600}
            ttl = next((t for prefix, t in ttl_map.items() if field.startswith(prefix)), 24*3600)
            await redis_client.set(key, json.dumps(value, default=str), ttl)
            return {"field": field, "value": value}

        elif step_type == "emit":
            # 发布事件：{ "emit": "health.calorie.meal_logged", "payload": "$.result" }
            from infra import nats_client
            import json as json_mod
            from datetime import datetime
            subject = step["emit"]
            payload = self._resolve_value(step.get("payload", {}), state)
            event = {
                "subject": subject,
                "payload": payload,
                "source_app": "arbor-core",
                "timestamp": datetime.utcnow().isoformat(),
            }
            await nats_client.publish(subject, json_mod.dumps(event).encode())
            return {"subject": subject, "payload": payload}

        elif step_type == "notify":
            # 触发全局弹窗：{ "notify": "global_popup", "title": "...", "body": "..." }
            return await self._send_notification(step, state)

        elif step_type == "parallel":
            # 并行执行多个步骤：{ "parallel": [ step1, step2 ] }
            import asyncio
            sub_steps = step["parallel"]
            results = await asyncio.gather(
                *[self._execute_step(s, state, flow_id, f"{step_idx}-{i}") for i, s in enumerate(sub_steps)],
                return_exceptions=True,
            )
            return {"parallel_results": [r for r in results if not isinstance(r, Exception)]}

        else:
            logger.warning(f"未知步骤类型: {step}")
            return {}

    def _step_type(self, step: dict) -> str:
        if "app" in step and "action" in step:
            return "app_action"
        if "intake" in step:
            return "intake"
        if "context" in step and step["context"] == "set":
            return "context_set"
        if "emit" in step:
            return "emit"
        if "notify" in step:
            return "notify"
        if "parallel" in step:
            return "parallel"
        return "unknown"

    def _resolve_params(self, input_spec, state: dict) -> dict:
        """解析步骤输入参数"""
        if isinstance(input_spec, str):
            # 单个路径，如 "$.photo_path"
            return {"photo_path": self._resolve_value(input_spec, state)}
        if isinstance(input_spec, dict):
            return {k: self._resolve_value(v, state) for k, v in input_spec.items()}
        return {}

    def _resolve_value(self, spec, state: dict):
        """解析 JSONPath 风格的值引用"""
        if not isinstance(spec, str):
            return spec
        if spec.startswith("$."):
            path = spec[2:].split(".")
            current = state
            for key in path:
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    return None
            return current
        return spec

    async def _send_notification(self, step: dict, state: dict) -> dict:
        """发送全局弹窗通知"""
        try:
            from infra import postgres_client
            import json
            title = self._resolve_value(step.get("title", "Nervus 通知"), state)
            body = self._resolve_value(step.get("body", ""), state)
            metadata = self._resolve_value(step.get("metadata", {}), state)
            if postgres_client.pool:
                await postgres_client.pool.execute(
                    "INSERT INTO notifications (type, title, body, metadata) VALUES ($1, $2, $3, $4)",
                    "global_popup", str(title), str(body), json.dumps(metadata or {})
                )
        except Exception as e:
            logger.error(f"发送通知失败: {e}")
        return {"type": "notification", "status": "sent"}

    async def _log_execution(self, **kwargs) -> None:
        try:
            from infra import postgres_client
            import json
            if postgres_client.pool:
                await postgres_client.pool.execute("""
                    INSERT INTO execution_logs
                    (flow_id, trigger_subject, trigger_payload, routing_mode, steps_executed, status, duration_ms, error)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                    kwargs.get("flow_id"),
                    kwargs.get("trigger_subject"),
                    json.dumps(kwargs.get("trigger_payload", {})),
                    kwargs.get("routing_mode", "fast"),
                    json.dumps(kwargs.get("steps_executed", [])),
                    kwargs.get("status"),
                    kwargs.get("duration_ms"),
                    kwargs.get("error"),
                )
        except Exception as e:
            logger.warning(f"记录执行日志失败: {e}")
