# Nervus

> **Agent OS for Embedded Linux**
> 运行在口袋设备上的个人 Agent 操作系统。云端推理，本地路由，终端交互，用得越久越懂你。

---

## 设计理念

Nervus 不是一个 AI 聊天 App，而是一个 **Agent 运行时**。它有三根支柱：

### 1. 路由引擎（Arbor Core）

所有用户意图经过三级路由，自动分发给对应 App 执行：

```
用户意图（文字 / 语音）
        ↓
  Fast Router      — Flow 模式匹配，< 100ms
        ↓（未命中）
  Semantic Router  — LLM 语义推理，< 2s
        ↓（复杂意图）
  Dynamic Router   — 多事件关联规划，< 5s
        ↓
  对应 App 自主执行任务
        ↓
  结果回显到终端
```

### 2. 终端优先（Terminal-First）

Claude Code、Aider 等真正有生产力的 AI 工具都活在终端里。GUI 是给"不知道自己要什么"的用户做的引导层——Agent 不需要它。

| 维度 | Web UI | TUI（nervus-cli） |
|------|--------|-----------------|
| H618 内存占用 | ~400-600MB（Chromium） | ~50MB |
| 启动速度 | 慢 | 极快 |
| SSH 远程访问 | 需额外配置 | 原生支持 |
| 硬件适配 | 需要浏览器引擎 | 任何终端均可 |

前端是后期可选插件，不是核心。

### 3. 代谢系统（Metabolism）

**这是 Nervus 与其他 Agent 框架最本质的区别。**

一个真正自主运行的 Agent OS，随着使用时间增长，系统熵增是必然的——知识库堆满过时信息、路由规则相互冲突、旧对话污染新上下文。

Nervus 内置主动熵减机制，让系统用得越久越干净、越懂你：

```
数据 → 积累 → 巩固 → 衰减 → 遗忘
              ↑                ↓
              └─ 高价值信息强化 ─┘
```

- **记忆巩固**：每日凌晨将短期对话提炼为长期知识，清除矛盾和重复条目
- **遗忘曲线**：所有知识节点携带 `relevance_score`，长期不访问的自动衰减归档
- **Flow 垃圾回收**：检测休眠和冲突的路由规则，定期清理
- **系统自审**：每周 LLM 分析系统状态，生成"健康报告"推送给用户

详见 [`docs/metabolism-design.md`](docs/metabolism-design.md)。

---

## 为什么不跑本地模型

LLM 推理是内存带宽瓶颈，不是算力瓶颈：

| 芯片 | 内存带宽 | 可用模型上限 |
|------|---------|------------|
| H618（目标硬件） | ~15 GB/s | 0.5B 勉强 |
| 骁龙 8 Elite | ~120 GB/s | 13B 可用 |
| Apple M 系列 | 100~400 GB/s | 30B+ |

H618 的 NPU 是为视觉 CNN 模型设计的，Transformer 算子支持不完整。跑 0.5B 以上模型没有意义。

**结论**：推理全部上云（DeepSeek / OpenAI / Anthropic），本地只做路由、存储、隐私边界。

---

## 目标硬件

| 项目 | 规格 |
|------|------|
| 芯片 | Allwinner H618（4× Cortex-A53，28nm） |
| 内存 | 4GB LPDDR4 |
| 系统 | Linux（Debian/Ubuntu ARM） |
| 屏幕 | 3.5 寸，480×320，横屏 |
| 语音 | 讯飞云端 ASR（实时 WebSocket） |
| LLM  | 云端（DeepSeek / OpenAI / Anthropic） |
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

**启动后端**：

```bash
git clone https://github.com/wangqioo/nervus-v1.git nervus
cd nervus
cp .env.example .env          # 填入云端 API Key
docker compose up -d
```

**启动 nervus-cli**：

```bash
cd nervus-cli
cp .env.example .env          # 填入讯飞 ASR Key 和 ARBOR_URL
pip install -r requirements.txt
python app.py
```

---

## nervus-cli 界面

适配 3.5 寸 480×320 横屏（约 60列 × 20行）：

```
Nervus  ●  14:30
──────────────────────────────────────────────────────────────
  ∷ Nervus 已启动。输入消息或按 Ctrl+V 语音输入。
14:31 你: 帮我设置明天10点的会议提醒
14:31 reminder: 已创建提醒：明天 10:00 会议
14:32 你: 今天的知识库里有什么关于健康的记录
14:32 knowledge-base: 找到 3 条相关记录...
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
| Ctrl+M / F5 | 系统健康（代谢状态） |
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
│   │   │   └── dynamic_router.py   # 多事件关联规划，< 5s
│   │   ├── metabolism/      # 代谢系统（熵减）
│   │   │   ├── scheduler.py        # 代谢任务调度器
│   │   │   ├── consolidation.py    # 记忆巩固
│   │   │   ├── decay.py            # 遗忘曲线
│   │   │   ├── gc.py               # Flow 垃圾回收
│   │   │   └── reflection.py       # 系统自审
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
│   └── ...（共 16 个）
│
├── sdk/python/              # Nervus Python SDK
├── config/                  # models.json / flows
└── docs/
    ├── metabolism-design.md         # 代谢系统设计（核心）
    ├── hardware-and-terminal-design.md  # 硬件选型 + 终端架构
    └── porting-guide.md             # 新 App 接入手册
```

---

## 职责划分

| 层 | 负责方 | 说明 |
|----|--------|------|
| 语音识别 | 讯飞云 ASR | 中文实时识别，WebSocket 流式 |
| LLM 推理 | 云端（DeepSeek / OpenAI / Anthropic） | 在 `config/models.json` 配置 |
| 意图路由 | 本地 Arbor Core | 三级路由，不依赖网络可降级 |
| 数据存储 | 本地 PostgreSQL + Redis | 隐私数据不出设备 |
| 系统代谢 | 本地 metabolism 模块 | 自主熵减，无需用户干预 |
| 交互界面 | nervus-cli | 终端 TUI，~50MB 内存 |

---

## 云端模型配置

在 `.env` 中填写对应的 API Key：

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

参考 `docs/porting-guide.md`，使用 `sdk/python/` 中的 SDK。每个 App 是独立的 Docker 服务，通过 NATS 消息总线与 Arbor Core 通信，注册 Intent Handler 即可接入路由引擎。

---

## 路线图

| 阶段 | 目标 |
|------|------|
| 当前 | nervus-cli TUI + 云端推理，在任意 Linux 机器上验证体验 |
| 近期 | 实现 metabolism 代谢模块（consolidation + decay），在 H618 设备上跑精简版 |
| 中期 | 物理按键 GPIO 接入，语音唤醒，设备封装 |
| 远期 | 定制外壳，Web UI 作为可选插件叠加在 TUI 之上 |

---

## 核心结论

> **不要做「更好的语音助手」，要做「放在口袋里的、能自主完成任务且越用越懂你的 Agent 终端」。**

Nervus 的真正壁垒是三位一体：
- **Arbor Core 的路由引擎** — 意图理解的准确性
- **持久上下文记忆** — 跨会话的连续性
- **代谢系统** — 随时间增长的系统品质
