"""
快速路由引擎 — 模式匹配，< 100ms
约 90% 场景，事件语义清晰时直接匹配 Flow 配置
"""

from __future__ import annotations
import logging

from platform.apps.registry import AppRegistry
from executor.flow_executor import FlowExecutor
from executor.flow_loader import FlowLoader

logger = logging.getLogger("nervus.arbor.fast_router")


class FastRouter:
    def __init__(self, registry: AppRegistry, executor: FlowExecutor):
        self.registry = registry
        self.executor = executor
        self._flows: dict[str, dict] = {}

    def load_flows(self, flows: dict[str, dict]) -> None:
        self._flows = flows
        logger.info(f"快速路由引擎加载 {len(flows)} 个 Flow")

    async def route(self, subject: str, event_data: dict) -> bool:
        """
        尝试快速路由。
        返回 True 表示找到匹配并已执行，False 表示未匹配。
        """
        matched_flows = []
        for flow in self._flows.values():
            trigger = flow.get("trigger", "")
            if not FlowLoader._trigger_matches(trigger, subject):
                continue

            # 检查条件过滤
            condition = flow.get("condition", {})
            payload = event_data.get("payload", {})
            if condition and not self._check_condition(condition, payload):
                continue

            matched_flows.append(flow)

        if not matched_flows:
            return False

        logger.debug(f"快速路由匹配 {len(matched_flows)} 个 Flow: {subject}")

        for flow in matched_flows:
            flow_with_mode = {**flow, "_routing_mode": "fast"}
            await self.executor.execute(flow_with_mode, event_data)

        return True

    def _check_condition(self, condition: dict, payload: dict) -> bool:
        """检查 Flow 触发条件"""
        if "tags_contains" in condition:
            tags = payload.get("tags", [])
            required = condition["tags_contains"]
            if not any(t in tags for t in required):
                return False

        if "field_eq" in condition:
            for field, value in condition["field_eq"].items():
                if payload.get(field) != value:
                    return False

        if "field_exists" in condition:
            for field in condition["field_exists"]:
                if field not in payload:
                    return False

        return True
