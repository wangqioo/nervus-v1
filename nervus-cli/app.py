"""Nervus CLI — Textual TUI 主界面
适配 3.5 寸 480×320 横屏（约 60列 × 20行）
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, RichLog, Static

import config
from client import ChatMessage, NervusClient
from voice import VoiceRecorder

logger = logging.getLogger("nervus.cli.app")

# ── 颜色常量 ──────────────────────────────────────────────────────────────────
C_ACCENT  = "bold #8B72FF"
C_TEAL    = "#5EEAB5"
C_DIM     = "dim white"
C_USER    = "bold white"
C_APP     = "#8B72FF"
C_WARN    = "bold yellow"
C_ERR     = "bold red"
C_OK      = "bold green"


# ── 自定义 Widget ─────────────────────────────────────────────────────────────

class StatusBar(Static):
    """顶部状态栏：标题 + 连接状态 + 时间"""

    connected: reactive[bool] = reactive(False)
    recording: reactive[bool] = reactive(False)
    _tick = 0

    def render(self):
        t = datetime.now().strftime("%H:%M")
        dot = f"[{C_OK}]●[/]" if self.connected else f"[{C_ERR}]●[/]"
        rec = f" [{C_ERR}]● REC[/]" if self.recording else ""
        return f"[{C_ACCENT}]Nervus[/]  {dot}{rec}  [{C_DIM}]{t}[/]"

    def update_time(self):
        self.refresh()


class HintBar(Static):
    """底部快捷键提示栏"""

    def render(self):
        keys = [
            (f"[{C_ACCENT}]V[/]", "语音"),
            (f"[{C_ACCENT}]S[/]", "状态"),
            (f"[{C_ACCENT}]A[/]", "应用"),
            (f"[{C_ACCENT}]L[/]", "日志"),
            (f"[{C_ACCENT}]?[/]", "帮助"),
            (f"[{C_ACCENT}]Q[/]", "退出"),
        ]
        parts = "  ".join(f"{k} {v}" for k, v in keys)
        return parts


# ── 主应用 ────────────────────────────────────────────────────────────────────

CSS = """
Screen {
    background: #07070E;
}

StatusBar {
    height: 1;
    background: #13132A;
    padding: 0 1;
    color: white;
}

#chat {
    height: 1fr;
    border: none;
    background: #07070E;
    padding: 0 1;
    scrollbar-size: 1 1;
    scrollbar-color: #8B72FF #13132A;
}

#input-row {
    height: 3;
    background: #13132A;
    border-top: solid #8B72FF;
    padding: 0 1;
    align: left middle;
}

#user-input {
    background: #07070E;
    color: white;
    border: none;
    height: 1;
    width: 1fr;
}

#user-input:focus {
    border: none;
}

#voice-btn {
    width: 8;
    height: 1;
    background: #1A1A3A;
    color: #8B72FF;
    border: none;
    margin-left: 1;
    content-align: center middle;
}

#voice-btn.recording {
    background: #FF6E7A;
    color: white;
}

HintBar {
    height: 1;
    background: #0D0D20;
    padding: 0 1;
    color: white;
}
"""


class NervusApp(App):
    CSS = CSS
    TITLE = "Nervus"
    BINDINGS = [
        Binding("ctrl+v", "toggle_voice", "语音", show=False),
        Binding("ctrl+s", "show_status", "状态", show=False),
        Binding("ctrl+a", "show_apps", "应用", show=False),
        Binding("ctrl+l", "show_logs", "日志", show=False),
        Binding("ctrl+h", "show_help", "帮助", show=False),
        Binding("ctrl+q", "quit", "退出", show=False),
        # 兼容小键盘/物理按键
        Binding("f1", "toggle_voice", "语音", show=False),
        Binding("f2", "show_status", "状态", show=False),
        Binding("f3", "show_apps", "应用", show=False),
        Binding("f4", "show_logs", "日志", show=False),
    ]

    def __init__(self):
        super().__init__()
        self._client = NervusClient()
        self._recorder = VoiceRecorder()
        self._recording = False
        self._poll_task: asyncio.Task | None = None
        self._clock_task: asyncio.Task | None = None

    # ── 布局 ─────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status-bar")
        yield RichLog(id="chat", highlight=True, markup=True, wrap=True)
        with Horizontal(id="input-row"):
            yield Input(placeholder="输入消息...", id="user-input")
            yield Static("[V]", id="voice-btn")
        yield HintBar(id="hint-bar")

    # ── 启动 & 关闭 ───────────────────────────────────────────────────────────

    async def on_mount(self):
        self._client.on_message(self._on_server_message)
        await self._client.connect()

        sb = self.query_one("#status-bar", StatusBar)
        sb.connected = self._client.is_connected

        self._print_system("Nervus 已启动。输入消息或按 Ctrl+V 语音输入。")
        self._print_system(f"Arbor Core: {config.ARBOR_URL}")

        # 启动后台任务
        self._poll_task = asyncio.create_task(self._poll_loop())
        self._clock_task = asyncio.create_task(self._clock_loop())

        self.query_one("#user-input", Input).focus()

    async def on_unmount(self):
        if self._poll_task:
            self._poll_task.cancel()
        if self._clock_task:
            self._clock_task.cancel()
        await self._client.close()

    # ── 后台循环 ──────────────────────────────────────────────────────────────

    async def _poll_loop(self):
        """无 NATS 时轮询通知"""
        while True:
            await asyncio.sleep(config.POLL_INTERVAL)
            await self._client.poll_notifications()
            # 更新连接状态
            sb = self.query_one("#status-bar", StatusBar)
            sb.connected = self._client.is_connected

    async def _clock_loop(self):
        """每 10 秒刷新时间"""
        while True:
            await asyncio.sleep(10)
            try:
                self.query_one("#status-bar", StatusBar).refresh()
            except NoMatches:
                pass

    # ── 消息收发 ──────────────────────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        self._print_user(text)
        await self._client.send_text(text)

    async def _on_server_message(self, cm: ChatMessage):
        """收到服务端消息（NATS 或轮询）"""
        label = cm.label()
        self._print_app(label, cm.text)

    # ── Actions ───────────────────────────────────────────────────────────────

    async def action_toggle_voice(self):
        if self._recording:
            self._recorder.stop()
            self._recording = False
            self._set_voice_btn(False)
            self._print_system("录音结束，识别中...")
        else:
            self._recording = True
            self._set_voice_btn(True)
            self._print_system("正在录音... 再按 Ctrl+V 结束")
            self._recorder.start()
            asyncio.create_task(self._run_asr())

    async def _run_asr(self):
        text = await self._recorder.listen(
            on_partial=lambda t: self._print_system(f"识别中: {t}", replace_last=True)
        )
        self._recording = False
        self._set_voice_btn(False)
        if text:
            inp = self.query_one("#user-input", Input)
            inp.value = text
            self._print_user(text)
            await self._client.send_text(text)
        else:
            self._print_system("未识别到语音")

    async def action_show_status(self):
        self._print_system("查询系统状态...")
        status = await self._client.get_status()
        health = await self._client.get_health()

        lines = ["─── 系统状态 ───"]
        for svc, state in health.items():
            icon = "✓" if state == "connected" else "✗"
            color = C_OK if state == "connected" else C_ERR
            lines.append(f"[{color}]{icon}[/] {svc}: {state}")
        n_apps = status.get("apps_registered", 0)
        n_flows = status.get("flows_loaded", 0)
        lines.append(f"应用: {n_apps}  流程: {n_flows}")
        self._print_block(lines)

    async def action_show_apps(self):
        self._print_system("查询应用列表...")
        apps = await self._client.get_apps()
        if not apps:
            self._print_system("无已注册应用")
            return
        lines = ["─── 已注册应用 ───"]
        for a in apps:
            status = a.get("status", "unknown")
            color = C_OK if status == "online" else C_DIM
            lines.append(f"[{color}]{'▶' if status=='online' else '○'}[/] {a['id']}")
        self._print_block(lines)

    async def action_show_logs(self):
        self._print_system("查询执行日志...")
        logs = await self._client.get_recent_logs(8)
        if not logs:
            self._print_system("暂无日志")
            return
        lines = ["─── 最近执行 ───"]
        for l in logs:
            ok = l.get("status") == "success"
            color = C_OK if ok else C_ERR
            ms = l.get("duration_ms", 0)
            lines.append(
                f"[{color}]{'✓' if ok else '✗'}[/] [{C_DIM}]{l.get('trigger','?')}[/] "
                f"→ {l.get('flow_id','?')} [{C_DIM}]{ms}ms[/]"
            )
        self._print_block(lines)

    async def action_show_help(self):
        lines = [
            "─── 快捷键 ───",
            f"[{C_ACCENT}]Ctrl+V / F1[/]  语音输入",
            f"[{C_ACCENT}]Ctrl+S / F2[/]  系统状态",
            f"[{C_ACCENT}]Ctrl+A / F3[/]  应用列表",
            f"[{C_ACCENT}]Ctrl+L / F4[/]  执行日志",
            f"[{C_ACCENT}]Ctrl+H[/]       帮助",
            f"[{C_ACCENT}]Ctrl+Q[/]       退出",
            "",
            "直接输入文字发送到 Nervus Agent",
        ]
        self._print_block(lines)

    # ── 打印工具 ──────────────────────────────────────────────────────────────

    def _chat(self) -> RichLog:
        return self.query_one("#chat", RichLog)

    def _print_user(self, text: str):
        t = datetime.now().strftime("%H:%M")
        self._chat().write(f"[{C_DIM}]{t}[/] [{C_USER}]你:[/] {text}")

    def _print_app(self, label: str, text: str):
        t = datetime.now().strftime("%H:%M")
        self._chat().write(f"[{C_DIM}]{t}[/] [{C_APP}]{label}:[/] {text}")

    def _print_system(self, text: str, replace_last: bool = False):
        self._chat().write(f"[{C_DIM}]  ∷ {text}[/]")

    def _print_block(self, lines: list[str]):
        chat = self._chat()
        for line in lines:
            chat.write(line)

    def _set_voice_btn(self, recording: bool):
        btn = self.query_one("#voice-btn", Static)
        sb = self.query_one("#status-bar", StatusBar)
        if recording:
            btn.update("[bold red]● REC[/]")
            btn.add_class("recording")
            sb.recording = True
        else:
            btn.update("[#8B72FF][V][/]")
            btn.remove_class("recording")
            sb.recording = False


# ── 入口 ──────────────────────────────────────────────────────────────────────

def main():
    import logging
    logging.basicConfig(level=logging.WARNING)
    app = NervusApp()
    app.run()


if __name__ == "__main__":
    main()
