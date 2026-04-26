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
- **Chat**（左划）— 接本地 LLM 对话
- **Files**（右划）— 文件传输助手
- **应用中心**（下划）— 可自定义的 App 网格，支持添加 / 删除

---

## 当前版本：v1.2

| 功能 | 状态 |
|------|------|
| 五方向空间导航 SPA | ✅ |
| iOS Capacitor 壳子 | ✅ |
| Files 文件传输面板 | ✅ |
| 应用中心（动态，localStorage） | ✅ |
| 深色 / 浅色自动跟随系统 | ✅ |
| 全屏 + 灵动岛安全区适配 | ✅ |
| 各 App 后端联通 | 🔧 进行中 |

---

## 目录

1. [硬件要求](#1-硬件要求)
2. [服务端部署（Linux 主机）](#2-服务端部署linux-主机)
3. [网络穿透（外网访问）](#3-网络穿透外网访问)
4. [iOS 壳子安装](#4-ios-壳子安装)
5. [日常更新前端](#5-日常更新前端)
6. [项目结构](#6-项目结构)

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
# 安装 Docker + Docker Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # 免 sudo 运行 docker（需重新登录）
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
| Files 后端 | 8015 | 文件传输助手 |

访问 `https://<主机IP>` 即可在局域网内打开 Nervus 前端。

---

## 3. 网络穿透（外网访问）

如果需要在外网用手机访问（不在同一局域网），需要配置穿透隧道，否则跳过此节。

推荐工具：**frp**（免费，自建）或 **cpolar / ngrok**（托管，有免费套餐）。

以 frp 为例，在有公网 IP 的服务器上运行 frps，在 Jetson 上运行 frpc，将本地 443 端口映射到公网某端口即可。

配置完成后将公网地址填入 `ios/capacitor.config.json` 的 `server.url`（见下节）。

---

## 4. iOS 壳子安装

### 前置条件

- Mac 电脑，已安装 **Xcode 15+**
- **Apple ID**（免费即可，无需付费开发者账号）
- 手机通过数据线连接 Mac

### 步骤

**① 修改服务器地址**

打开 `ios/capacitor.config.json`，将 `server.url` 改为你自己的 Nervus 地址：

```json
{
  "appId": "com.yourname.nervus",
  "appName": "Nervus",
  "webDir": "www",
  "server": {
    "url": "https://<你的主机IP或域名>",
    "cleartext": true
  }
}
```

**② 安装依赖**

```bash
cd ios-shell
npm install
npx cap sync ios
```

**③ 用 Xcode 编译安装**

```bash
open ios/App/App.xcodeproj
```

在 Xcode 里：
1. 左侧选中 `App` 项目
2. `Signing & Capabilities` → Team 选你的 Apple ID
3. Bundle Identifier 改成你自己的（如 `com.yourname.nervus`）
4. 顶部设备选你的 iPhone → 点 ▶ Run

**④ 信任开发者证书**

首次安装后，在手机上：
> **设置 → 通用 → VPN 与设备管理 → 找到你的 Apple ID → 信任**

之后每次打开 App 即可正常使用。

> **注意**：免费 Apple ID 签名的 App 有效期 7 天，到期后需重新用 Xcode Run 一次。付费开发者账号有效期 1 年。

---

## 5. 日常更新前端

前端是单文件 `frontend/index.html`，修改后直接 scp 到主机，**无需重启 Docker，无需重新编译 Xcode**。

```bash
# 局域网直连
scp frontend/index.html <用户名>@<主机IP>:/home/<用户名>/nervus/frontend/index.html

# 或通过 SSH 隧道
scp -P <端口> frontend/index.html <用户名>@<公网IP>:/home/<用户名>/nervus/frontend/index.html
```

上传后刷新手机 App（完全关闭再重开）即可看到最新版本。

---

## 6. 项目结构

```
nervus/
├── frontend/                   # 前端（单文件 SPA，直接 scp 更新，无需重新构建）
│   └── index.html              # 五方向空间导航 UI，包含所有面板逻辑
│
├── ios/                        # iOS 原生壳子（Capacitor，负责打包安装到手机）
│   ├── capacitor.config.json   # ← 部署时改这里：填入 Nervus 主机地址
│   └── ios/App/App/
│       ├── MainViewController.swift   # SSL 自签名证书绕过 + 深色/浅色状态栏
│       ├── AppDelegate.swift          # 应用生命周期
│       └── Info.plist                 # 权限声明（麦克风、相册等）
│
├── apps/                       # 各功能后端，每个都是独立 Docker 服务
│   ├── file-manager/           # 文件传输助手，已联通前端（端口 8015）
│   ├── meeting-notes/          # 会议纪要，录音转文字 + AI 摘要（端口 8002）
│   ├── pdf-extractor/          # PDF 解析与内容提取（端口 8008）
│   ├── video-transcriber/      # 视频转文字，调用 Whisper（端口 8009）
│   ├── calorie-tracker/        # 饮食热量记录，图像识别食物（端口 8001）
│   ├── photo-scanner/          # 相册扫描与 AI 分析（端口 8006）
│   ├── reminder/               # 提醒事项管理（端口 8012）
│   ├── personal-notes/         # 个人笔记，支持全文检索（端口 8007）
│   ├── knowledge-base/         # 知识库，向量检索（端口 8003）
│   ├── rss-reader/             # RSS 订阅聚合（端口 8010）
│   ├── sense/                  # 感知数据收集，健康 + 系统状态（端口 8005）
│   ├── status-sense/           # 系统状态历史，供感知面板展示（端口 8013）
│   ├── workflow-viewer/        # 工作流可视化，展示 Arbor 执行记录（端口 8014）
│   ├── life-memory/            # 生活记忆图谱，长期记忆存储（端口 8004）
│   └── calendar/               # 日历与日程管理（端口 8011）
│
├── core/                       # 基础设施，所有服务共用
│   ├── arbor/                  # 事件路由核心，FastRouter/SemanticRouter/DynamicRouter（端口 8090）
│   ├── caddy/                  # 反向代理，统一入口，自签名 HTTPS（端口 443/8900）
│   ├── nats/                   # 消息队列，服务间事件总线（端口 4222）
│   ├── postgres/               # PostgreSQL + pgvector，结构化数据 + 向量检索（端口 5432）
│   ├── redis/                  # 缓存与上下文图谱（端口 6379）
│   └── whisper/                # 本地语音识别，供会议纪要 / 视频转写调用（端口 8081）
│
├── sdk/                        # 开发套件，新 App 接入 Nervus 生态时使用
│   ├── python/                 # Python SDK，14 个现有 App 均基于此构建
│   └── typescript/             # TypeScript SDK，供前端或 Node.js App 使用
│
├── docker-compose.yml          # 一键启动全部服务
└── docs/                       # 项目文档
    ├── porting-guide.md        # 新 App 接入手册（NSI 接口规范）
    ├── audit-v1.2.md           # v1.2 代码审查报告，记录已知问题与优先级
    └── Nervus_完整开发文档.md  # 完整架构设计文档
```

---

## 内存参考（Jetson Orin Nano 8GB）

| 组件 | 占用 |
|------|------|
| 系统底层 | ~1.5 GB |
| LLM（Qwen 4B INT4） | ~2.8 GB |
| Redis + PostgreSQL + NATS | ~550 MB |
| Caddy + 各 App 服务 | ~1.5 GB |
| **合计** | **~6.4 GB** |
