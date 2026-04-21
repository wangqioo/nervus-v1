# Nervus

> 连接所有 App 的神经系统

**它从未停止存在过。**

---

## 项目结构

```
nervus/
├── docker-compose.yml          # 一键启动所有服务
├── start.sh                    # 分阶段启动脚本（基础设施→Arbor→Apps→Caddy）
├── Dockerfile.base             # Python 3.12 基础镜像（aarch64/Jetson 专用）
├── Dockerfile.caddy            # Caddy ARM64 自定义镜像
├── Dockerfile.postgres         # pgvector 自定义镜像
├── nats/                       # NATS 突触总线配置
├── redis/                      # Redis Context Graph 配置
├── postgres/                   # PostgreSQL Memory Graph 初始化 SQL
├── caddy/                      # 反向代理配置（局域网 HTTPS + HTTP :8900）
├── whisper/                    # faster-whisper 语音转写服务
├── arbor-core/                 # Nervus 神经路由中枢
│   ├── router/                 # 快速/语义/动态三种路由引擎
│   ├── executor/               # Flow 执行引擎 + 流程加载器
│   ├── flows/                  # JSON 流程配置
│   └── api/                    # App 注册、通知、状态 API
├── nervus-sdk/                 # Python SDK
├── nervus-sdk-ts/              # TypeScript SDK
├── mobile/                     # 前端（单文件 SPA，已接真实 API）
│   └── index.html
└── docs/
    └── porting-guide.md        # App 移植手册（自包含，无需参考其他文档）
apps/
├── calorie-tracker/            # 热量管理（拍照自动记录）
├── meeting-notes/              # 会议纪要（录音+白板自动整合）
├── photo-scanner/              # 相册扫描器（感知层）
├── knowledge-base/             # 知识库（语义检索+问答）
├── life-memory/                # 人生记忆库（旅行日志+时间线）
├── personal-notes/             # 个人笔记（CRUD + 向量化）
├── pdf-extractor/              # PDF 解析与知识提取
├── rss-reader/                 # RSS 阅读器
├── reminder/                   # 提醒事项
├── calendar/                   # 日历事件
├── sense/                      # 感知页数据服务
├── status-sense/               # 系统状态感知
├── video-transcriber/          # 视频转写
└── workflow-viewer/            # 工作流可视化
```

---

## 快速开始（Jetson Orin Nano）

### 1. 克隆并构建

```bash
git clone https://github.com/wangqioo/nervus-core.git nervus
cd nervus
```

### 2. 准备 AI 模型

```bash
mkdir -p models
# 下载到 models/ 目录：
# - qwen3.5-4b-multimodal-q4_k_m.gguf
# - mmproj-qwen3.5-4b.gguf
```

### 3. 分阶段启动

```bash
# 方式 A：使用启动脚本（推荐）
chmod +x start.sh && ./start.sh

# 方式 B：手动分阶段
docker compose up -d nats redis postgres
sleep 10
docker compose up -d arbor-core
sleep 5
docker compose up -d $(docker compose config --services | grep ^app-)
docker compose up -d caddy llama-cpp whisper
```

### 4. 验证

```bash
# 系统总线
curl http://localhost:8900/api/status

# 所有已注册的 App
curl http://localhost:8900/api/apps/list

# 前端
open http://nervus.local  # 或 http://<device-ip>:8900
```

---

## 核心概念

### Synapse Bus（突触总线）

所有数据通过 NATS 事件总线流动。主题命名规范：

```
{domain}.{entity}.{verb}

media.photo.classified
meeting.recording.processed
health.calorie.meal_logged
context.user_state.updated
knowledge.document.indexed
```

### NSI（Nervus Standard Interface）

每个 App 必须实现：

```
GET  /manifest    能力声明
POST /intake/:id  接收事件
POST /action/:id  执行能力
GET  /state       当前状态
GET  /health      健康检查
```

### Context Graph

用户当下状态，存储在 Redis，所有 App 共享：

```
physical.last_meal / calorie_remaining
cognitive.load (low/medium/high)
temporal.day_type / time_of_day
travel.is_traveling / current_trip
social.recent_meeting
```

### Memory Graph

长期记忆，存储在 PostgreSQL + pgvector：

- `life_events` — 人生事件（照片、会议、旅行）
- `knowledge_items` — 知识条目（文章、PDF、笔记）
- `item_relations` — 条目间的语义关联

---

## 开发 / 移植新 App

详见 **[docs/porting-guide.md](docs/porting-guide.md)** — 完整移植手册，包含：

- 端口分配表（现有 14 个 App 占用 8001–8014，新 App 从 8015 开始）
- `main.py` / `Dockerfile` / `requirements.txt` 完整模板
- `docker-compose.yml` 服务块模板
- `Caddyfile` 路由模板
- SDK 速查（LLM / 事件总线 / Context / Memory）
- 部署命令与验证 Checklist

```python
# 最简示例
from nervus_sdk import NervusApp, emit
from nervus_sdk.models import Event

app = NervusApp("my-app")

@app.on("media.photo.classified", filter={"tags_contains": ["food"]})
async def handle_food(event: Event):
    result = await app.llm.vision(event.payload["photo_path"], "识别食物")
    await emit("health.calorie.meal_logged", result)

@app._api.get("/items")
async def list_items():
    return {"items": []}

app.run(port=8015)
```

---

## 硬件要求

- **推荐：** NVIDIA Jetson Orin Nano 8GB（JetPack 6.x）
- **开发调试：** 任意 x86/ARM Linux（禁用 CUDA，使用 CPU 推理）

### 内存预算（Jetson）

| 组件 | 内存 |
|---|---|
| 系统底层 | ~1.5 GB |
| Qwen3.5-4B 多模态 INT4 | ~2.8 GB |
| Redis + PostgreSQL + NATS | ~550 MB |
| Arbor Core + 14 个 App | ~1.5 GB |
| faster-whisper（按需） | ~500 MB |
| **常驻合计** | **~6.4 GB** |
| **峰值（转写中）** | **~6.9 GB** |

---

## 网络访问

| 方式 | 地址 | 说明 |
|------|------|------|
| 局域网 HTTPS | `https://nervus.local` | 需要设备已配置 mDNS |
| 局域网 HTTP | `http://<ip>:8900` | 无需证书，直接访问 |
| FRP 穿透 | 配置 FRP 转发 8900 端口 | 公网访问 |
