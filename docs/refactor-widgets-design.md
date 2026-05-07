# Nervus 重构方案：卡片化 + 轻量化（Widget-First Refactor）

> 设计方案，用于指导后续重构实施。
> 状态：v0.1 · 设计阶段 · 讨论后可修改

---

## 一、核心理念

### 问题

Nervus 当前架构用 Docker 容器封装了 16 个独立 App，每个 App 是一整条独立的 FastAPI 进程，通过 NATS 消息总线 + Postgres 数据库通信。

```
传统聊天 vs. 状态管理的本质矛盾：

聊天界面  ← 适合 →  复杂/开放任务（LLM 推理、多步规划、知识问答）
图形卡片  ← 适合 →  简单/状态操作（待办、日历、闹钟、快速查看）
           ← 不适合 →  反过来了就是灾难
```

**当前痛点**：16 个 Docker 容器、Postgres、Redis、NATS 全栈启动只为跑一个 todo 管理，太重了。而且 chat 界面不适合「看一眼待办、秒改闹钟」这种高频低复杂度操作。

### 方案

**单进程 + 内嵌卡片（Widget-First Architecture）**

```
之前（1 平台 + 3 中间件 + 16 容器 = 20 个进程）：
  Arbor Core + Postgres + Redis + NATS + 16 个独立 App Docker 容器

之后（1 个进程，1 个数据库文件）：
  Arbor Core（内嵌所有 Widget + 聊天路由 + SQLite）
```

### 关键设计原则

1. **读操作直出，写操作过确认面板** — AI 不能不经确认写入数据
2. **数据隔离靠表/文件，不靠进程** — SQLite 天然支持多表隔离
3. **路由意图确认 → 延迟写入** — 先展示给用户看，点了"确认"再写
4. **聊天是复杂任务的入口，卡片是状态管理的界面** — 两者并存，各管各的

---

## 二、数据流

### 读操作

```
你说: "今天有什么待办"
    ↓
Arbor Core → 三级路由 → 识别为 read(todos) → 直接查 SQLite → 返回数据
    ↓
TUI 仪表盘展示 ── 或 ── 聊天面板展示
```

### 写操作

```
你说: "提醒我明天下午3点开会"
    ↓
Arbor Core → 三级路由 → 识别为 write(reminders, {title, time})
    ↓
        不直接写入
    ↓
意图确认面板（TUI 或图形界面弹窗）：
  ┌─────────────────────────────────────┐
  │  📌 写入: 提醒卡片                    │
  │  内容: "开会"                         │
  │  时间: 2026-05-08 15:00 (+08:00)     │
  │  [✓ 确认]  [✗ 取消]  [↻ 改路由]     │
  └─────────────────────────────────────┘
    ↓ 用户确认
写入 SQLite
    ↓
成功后，有需要则触发 Flow / 通知
```

### 跨卡片操作

```
"把今天没做完的事加到明天的日程里"
    ↓
路由 → 识别为跨卡片操作（read todos + write calendar）
    ↓
确认面板展示影响范围：
  ┌─────────────────────────────────────┐
  │  📌 跨卡片操作                        │
  │  从  todo    读取: 2 条未完成         │
  │  向  calendar 写入: 明日日程 × 2      │
  │  [✓ 确认全部]  [逐条确认]  [取消]    │
  └─────────────────────────────────────┘
```

---

## 三、架构变更

### 3.1 基础设施瘦身

| 组件 | 当前 | 目标 |
|------|------|------|
| **数据库** | PostgreSQL + pgvector | SQLite + sqlite-vec（或简单向量搜索） |
| **缓存** | Redis | I/O 用 aiosqlite，内存用 dict |
| **消息总线** | NATS | asyncio event bus |
| **App 注册** | Postgres 表 + HTTP 心跳 | Python 模块自动注册 |
| **日志** | Postgres 表 | 文件日志（保留最近 1000 条） |

**SQLite 文件布局**：

```
data/
├── core.db           # 系统元数据：路由、Flow、日志
├── widgets/
│   ├── todos.db
│   ├── calendar.db
│   ├── reminders.db
│   ├── notes.db
│   └── knowledge.db   # 知识库（含向量需要独立文件）
└── events.db         # 事件历史
```

**为什么还是多文件？** 隔离和迁移——想备份只备份 `widgets/calendar.db` 即可，不想连带 todos 一起。但代码层没有进程隔离成本。

### 3.2 代码结构变化

```
当前结构：
nervus-v1/
├── core/arbor/          # 平台基座
├── apps/                # 16 个独立 Docker App
│   ├── reminder/
│   ├── calendar/
│   ├── todos/           ← 当前不存在，用 reminder 替代
│   └── ...
├── sdk/                 # Python SDK
├── nervus-cli/          # TUI 客户端
└── docker-compose.yml

目标结构：
nervus-v1/
├── core/
│   ├── arbor/           # 平台核心（FastAPI + 路由 + 聊天）
│   │   ├── main.py
│   │   ├── router/      # 三级路由引擎（不变）
│   │   ├── executor/    # Flow 执行器（不变，但去掉 NATS/Redis 依赖）
│   │   ├── infra/       # 基础设施层（SQLite 替换 Postgres/Redis/NATS）
│   │   ├── metabolism/  # 代谢系统（设计已完成，待实现）
│   │   └── api/         # 平台 API
│   │
│   ├── widgets/         # 内嵌卡片模块（替换 apps/ 目录）
│   │   ├── __init__.py
│   │   ├── base.py      # Widget 基类（统一 schema + 确认面板协议）
│   │   ├── todos/
│   │   │   ├── __init__.py
│   │   │   ├── model.py     # SQLite schema + CRUD
│   │   │   ├── routes.py    # FastAPI 端点
│   │   │   └── card.html    # 卡片 HTML 模板
│   │   ├── calendar/
│   │   │   └── ...
│   │   ├── reminders/
│   │   │   └── ...
│   │   ├── notes/
│   │   │   └── ...
│   │   └── knowledge/
│   │       └── ...
│   │
│   └── asyncio_bus.py   # 替换 NATS，纯 asyncio 内存事件总线
│
├── nervus-cli/          # TUI 客户端（不变 + 仪表盘模式）
├── web/                 # 新增：图形化仪表盘页面（可选）
│   └── dashboard.html   # 所有卡片聚合在一个页面
│
├── run.py               # 单命令启动：docker 和 python 模式都能用
├── docker-compose.yml   # 保留但简化（可选，也可以删掉）
├── config/
│   ├── models.json      # 模型配置（不变）
│   └── flows/           # Flow 配置（不变）
└── docs/
    ├── metabolism-design.md
    ├── refactor-widgets-design.md     ← 本文档
    └── hardware-and-terminal-design.md
```

### 3.3 Widget 基类设计

```python
# core/widgets/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ConfirmIntent:
    """确认面板数据"""
    widget_id: str
    action: Literal["create", "update", "delete"]
    summary: str                          # "新增提醒：明天15:00开会"
    detail: dict[str, Any]               # 完整参数
    change_preview: str | None = None    # "旧: 14:00 → 新: 15:00"
    affected_count: int = 1
    requires_confirm: bool = True        # False = 可直接写入（低风险操作）


class Widget(ABC):
    """所有卡片模块的基类"""
    id: str
    name: str
    icon: str

    @abstractmethod
    async def handle_read(self, intent: str, params: dict) -> dict:
        """读操作：直接返回数据"""
        ...

    @abstractmethod
    async def prepare_write(self, intent: str, params: dict) -> ConfirmIntent:
        """写操作准备：返回确认面板数据，不执行写入"""
        ...

    @abstractmethod
    async def execute_write(self, intent: str, params: dict) -> dict:
        """写操作执行：只有确认后才调用"""
        ...

    async def search(self, query: str) -> list[dict]:
        """语义搜索本卡片数据"""
        return []
```

### 3.4 路由引擎适配

三级路由引擎（Fast → Semantic → Dynamic）逻辑不变，但路由不再通过 NATS 分配到 HTTP 端点，而是直接调用 Widget 方法：

```python
# 当前：通过 HTTP 调用 App 的 action 端点
result = await registry.call_action(app_id, action_name, params)

# 之后：直接调用 Widget 方法
widget = widget_registry.get("reminders")
if is_read_operation(intent):
    return await widget.handle_read(intent, params)
else:
    confirm = await widget.prepare_write(intent, params)
    # 返回确认面板给用户
    return {"type": "confirm", "data": confirm}
```

---

## 四、确认面板机制

### 4.1 交互流程

```
用户语句
    ↓
三级路由 → 识别意图 (read / write / delete / update)
    ↓
write 类 → 路由到对应 Widget → prepare_write() → 返回 ConfirmIntent
    ↓
主干进程将 ConfirmIntent → 发送到 nervus-cli（或 Web 仪表盘）
    ↓
nervus-cli 弹确认面板（在聊天界面叠加显示）
    ↓
用户操作：
  ├─ [确认] → 调用 widget.execute_write()
  ├─ [取消] → 丢弃
  └─ [改路由] → 让用户重新选择目标 Widget
```

### 4.2 nervus-cli 确认面板

```
──────────────────────────────────────────────────────────────
14:31 你: 提醒我明天下午3点开会
14:31 nervus: 正在确认操作...

┌─ ⚠ 需要确认 ───────────────────────────────────────────┐
│  操作: 写入「提醒」卡片                                   │
│  内容: "开会"                                             │
│  时间: 2026-05-08 15:00 (明天)                           │
│  重复: 不重复                                             │
│                                                           │
│  [Tab: 确认]  [Esc: 取消]  [F3: 改路由]                  │
└──────────────────────────────────────────────────────────┘
──────────────────────────────────────────────────────────────
  输入消息...                                           [V]
  V 语音  S 状态  A 应用  L 日志  ? 帮助  Q 退出
```

### 4.3 白名单机制

为避免每个写操作都要确认，引入风险等级：

| 等级 | 定义 | 行为 |
|------|------|------|
| **高风险** | 删除数据、修改已有日程、涉及多张卡片 | **必须确认** |
| **中风险** | 新增提醒、添加待办、修改笔记内容 | 默认确认，TUI 内支持配置跳过 |
| **低风险** | 标记 todo 完成、闹钟 snooze | 可跳过确认直接写入 |

用户可在配置中按 Widget 自定义确认行为。

---

## 五、仪表盘（Dashboard）

### 5.1 TUI 仪表盘模式

在聊天界面按 F2 切换到仪表盘模式，按数据类别组织卡片：

```
┌──────────────────────────────────────────────────────────┐
│  Nervus 仪表盘        ● 在线      2026-05-07 周四       │
├──────────────────────────────────────────────────────────┤
│ ┌─ 待办 (3) ──────┐ ┌─ 今日日程 ────────────────────┐  │
│ │ ☐ 买牛奶        │ │ 10:00 项目周会    📍 3F 会议A  │  │
│ │ ☐ 交电费   🔴   │ │ 12:00 午饭       📍 楼下餐厅  │  │
│ │ ☑ 发邮件        │ │ 15:00 牙医       📍 门诊      │  │
│ │ [+] 新增        │ │ [+] 新增                      │  │
│ └─────────────────┘ └───────────────────────────────┘  │
│ ┌─ 闹钟 ──────────┐ ┌─ 最近笔记 ────────────────────┐  │
│ │ ⏰ 07:00 起床 ✓  │ │ 昨天: AI 框架设计思路        │  │
│ │ ⏰ 12:00 午休 ✓  │ │ 前天: 周会纪要 - 项目排期    │  │
│ │ ⏰ 22:00 睡觉    │ │ 上周: Docker 部署踩坑记录    │  │
│ │ [+] 新增        │ │ [查看全部 →]                  │  │
│ └─────────────────┘ └───────────────────────────────┘  │
│                                                         │
│  F1 聊天  F2 仪表盘  F3 系统状态  F4 代谢健康  Q 退出  │
└──────────────────────────────────────────────────────────┘
```

### 5.2 Web 仪表盘（可选）

TUI 仪表盘之外，提供 Web 图形界面：

- **端口**: `:8091`（副端口，Arbor Core 多监听一个端口）
- **技术**: 纯 HTML + CSS + JS，内嵌在 Arbor Core 进程里（不需要额外服务器）
- **定位**: 可选插件，不是核心。TUI 仪表盘 + Web 仪表盘功能一致，互不依赖
- **交互**: 卡片支持点击操作（勾选 todo、点击闹钟修改时间、滚轮查看日程）

---

## 六、与当前代码的兼容策略

### 6.1 迁移路径

```
阶段 1（当前状态）：
  Docker Compose + Postgres + Redis + NATS + 16 App 容器
      ↓
阶段 2（并行运行）：
  保留 Docker 基础架构 + 新增 Widget 模块（新功能走 Widget）
      ↓
阶段 3（逐步迁移）：
  逐个将现有 App 的逻辑搬运到 Widget 中，保持 API 兼容
      ↓
阶段 4（完成）：
  去掉 Docker、Postgres、Redis、NATS，纯单进程运行
```

### 6.2 每个阶段的详细内容

**阶段 2**（最低改动，快速验证）：

- 在 `core/arbor/` 下新增 `widgets/` 子包
- Widget 共享 Arbor Core 的 SQLite 连接（不依赖 Postgres 表）
- 路由引擎优先匹配 Widget，未匹配则走老路
- nervus-cli 新增仪表盘模式（从新端口 `:8091` 拉数据或直接调用 Widget API）
- 确认面板功能上线

**阶段 3**（逐步搬运，无侵入）：

- 第一次先搬运 `reminder`（当前已有 SQLite 代码，最简单）
- 第二次搬运 `calendar`
- 依次类推...
- 每个 App 搬完后，老的 Docker 容器可以停止但保留
- 数据通过迁移脚本从 Postgres 导入 SQLite

**阶段 4**（可选）：

- 当老 App 全部搬运完毕，删除 Docker Compose
- 删除 Postgres、Redis、NATS 依赖
- `run.py` 可作为唯一启动入口

---

## 七、首批卡片优先级

| 优先级 | 卡片 | 理由 | 当前已有？ |
|--------|------|------|-----------|
| P0 | **提醒** (Reminder) | 已有完整 SQLite 代码，搬运最快 | ✅ `apps/reminder/main.py` |
| P0 | **待办** (Todo) | 最常见的状态管理需求 | ❌ 当前未有，需新建 |
| P1 | **日程** (Calendar) | 日程查看点选很直观 | ✅ `apps/calendar/main.py` |
| P1 | **笔记** (Notes) | 快速记录+回顾 | ✅ `apps/personal-notes/main.py` |
| P2 | **闹钟** (Alarm) | 起床/提醒 | ❌ 当前由 reminder 兼任 |
| P2 | **知识库** (Knowledge) | 搜索已有记录 | ✅ `apps/knowledge-base/main.py` |

---

## 八、依赖变更

### 新增依赖

```txt
# core/arbor/requirements.txt（追加）
aiosqlite          # SQLite 异步驱动
```

### 可移除依赖（阶段 4）

```txt
# nats-py[nkeys]  → 移除（用 asyncio event bus 替代）
# redis[hiredis]  → 移除（用 dict + aiosqlite 替代）
# asyncpg         → 移除（用 aiosqlite 替代）
```

---

## 九、未解决的问题/待讨论

1. **Flow 执行器里的 context_set / notify / emit 步骤** — 当前依赖 Redis 和 NATS，迁移后如何适配？改为直接调用 Widget 方法还是保留 asyncio bus？
2. **向量搜索**（pgvector）— 迁移到 sqlite-vec 是否成熟？还是继续保留 Postgres 做知识库搜索？
3. **TUI 仪表盘的 WebView** — Textual 的 WebView widget 是否足以渲染 HTML 卡片？如果不行，副端口 Web 页面 + TUI 的 browser_模式？
4. **代谢系统的调度** — 本来依赖 NATS 定时消息（`system.metabolism.trigger.*`），迁移后改为 asyncio 定时任务
5. **多用户** — 单用户设备不需要，但 SQLite 文件路径是否要支持 `DATA_DIR` 环境变量？

---

## 十、附录：当前架构 vs 目标架构对比

| 维度 | 当前 | 目标 |
|------|------|------|
| **进程数** | 20+ (1 Arbor + 3 中间件 + 16 App) | 1 (Arbor Core 单进程) |
| **启动命令** | `docker compose up -d` | `python run.py` |
| **启动时间** | 30s-2min (镜像构建+容器启动) | < 1s |
| **内存占用** | ~1.3GB | ~200-300MB |
| **H618 可用性** | 勉强 (4GB 剩 2.7GB) | 宽松 (剩 3.7GB) |
| **数据隔离方式** | 进程隔离 + Docker 网络 | SQLite 文件隔离 |
| **交互模式** | 纯 TUI 聊天 | 聊天 + 图形化仪表盘双模式 |
| **写操作安全** | 无确认机制 | 意图确认面板兜底 |
| **可扩展性** | 添加 Docker 容器 | 添加 Python 模块 |
| **远程访问** | SSH + TUI | SSH + TUI + Web 仪表盘（可选） |
