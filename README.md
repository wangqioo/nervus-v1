# Nervus

> **Agent OS for Embedded Linux**
> 运行在口袋设备上的个人 Agent 操作系统。云端推理，本地路由，终端交互，零前端依赖。

---

## 设计理念

Nervus 不是一个 AI 聊天 App，而是一个 **Agent 运行时**：

```
用户意图（文字 / 语音）
        ↓
  Arbor Core 路由引擎
  Fast → Semantic → Dynamic
        ↓
  对应 App 自主执行任务
        ↓
  结果回显到终端
```

**为什么是终端？** Claude Code、Aider 等真正有生产力的 AI 工具都活在终端里。GUI 是给"不知道自己要什么"的用户做的引导层——Agent 不需要它。前端是后期可选插件，不是核心。

**为什么不跑本地模型？** 2025 年没有成熟又便宜的边缘 AI 推理芯片。LLM 推理是内存带宽瓶颈，H618 这类芯片的 NPU 是为视觉模型设计的，跑 0.5B 以上模型意义不大。推理全部上云。

---

## 目标硬件

| 项目 | 规格 |
|------|------|
| 芯片 | Allwinner H618（4× Cortex-A53，28nm） |
| 内存 | 4GB LPDDR4 |
| 系统 | Linux（Debian/Ubuntu ARM） |
| 屏幕 | 3.5 寸，480×320，横屏 |
| 语音 | 讯飞云端 ASR（实时 WebSocket） |
| 推理 | 云端 LLM（DeepSeek / OpenAI / Anthropic） |
| 交互 | nervus-cli（Textual TUI） |

**内存占用（精简配置）**：

```
Arbor Core          ~200MB
PostgreSQL+pgvector ~300MB
Redis + NATS        ~110MB
核心 App 容器        ~400MB
系统底层             ~300MB
──────────────────────────
合计                 ~1.3GB   （4GB 中剩约 2.7GB）
```

> 任何支持 Docker 的 Linux 机器（x86 / ARM）均可运行，不依赖特定硬件。

---

## 快速开始

```bash
git clone https://github.com/wangqioo/nervus-v1.git nervus
cd nervus
cp .env.example .env          # 填入云端 API Key
docker compose up -d
```

启动后运行 nervus-cli：

```bash
cd nervus-cli
cp .env.example .env          # 填入讯飞 ASR Key 和 ARBOR_URL
pip install -r requirements.txt
python app.py
```

---

## nervus-cli 界面

```
Nervus  ●  14:30
──────────────────────────────────────────────────────────────
  ∷ Nervus 已启动。输入消息或按 Ctrl+V 语音输入。
14:31 你: 帮我设置明天10点的会议提醒
14:31 reminder: 已创建提醒：明天 10:00 会议
14:32 你: 查一下今天有什么日程
14:32 calendar: 今天暂无日程
──────────────────────────────────────────────────────────────
  输入消息...                                           [V]
  V 语音  S 状态  A 应用  L 日志  ? 帮助  Q 退出
```

| 快捷键 | 功能 |
|--------|------|
| Ctrl+V / F1 | 语音输入（讯飞实时 ASR） |
| Ctrl+S / F2 | 系统状态 |
| Ctrl+A / F3 | 应用列表 |
| Ctrl+L / F4 | 执行日志 |
| Ctrl+Q | 退出 |

---

## 架构

```
nervus/
├── nervus-cli/              # 终端交互层（Textual TUI）
│   ├── app.py               # 主界面，适配 3.5" 480×320 横屏
│   ├── client.py            # Arbor Core HTTP + NATS 客户端
│   ├── voice.py             # 讯飞实时 ASR（WebSocket）
│   └── config.py            # 环境变量配置
│
├── core/
│   ├── arbor/               # 平台基座（:8090）
│   │   ├── router/          # 三级路由引擎
│   │   │   ├── fast_router.py      # Flow 模式匹配，< 100ms
│   │   │   ├── semantic_router.py  # LLM 语义推理，< 2s
│   │   │   └── dynamic_router.py  # 多事件关联规划，< 5s
│   │   ├── nervus_platform/ # Apps / Models / Events / Knowledge
│   │   └── executor/        # Flow 执行器 + Embedding Pipeline
│   ├── nats/                # 消息总线（:4222）
│   ├── postgres/            # PostgreSQL + pgvector（:5432）
│   └── redis/               # 上下文缓存（:6379）
│
├── apps/                    # 各功能 App（独立 Docker 服务，共 16 个）
│   ├── reminder/            :8012
│   ├── calendar/            :8011
│   ├── personal-notes/      :8007
│   ├── knowledge-base/      :8003
│   ├── life-memory/         :8004
│   ├── meeting-notes/       :8002
│   ├── rss-reader/          :8010
│   ├── photo-scanner/       :8006
│   └── ...
│
├── sdk/python/              # Nervus Python SDK
├── config/                  # models.json / flows / public.json
└── docs/
    ├── hardware-and-terminal-design.md  # 硬件选型 + 终端架构设计思路
    ├── porting-guide.md                 # 新 App 接入手册
    └── Nervus_完整开发文档.md
```

---

## 职责划分

| 层 | 负责方 | 说明 |
|----|--------|------|
| 语音识别 | 讯飞云 ASR | 中文实时识别，WebSocket 流式 |
| LLM 推理 | 云端（DeepSeek / OpenAI） | 在 config/models.json 配置 |
| 意图路由 | 本地 Arbor Core | 三级路由，不依赖网络 |
| 数据存储 | 本地 PostgreSQL + Redis | 隐私数据不出设备 |
| 交互界面 | nervus-cli | 终端 TUI，~50MB 内存 |

---

## 云端模型配置

在 `.env` 中填写：

```bash
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

模型列表在 `config/models.json` 中配置，支持热更新。

---

## 平台 API

Arbor Core 直接暴露在 `:8090`：

| 接口 | 说明 |
|------|------|
| `GET /health` | 健康检查 |
| `GET /status` | 全局状态（App 数、Flow 数） |
| `GET /apps` | 已注册 App 列表 |
| `POST /models/chat` | Chat 统一网关 |
| `GET /events/recent` | 最近事件 |
| `POST /platform/knowledge` | 写入知识库 |
| `POST /platform/knowledge/search` | 语义搜索 |
| `GET /flows` | 已加载 Flow 列表 |
| `POST /flows/reload` | 热更新 Flow |
| `GET /logs` | 执行日志 |
| `GET /notifications` | 通知列表 |

---

## 开发新 App

参考 `docs/porting-guide.md`，使用 `sdk/python/` 中的 SDK，每个 App 是独立的 Docker 服务，通过 NATS 消息总线与 Arbor Core 通信。

---

## 路线图

| 阶段 | 目标 |
|------|------|
| 当前 | nervus-cli TUI + 云端推理，在任意 Linux 机器上验证体验 |
| 近期 | 在 H618 设备上跑精简版，物理按键接入语音 |
| 中期 | 设备封装，GPIO 接入，定制外壳 |
| 远期 | Web UI 作为可选插件叠加在 TUI 之上 |
