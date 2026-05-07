# Nervus

> **Agent OS — 放在口袋里的个人 Agent 运行时。**
> 云端推理，本地路由，终端交互，单进程启动，用得越久越懂你。

---

## 一句话

Nervus 不是一个 AI 聊天 App。它是一套 **Agent 运行时**：用户通过终端（或未来其他交互层）输入自然语言意图，三级路由引擎自动分发给对应的功能模块执行，结果回显给用户。所有数据存储于本地 SQLite，零基础设施依赖。

---

## 快速开始

```bash
git clone https://github.com/wangqioo/nervus-v1.git
cd nervus-v1/core/arbor

# 配置模型 API Key
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 安装依赖
pip install -r requirements.txt

# 启动！（单进程，无需 Docker）
python main.py
```

启动后访问 http://localhost:8090/health 确认服务正常。

**启动 nervus-cli（可选，终端交互界面）：**

```bash
cd nervus-v1/nervus-cli
pip install -r requirements.txt
python app.py
```

---

## 设计理念

### 1. 三级路由引擎

所有用户意图经过三级路由，自动分发给对应模块执行：

```
用户意图（文字 / 语音）
        ↓
  Fast Router      — Flow 模式匹配，< 100ms
        ↓（未命中）
  Semantic Router  — LLM 语义推理，< 2s
        ↓（复杂意图）
  Dynamic Router   — 多事件关联规划，< 5s
        ↓
  对应模块自主执行
        ↓
  结果回显到终端
```

### 2. 终端优先（Terminal-First）

Claude Code、Aider 等真正有生产力的 AI 工具都活在终端里。GUI 是给"不知道自己要什么"的用户做的引导层——Agent 不需要它。

| 维度 | Web UI | TUI（nervus-cli） |
|------|--------|-----------------|
| 内存占用 | ~400-600MB（Chromium） | ~50MB |
| 启动速度 | 慢 | 极快 |
| SSH 远程访问 | 需额外配置 | 原生支持 |
| 硬件适配 | 需要浏览器引擎 | 任何终端均可 |

### 3. 代谢系统（Metabolism）

系统用的越久，熵增越大。Nervus 内置主动熵减机制：

```
数据 → 积累 → 巩固 → 衰减 → 遗忘
              ↑                ↓
              └─ 高价值信息强化 ─┘
```

- **记忆巩固**：每日将短期对话提炼为长期知识
- **遗忘曲线**：知识节点携带 `relevance_score`，不访问的自动衰减
- **Flow 垃圾回收**：检测休眠和冲突的路由规则
- **系统自审**：每周 LLM 分析系统状态，生成健康报告

详见 [`docs/metabolism-design.md`](docs/metabolism-design.md)。

---

## 架构

```
nervus-v1/
├── core/arbor/              # 🎯 核心：单进程 Arbor Core（:8090）
│   ├── main.py              # 入口 — python main.py 即启动
│   ├── router/              # 三级路由引擎
│   │   ├── fast_router.py   # Flow 模式匹配，< 100ms
│   │   ├── semantic_router.py # LLM 语义推理，< 2s
│   │   └── dynamic_router.py  # 多事件关联规划，< 5s
│   ├── executor/            # Flow 执行器 + Embedding Pipeline
│   ├── nervus_platform/     # Models / Events / Knowledge / Config
│   ├── widgets/             # 卡片 Widget（reminders, calendar, notes, alarms）
│   ├── api/                 # HTTP API（status, notify）
│   ├── infra/               # 🆕 基础设施层
│   │   ├── db.py            # SQLite 核心存储引擎
│   │   ├── nats_client.py   # 进程内 EventBus（替代 NATS）
│   │   ├── redis_client.py  # SQLite 键值存储（替代 Redis）
│   │   └── postgres_client.py # SQLite 包装器（替代 PostgreSQL）
│   └── requirements.txt     # 仅 6 个依赖
│
├── config/
│   ├── models.json          # 模型配置
│   └── flows/               # Flow 路由规则
│
├── nervus-cli/              # 终端交互层（Textual TUI，可选）
│
├── sdk/
│   ├── python/              # Python SDK
│   └── typescript/          # TypeScript SDK
│
├── docs/                    # 设计文档
└── tests/                   # 测试
```

### 基础设施层（infra/）

原架构依赖 PostgreSQL + Redis + NATS 三个外部服务（需要 Docker 编排启动）。重构后全部替换为进程内 SQLite：

| 原组件 | 替换方案 |
|--------|---------|
| **NATS**（消息总线） | `EventBus` — 进程内 pub/sub，零网络 IO |
| **Redis**（键值缓存） | SQLite `kv` 命名空间，`kv_get/kv_set` |
| **PostgreSQL**（关系库） | SQLite `events` / `knowledge` / `apps` 命名空间 |
| 外部 Docker 编排 | ❌ 已删除，`python main.py` 一键启动 |

数据文件存放于 `core/arbor/data/`：
- `nervus.db` — 主数据库（事件、知识、应用注册、键值存储）
- `widgets/*.db` — 各 Widget 独立数据库

### 内存占用（精简配置）

```
Arbor Core          ~80MB   （纯 Python，无外部进程）
内部 SQLite        包含在 Arbor Core 内
──────────────────────────
合计                ~80MB    （不再需要 1.3GB）
```

---

## 模块说明

### Widget 卡片系统

Widget 是 Nervus 的功能单元，每个 Widget 拥有独立的 SQLite 数据库和 FastAPI 路由挂载：

| Widget | 文件 | 说明 |
|--------|------|------|
| 🔔 提醒 | `widgets/reminders.py` | 基于 intent 的提醒管理 |
| 📅 日历 | `widgets/calendar.py` | 日历事件管理 |
| 📝 备忘录 | `widgets/notes.py` | 自由文本笔记 |
| ⏰ 闹钟 | `widgets/alarms.py` | 定时闹钟 |

AI Agent 通过 `/api/widgets/dispatch` 直接读写 Widget 数据（无确认面板模式）。

---

## 模型配置

### 云端模型

创建 `.env` 文件（参考 `.env.example`）：

```bash
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

在 `config/models.json` 中配置模型列表，支持热更新：

```bash
curl -X POST http://localhost:8090/flows/reload
```

### 本地模型（可选）

支持通过 llama.cpp 运行本地模型，设置 `"provider": "llama.cpp"` 并配置 `LLM_URL` 指向本地推理端点。

---

## API 概览

Arbor Core 暴露在 `:8090`：

| 接口 | 说明 |
|------|------|
| `GET /health` | 健康检查 |
| `GET /status` | 全局状态（App 数、Flow 数） |
| `GET /apps` | 已注册模块列表 |
| `POST /models/chat` | Chat 统一网关 |
| `GET /events/recent` | 最近事件 |
| `POST /platform/knowledge` | 写入知识库 |
| `POST /platform/knowledge/search` | 语义搜索 |
| `GET /flows` | 已加载 Flow 列表 |
| `POST /flows/reload` | 热更新 Flow |
| `GET /api/widgets` | Widget 列表 |
| `POST /api/widgets/dispatch` | Widget 操作分发（read/write/execute） |

---

## 开发

```bash
# 启动
cd core/arbor && python main.py

# 测试
cd tests && bash run_tests.sh

# 测试 API
make test-api

# 热更新 Flow 配置
make reload-flows
```

开发新 Widget 参考 `widgets/base.py`，实现 `get/set/delete` 接口后注册到 `widgets/__init__.py` 的 `WidgetRegistry` 即可。

---

## 路线图

| 阶段 | 目标 |
|------|------|
| 当前 | 单进程 Arbor Core + nervus-cli TUI，零外部依赖 |
| 近期 | 实现 metabolism 代谢模块（consolidation + decay） |
| 中期 | 物理设备封装（H618），语音输入，GPIO 按键 |
| 远期 | 定制外壳，Web UI 作为可选插件 |

---

## 核心结论

> **不要做「更好的语音助手」，要做「放在口袋里的、能自主完成任务且越用越懂你的 Agent 终端」。**

Nervus 的真正壁垒：
- **Arbor Core 的路由引擎** — 意图理解的准确性
- **持久上下文记忆** — 跨会话的连续性
- **代谢系统** — 随时间增长的系统品质
- **单进程零依赖** — 任何 Linux 机器，`pip install && python main.py` 即运行
