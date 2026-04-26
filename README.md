# Nervus

> 一个运行在本地 AI 主机上的个人操作系统，以五方向空间导航为交互核心，通过 iOS 原生壳子安装到手机上。

```
          ↑ 上滑
          感知面板
← 左滑    ← 主页 →    右滑 →
  Chat          Files
          ↓ 下滑
          应用中心
```

- **主页** — AI 摘要卡片 + 快捷入口
- **感知面板**（上划）— 健康 / 系统状态
- **Chat**（左划）— 接本地 LLM 对话（走 Model Platform 代理）
- **Files**（右划）— 文件传输助手
- **应用中心**（下划）— 从 `/api/apps` 动态读取已注册 App

---

## 当前版本：v0.1 Platform

| 功能 | 状态 |
|------|------|
| 五方向空间导航 SPA | ✅ |
| iOS Capacitor 壳子 | ✅ |
| Files 文件传输面板 | ✅ |
| 深色 / 浅色自动跟随系统 | ✅ |
| 全屏 + 安全区适配 | ✅ |
| **Arbor Core Platform（基座）** | ✅ |
| App Platform（注册/发现/心跳） | ✅ |
| Model Platform（Chat 网关） | ✅ |
| Event Platform（事件持久化/查询） | ✅ |
| Knowledge Platform（写入/检索） | ✅ |
| 三级路由引擎（Fast/Semantic/Dynamic） | ✅ |
| Flow 配置驱动的跨 App 自动化 | ✅ |
| Embedding Pipeline（异步向量化） | ✅ |
| App 心跳 / 离线检测 | ✅ |
| Chat 面板接 LLM | ✅ |
| 应用中心动态读取 /api/apps | ✅ |
| 各 App 前端面板联通 | 🔧 进行中 |

---

## 目录

1. [硬件要求](#1-硬件要求)
2. [服务端部署](#2-服务端部署linux-主机)
3. [网络穿透](#3-网络穿透外网访问)
4. [iOS 壳子安装](#4-ios-壳子安装)
5. [日常更新前端](#5-日常更新前端)
6. [平台 API 速查](#6-平台-api-速查)
7. [项目结构](#7-项目结构)

---

## 1. 硬件要求

| 角色 | 推荐配置 | 说明 |
|------|---------|------|
| AI 主机 | NVIDIA Jetson Orin Nano 8GB | 运行 LLM + 所有后端服务 |
| 手机 | iPhone（iOS 16+） | 安装 Nervus 壳子 |
| 开发电脑 | Mac（macOS 13+，Xcode 15+） | 编译 iOS 壳子 |

> 没有 Jetson 也可以用任意 Linux 机器（x86 / ARM），只要有 Docker 和足够内存跑 LLM 即可。

---

## 2. 服务端部署（Linux 主机）

### 前置条件

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

### 拉取代码并启动

```bash
git clone https://github.com/wangqioo/nervus-v1.git nervus
cd nervus
docker compose up -d
```

启动后各服务端口：

| 服务 | 端口 | 说明 |
|------|------|------|
| Caddy（HTTPS） | 443 | 主入口，自签名证书 |
| Caddy（HTTP） | 8900 | 局域网备用 |
| Arbor Core | 8090 | 平台基座（内部） |
| llama.cpp | 8080 | 本地 LLM（内部） |

访问 `https://<主机IP>` 即可在局域网内打开 Nervus 前端。

---

## 3. 网络穿透（外网访问）

推荐工具：**frp**（免费，自建）或 **cpolar / ngrok**（托管）。

在有公网 IP 的服务器上运行 frps，在主机上运行 frpc，将本地 443 端口映射到公网某端口。配置完成后将公网地址填入 `ios/capacitor.config.json` 的 `server.url`。

---

## 4. iOS 壳子安装

**① 修改服务器地址**

```json
// ios/capacitor.config.json
{
  "server": {
    "url": "https://<你的主机IP或域名>",
    "cleartext": true
  }
}
```

**② 安装依赖并同步**

```bash
cd ios
npm install
npx cap sync ios
open ios/App/App.xcodeproj
```

**③ 用 Xcode 编译安装**

在 Xcode 里：Signing & Capabilities → 选 Apple ID → Bundle Identifier 改成你自己的 → ▶ Run

**④ 信任证书**

设置 → 通用 → VPN 与设备管理 → 找到你的 Apple ID → 信任

> 免费 Apple ID 签名有效期 7 天，到期后重新 Run 一次。

---

## 5. 日常更新前端

前端是单文件 `frontend/index.html`，修改后直接 scp，**无需重启 Docker**。

```bash
scp frontend/index.html <用户名>@<主机IP>:/home/<用户名>/nervus/frontend/index.html
```

更新 Flow 配置同理，scp 后调用热更新接口：

```bash
curl -X POST http://<主机IP>:8900/api/flows/reload
```

---

## 6. 平台 API 速查

所有接口经 Caddy `/api/*` → Arbor Core（`:8090`）。

| 接口 | 说明 |
|------|------|
| `GET /api/health` | 基础健康检查 |
| `GET /api/status` | 全局状态（App 数、Flow 数、embedding 统计） |
| `GET /api/apps` | 已注册 App 列表 |
| `POST /api/apps/register` | App 注册（SDK 自动调用） |
| `POST /api/apps/{id}/heartbeat` | 心跳上报（SDK 自动调用） |
| `GET /api/models` | 模型列表 |
| `GET /api/models/status` | 模型在线状态 |
| `POST /api/models/chat` | Chat 统一网关 |
| `GET /api/events/recent` | 最近事件（`?limit=50&subject=meeting`） |
| `POST /api/platform/knowledge` | 写入知识库 |
| `POST /api/platform/knowledge/search` | 搜索知识库 |
| `GET /api/flows` | 已加载 Flow 列表 |
| `POST /api/flows/reload` | 热更新 Flow 配置 |
| `GET /api/logs` | Flow 执行日志 |
| `GET /api/config/public` | 前端公共配置 |

---

## 7. 项目结构

```
nervus/
├── frontend/
│   └── index.html              # 全屏 SPA，五方向导航，单文件
│
├── ios/                        # iOS Capacitor 壳子
│   ├── capacitor.config.json   # ← 部署时改这里：填服务器地址
│   └── ios/App/                # Xcode 工程
│
├── apps/                       # 各功能 App，每个是独立 Docker 服务
│   ├── file-manager/           # 文件传输（:8015，前端已联通）
│   ├── meeting-notes/          # 会议纪要（:8002）
│   ├── calorie-tracker/        # 热量管理（:8001）
│   ├── photo-scanner/          # 相册扫描（:8006）
│   ├── personal-notes/         # 个人笔记（:8007）
│   ├── knowledge-base/         # 知识库（:8003）
│   ├── pdf-extractor/          # PDF 提取（:8008）
│   ├── video-transcriber/      # 视频转录（:8009）
│   ├── rss-reader/             # RSS 订阅（:8010）
│   ├── reminder/               # 提醒（:8012）
│   ├── calendar/               # 日历（:8011）
│   ├── life-memory/            # 生活记忆（:8004）
│   ├── status-sense/           # 系统状态（:8013）
│   ├── sense/                  # 感知数据（:8005）
│   └── workflow-viewer/        # 工作流可视化（:8014）
│
├── core/                       # 基础设施
│   ├── arbor/                  # 平台基座（:8090）
│   │   ├── main.py             # 启动入口，所有模块在此初始化
│   │   ├── platform/           # Platform 层
│   │   │   ├── apps/           # App 注册/发现/心跳
│   │   │   ├── models/         # Chat 网关
│   │   │   ├── events/         # 事件持久化/查询
│   │   │   ├── knowledge/      # 知识写入/检索
│   │   │   └── config/         # 公共配置
│   │   ├── router/             # 三级路由引擎
│   │   │   ├── fast_router.py  # Flow 模式匹配，< 100ms
│   │   │   ├── semantic_router.py  # LLM 语义推理，< 2s
│   │   │   └── dynamic_router.py  # 多事件关联规划，< 5s
│   │   ├── executor/           # Flow 执行器 + Embedding Pipeline
│   │   └── infra/              # NATS / Redis / Postgres / Settings 客户端
│   ├── caddy/                  # 反向代理，统一入口（:443/:8900）
│   ├── nats/                   # 消息总线（:4222）
│   ├── postgres/               # PostgreSQL + pgvector（:5432）
│   ├── redis/                  # 上下文缓存（:6379）
│   └── whisper/                # 本地语音识别（:8081）
│
├── sdk/
│   └── python/                 # Nervus Python SDK，所有 App 基于此构建
│
├── config/
│   ├── public.json             # 前端公共配置（外部演示链接等）
│   └── flows/                  # Flow 配置文件（热更新，无需重启）
│       ├── media-flows.json    # 相片→热量/生活记忆
│       ├── meeting-flows.json  # 录音→纪要→知识库
│       └── health-flows.json   # 热量→上下文/提醒→弹窗
│
├── docker-compose.yml          # 一键启动全部服务
└── docs/
    ├── porting-guide.md        # 新 App 接入手册
    ├── platform-v0.1-plan.md   # 平台 v0.1 规划（已完成）
    ├── audit-v1.2.md           # v1.2 代码审查报告
    └── Nervus_完整开发文档.md  # 完整架构设计文档
```

---

## 内存参考（Jetson Orin Nano 8GB）

| 组件 | 占用 |
|------|------|
| 系统底层 | ~1.5 GB |
| LLM（Qwen 4B INT4） | ~2.8 GB |
| Redis + PostgreSQL + NATS | ~550 MB |
| Caddy + Arbor + 各 App 服务 | ~1.5 GB |
| **合计** | **~6.4 GB** |
