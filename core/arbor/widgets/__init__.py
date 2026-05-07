"""
Widget 注册表 — 管理所有卡片模块
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

from .base import Widget, ConfirmIntent
from .reminders import ReminderWidget
from .calendar import CalendarWidget
from .notes import NotesWidget
from .alarms import AlarmsWidget

logger = logging.getLogger("nervus.widgets")

# 注册所有卡片
_BUILTIN_WIDGETS: list[type[Widget]] = [
    ReminderWidget,
    CalendarWidget,
    NotesWidget,
    AlarmsWidget,
]


class WidgetRegistry:
    """卡片注册表 — 管理生命周期 + 路由挂载"""

    def __init__(self) -> None:
        self._widgets: dict[str, Widget] = {}

    def init_all(self) -> None:
        for cls in _BUILTIN_WIDGETS:
            w = cls()
            w.init_db()
            self._widgets[w.id] = w
            logger.info("Widget 已加载: %s (%s %s)", w.id, w.icon, w.name)

    def mount_all(self, app: FastAPI) -> None:
        for w in self._widgets.values():
            app.include_router(w.router)
            logger.info("Widget 路由已挂载: %s", w.id)

    def get(self, widget_id: str) -> Widget | None:
        return self._widgets.get(widget_id)

    def list(self) -> list[dict]:
        return [
            {"id": w.id, "name": w.name, "icon": w.icon, "state": w.get_state()}
            for w in self._widgets.values()
        ]

    def dispatch_read(self, widget_id: str, intent: str, params: dict) -> dict:
        """AI 读调度"""
        w = self.get(widget_id)
        if not w:
            return {"error": f"widget '{widget_id}' not found"}
        return w.handle_read(intent, params)

    def dispatch_write(self, widget_id: str, intent: str, params: dict) -> dict:
        """AI 写调度（返回确认数据）"""
        w = self.get(widget_id)
        if not w:
            return {"error": f"widget '{widget_id}' not found"}
        confirm = w.prepare_write(intent, params)
        return {"type": "confirm", "data": confirm}

    def dispatch_execute(self, widget_id: str, intent: str, params: dict) -> dict:
        """AI 写执行（确认后调用）"""
        w = self.get(widget_id)
        if not w:
            return {"error": f"widget '{widget_id}' not found"}
        return w.execute_write(intent, params)
