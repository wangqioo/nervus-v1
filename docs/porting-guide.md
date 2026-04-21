# Nervus App 移植手册

> 拿到这份文档即可独立完成移植，无需参考其他资料。

---

## 1. 系统架构速览

```
iPhone/Browser
    │
    ▼ HTTP
Caddy (:443 nervus.local / :8900 HTTP)
    │
    ├─ /api/{app-id}/*  ──►  nervus-app-{id}:{port}   (各 App，FastAPI)
    ├─ /api/llm/*        ──►  nervus-llama:8080          (Qwen3.5 LLM)
    └─ /api/*            ──►  nervus-arbor:8090           (路由总线)
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼             ▼
                    nervus-nats   nervus-redis  nervus-postgres
                  (事件总线)     (上下文缓存)    (持久化/向量)
```

- **每个 App** 是一个独立的 Docker 容器，运行 FastAPI 服务
- **nervus-sdk** 封装了 LLM / NATS / Redis / Postgres 所有基础设施调用
- **Caddy** 负责将 `/api/{app-id}/*` 路由到对应容器，前端直接 `fetch('/api/...')`
- **Arbor** 是中枢路由和 App 注册中心，App 启动时自动注册

---

## 2. 已用端口一览（新 App 从 8015 往后顺序分配）

| 端口 | 容器名 | App ID |
|------|--------|--------|
| 8001 | nervus-app-calorie | calorie-tracker |
| 8002 | nervus-app-meeting | meeting-notes |
| 8003 | nervus-app-knowledge | knowledge-base |
| 8004 | nervus-app-life | life-memory |
| 8005 | nervus-app-sense | sense |
| 8006 | nervus-app-photo | photo-scanner |
| 8007 | nervus-app-notes | personal-notes |
| 8008 | nervus-app-pdf | pdf-extractor |
| 8009 | nervus-app-video | video-transcriber |
| 8010 | nervus-app-rss | rss-reader |
| 8011 | nervus-app-calendar | calendar |
| 8012 | nervus-app-reminder | reminder |
| 8013 | nervus-app-status-sense | status-sense |
| 8014 | nervus-app-workflow | workflow-viewer |
| **8015+** | **新 App 从这里开始** | — |

---

## 3. 移植四步流程

### 步骤 1 — 创建 App 目录

```
apps/
└── {app-id}/          ← 用小写中划线，如 habit-tracker
    ├── main.py        ← 核心逻辑（唯一必须文件）
    ├── requirements.txt
    └── Dockerfile
```

### 步骤 2 — 编写 main.py（模板见第 4 节）

### 步骤 3 — 在 docker-compose.yml 添加服务（模板见第 5 节）

### 步骤 4 — 在 caddy/Caddyfile 添加路由（模板见第 6 节）

完成后执行部署命令（见第 8 节）。

---

## 4. main.py 完整模板

```python
"""
{AppName} — {功能简述}
"""

import os
import json
from datetime import datetime
from typing import Optional

# ── SDK 导入（固定写法，所有 App 相同）──
import sys
sys.path.insert(0, "/app/nervus-sdk")
from nervus_sdk import NervusApp, emit
from nervus_sdk.models import Event

# ── 初始化（app_id 必须与目录名、docker-compose service 名一致）──
nervus = NervusApp("{app-id}")

# ════════════════════════════════════════
# 数据库（SQLite，推荐用法）
# ════════════════════════════════════════
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "/data/{app-id}.db")

def get_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                id         TEXT PRIMARY KEY,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

init_db()

# ════════════════════════════════════════
# Actions（供 Arbor / 其他 App 调用）
# ════════════════════════════════════════

@nervus.action("create_item")
async def action_create_item(payload: dict) -> dict:
    import uuid
    item_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO items (id, content, created_at, updated_at) VALUES (?,?,?,?)",
            (item_id, payload.get("content", ""), now, now)
        )
    # 可选：发布事件到总线
    # await emit("myapp.item.created", {"item_id": item_id})
    return {"item_id": item_id, "status": "created"}

# ════════════════════════════════════════
# REST API（供前端直接调用）
# ════════════════════════════════════════

@nervus._api.get("/items")
async def list_items(limit: int = 50):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM items ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return {"items": [dict(r) for r in rows]}

@nervus._api.post("/items")
async def create_item(body: dict):
    return await action_create_item(body)

@nervus._api.get("/items/{item_id}")
async def get_item(item_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")
    return dict(row)

@nervus._api.delete("/items/{item_id}")
async def delete_item(item_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    return {"item_id": item_id, "status": "deleted"}

# ════════════════════════════════════════
# 事件订阅（可选，监听总线事件）
# ════════════════════════════════════════

# @nervus.on("some.other.app.event")
# async def handle_event(event: Event):
#     data = event.payload
#     ...

# ════════════════════════════════════════
# 状态快照（供 Sense / 前端展示）
# ════════════════════════════════════════

@nervus.state
async def get_state():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM items").fetchone()["c"]
    return {"total_items": total}

# ════════════════════════════════════════
# 启动
# ════════════════════════════════════════

if __name__ == "__main__":
    nervus.run(port=int(os.getenv("APP_PORT", "8015")))
```

---

## 5. Dockerfile 模板

```dockerfile
FROM nervus-python-base:latest
WORKDIR /app
COPY nervus-sdk /app/nervus-sdk
COPY apps/{app-id}/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
 && pip install --no-cache-dir /app/nervus-sdk -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY apps/{app-id}/. .
RUN mkdir -p /data
EXPOSE {PORT}
CMD ["python", "main.py"]
```

---

## 6. requirements.txt 模板（最小集）

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
nats-py>=2.6.0
redis>=5.0.0
httpx>=0.27.0
pydantic>=2.0.0
```

如果需要额外依赖（如 `pandas`、`Pillow` 等），直接追加。

---

## 7. docker-compose.yml — 新增服务块

在 `services:` 下添加（参考已有 app 格式，替换 `{...}` 占位符）：

```yaml
  app-{app-id}:
    build:
      context: .
      dockerfile: apps/{app-id}/Dockerfile
    image: nervus-app-{app-id}:latest
    container_name: nervus-app-{short-name}
    entrypoint: []
    restart: unless-stopped
    depends_on:
      - arbor-core
    networks:
      - nervus-net
    ports:
      - "{PORT}:{PORT}"
    environment:
      APP_PORT: "{PORT}"
      NATS_URL: nats://nervus-nats:4222
      REDIS_URL: redis://nervus-redis:6379
      POSTGRES_URL: postgresql://nervus:nervus_secret@nervus-postgres:5432/nervus?sslmode=disable
      LLAMA_URL: http://nervus-llama:8080
      ARBOR_URL: http://nervus-arbor:8090
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{PORT}/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
```

**注意：** `container_name` 用作内部 DNS，Caddy 的 `reverse_proxy` 指向它。

---

## 8. caddy/Caddyfile — 新增路由

Caddyfile 中有两个相同的块（一个是 `nervus.local` HTTPS，一个是 `:8900` HTTP），**两处都要加**，且必须放在 `handle /api/*` 这一行**之前**：

```caddyfile
    handle /api/{app-id}/* {
        uri strip_prefix /api/{app-id}
        reverse_proxy nervus-app-{short-name}:{PORT}
    }
```

替换规则：
- `{app-id}` = App 的 URL 路径段（与目录名相同，如 `habit-tracker`）
- `{short-name}` = `container_name` 中 `nervus-app-` 后面的部分
- `{PORT}` = 分配的端口号

---

## 9. 部署命令（SSH 到设备后执行）

```bash
cd ~/nervus

# 1. 构建新 App 镜像
docker compose build app-{app-id}

# 2. 启动新容器
docker compose up -d app-{app-id}

# 3. 重载 Caddy 路由（让新路由生效）
docker restart nervus-caddy

# 4. 验证
curl -s http://localhost:8900/api/{app-id}/health
# 期望: {"status":"ok","app_id":"{app-id}"}

curl -s http://localhost:8900/api/{app-id}/{your-endpoint}
# 验证具体接口
```

---

## 10. SDK 能力速查

### 10.1 调用 LLM（文字对话）

```python
# nervus.llm 已在 NervusApp 中自动初始化
text = await nervus.llm.chat(
    prompt="用户输入的内容",
    system="你是专业助手，简洁回答。",   # 可选，默认有
    temperature=0.3,
    max_tokens=512,
)
# 返回: str

# 返回 JSON 对象
data = await nervus.llm.chat_json(
    prompt="分析这段文本，返回 {score: int, tags: list}",
)
# 返回: dict
```

### 10.2 调用 LLM（视觉识别）

```python
result = await nervus.llm.vision(
    image_path="/data/photo.jpg",   # 本地路径 或 http URL
    prompt="识别图中食物并估算热量",
    temperature=0.2,
)
# 返回: str

data = await nervus.llm.vision_json(
    image_path="/data/photo.jpg",
    prompt="返回 {items: [{name, kcal}]}",
)
# 返回: dict
```

### 10.3 发布 / 订阅事件

```python
from nervus_sdk import emit

# 发布事件（在任意 async 函数中）
await emit("health.calorie.logged", {"kcal": 500, "meal": "lunch"})

# 订阅事件（在 App 顶层声明）
@nervus.on("media.photo.classified", filter={"tags_contains": ["food"]})
async def on_food_photo(event: Event):
    payload = event.payload   # dict
    source  = event.source_app
    ...
```

**常用事件主题约定：**

| 主题 | 含义 |
|------|------|
| `media.photo.taken` | 新照片 |
| `media.photo.classified` | 照片已分类 |
| `health.calorie.logged` | 卡路里记录 |
| `knowledge.note.created` | 笔记新建/更新 |
| `knowledge.document.added` | 文档添加 |
| `system.daily.morning` | 每日早间触发 |

### 10.4 读写 Redis 上下文

```python
from nervus_sdk import Context

# 写（自动序列化 JSON）
await Context.set("physical.calorie_remaining", 800)
await Context.set("cognitive.load", "high")

# 读
val = await Context.get("physical.calorie_remaining")  # 返回原始值

# 带过期时间（秒）
await Context.set("temp.processing", True, ttl=300)
```

### 10.5 写入 Memory Graph（向量记忆，可选）

```python
from nervus_sdk import MemoryGraph

await MemoryGraph.store(
    subject="user",
    predicate="ate",
    obj="lunch at 12:30",
    embedding_text="用户午饭吃了米饭和蔬菜",
)

results = await MemoryGraph.search("今天吃了什么", limit=5)
```

---

## 11. 前端调用规范

前端 `fetch` 路径格式：`/api/{app-id}/{endpoint}`

示例：
```javascript
// 获取列表
const res = await fetch('/api/habit-tracker/habits');
const { habits } = await res.json();

// 创建
await fetch('/api/habit-tracker/habits', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ name: '早起', frequency: 'daily' })
});

// 删除
await fetch(`/api/habit-tracker/habits/${id}`, { method: 'DELETE' });
```

---

## 12. 完整移植 Checklist

```
□ 1. apps/{app-id}/ 目录已创建
□ 2. main.py 完成，app_id 与目录名一致
□ 3. requirements.txt 列出所有依赖
□ 4. Dockerfile 端口号与 APP_PORT 一致
□ 5. docker-compose.yml 新服务已添加（ports / environment 正确）
□ 6. caddy/Caddyfile 两处路由块均已添加（HTTPS + HTTP 8900）
□ 7. docker compose build app-{app-id}  ← 构建成功（无报错）
□ 8. docker compose up -d app-{app-id}  ← 容器已 Up
□ 9. curl /health 返回 {"status":"ok"}
□ 10. docker restart nervus-caddy  ← 路由重载
□ 11. curl http://localhost:8900/api/{app-id}/health  ← 通过 Caddy 验证
□ 12. 主要接口手动测试通过
□ 13. git add / commit / push（通过工具推送，设备无法直连 GitHub）
```

---

## 13. 常见问题

**Q: App 启动后注册不到 Arbor？**
Arbor 重启后内存清空，执行 `docker restart nervus-app-{short-name}` 即可重新注册。

**Q: LLM 返回空字符串？**
SDK 已内置 `chat_template_kwargs: {"enable_thinking": false}`，正常不会出现。如果自己手写 `httpx` 调用要记得加这个参数。

**Q: SQLite 并发写入报错？**
在高并发场景改用 `check_same_thread=False`，或换用 Postgres（通过 `POSTGRES_URL` 环境变量已注入，用 `asyncpg` 连接）。

**Q: 新 App 的接口返回 404？**
检查 Caddyfile 两处（HTTPS 和 :8900）是否都加了路由，且 `docker restart nervus-caddy` 后是否有报错日志（`docker logs nervus-caddy`）。

**Q: 镜像构建失败（pip 超时）？**
所有 pip 已走清华镜像，如仍超时检查设备网络，或在 requirements.txt 中固定版本号。

---

## 14. 参考：一个完整的最小 App（habit-tracker，端口 8015）

**文件结构：**
```
apps/habit-tracker/
├── Dockerfile
├── requirements.txt
└── main.py
```

**main.py 核心部分：**
```python
nervus = NervusApp("habit-tracker")

@nervus._api.get("/habits")
async def list_habits():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM habits ORDER BY created_at DESC").fetchall()
    return {"habits": [dict(r) for r in rows]}

@nervus._api.post("/habits")
async def create_habit(body: dict):
    ...

if __name__ == "__main__":
    nervus.run(port=int(os.getenv("APP_PORT", "8015")))
```

**docker-compose 片段：**
```yaml
  app-habit-tracker:
    build:
      context: .
      dockerfile: apps/habit-tracker/Dockerfile
    image: nervus-app-habit-tracker:latest
    container_name: nervus-app-habit
    entrypoint: []
    ...
    environment:
      APP_PORT: "8015"
      ...
```

**Caddyfile 路由（两处）：**
```caddyfile
    handle /api/habit-tracker/* {
        uri strip_prefix /api/habit-tracker
        reverse_proxy nervus-app-habit:8015
    }
```

**前端调用：**
```javascript
fetch('/api/habit-tracker/habits')
```

---

*手册版本：2026-04-21 · 适用于 Nervus aarch64/Jetson Orin Nano 部署*
