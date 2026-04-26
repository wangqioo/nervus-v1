# Nervus App 接入手册

> 拿到这份文档即可独立完成接入，无需参考其他资料。

---

## 1. 架构一眼看懂

```
iPhone/Browser
    │
    ▼ HTTP
Caddy (:443 / :8900)
    │
    ├─ /api/{app-id}/*  ──►  nervus-app-{id}:{port}   （你的 App）
    ├─ /api/models/chat  ──►  nervus-arbor:8090         （LLM 网关）
    └─ /api/*            ──►  nervus-arbor:8090         （平台基座）
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼             ▼
                    nervus-nats   nervus-redis  nervus-postgres
```

**每个 App 是独立的 Docker 容器，通过 Nervus SDK 接入生态：**
- 启动时向 Arbor 注册（自动）
- 每 60s 上报心跳（自动）
- 通过 NATS 收发事件
- 向平台 API 写入知识/读取数据

---

## 2. 已用端口

新 App 从 **8016** 往后顺序分配。

| 端口 | App ID |
|------|--------|
| 8001 | calorie-tracker |
| 8002 | meeting-notes |
| 8003 | knowledge-base |
| 8004 | life-memory |
| 8005 | sense |
| 8006 | photo-scanner |
| 8007 | personal-notes |
| 8008 | pdf-extractor |
| 8009 | video-transcriber |
| 8010 | rss-reader |
| 8011 | calendar |
| 8012 | reminder |
| 8013 | status-sense |
| 8014 | workflow-viewer |
| 8015 | file-manager |

---

## 3. 接入四步

1. 创建 `apps/{app-id}/` 目录（`main.py` + `manifest.json` + `Dockerfile` + `requirements.txt`）
2. 在 `docker-compose.yml` 添加服务块
3. 在 `core/caddy/Caddyfile` 两处添加路由
4. 构建并部署

---

## 4. manifest.json（必须）

放在 `apps/{app-id}/manifest.json`，SDK 启动时自动加载（Docker 挂载到 `/app/manifest.json`）。

```json
{
  "schema_version": "0.1",
  "id": "habit-tracker",
  "name": "习惯追踪",
  "type": "nervus",
  "version": "0.1.0",
  "description": "记录和追踪每日习惯",
  "icon": "✅",
  "route": "/api/habit-tracker",
  "service": {
    "container": "nervus-app-habit",
    "internal_url": "",
    "port": 8016
  },
  "capabilities": {
    "actions": [
      {
        "name": "log_habit",
        "description": "记录一次习惯完成",
        "input": { "habit_id": "string", "date": "string" }
      }
    ],
    "consumes": [],
    "emits": ["schedule.habit.logged"],
    "models": [],
    "writes": []
  }
}
```

**字段说明：**

| 字段 | 说明 |
|------|------|
| `schema_version` | 固定填 `"0.1"` |
| `id` | 全局唯一，与目录名、docker service 名一致 |
| `type` | 固定填 `"nervus"` |
| `service.container` | docker container_name |
| `service.port` | App 端口（与 APP_PORT 一致）|
| `capabilities.consumes` | 订阅的 NATS 主题列表 |
| `capabilities.emits` | 发布的 NATS 主题列表 |
| `capabilities.actions` | 可被 Flow / 其他 App 调用的 action |
| `capabilities.writes` | 写入的数据类型（`knowledge` / `memory` 等）|

---

## 5. main.py 模板

```python
"""
{AppName} — {功能简述}
"""
import os
from datetime import datetime

from nervus_sdk import NervusApp
from nervus_sdk.models import Event

nervus = NervusApp("{app-id}")

# ── 数据库（SQLite，简单场景够用）──────────────
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
                created_at TEXT NOT NULL
            );
        """)

init_db()

# ── Actions（供 Flow / 其他 App 调用）─────────
@nervus.action("log_habit")
async def action_log_habit(habit_id: str, date: str = "") -> dict:
    import uuid
    item_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO items (id, content, created_at) VALUES (?,?,?)",
            (item_id, habit_id, now)
        )
    await nervus.emit("schedule.habit.logged", {"habit_id": habit_id, "logged_at": now})
    return {"item_id": item_id, "status": "logged"}

# ── REST API（供前端直接调用）─────────────────
@nervus._api.get("/habits")
async def list_habits(limit: int = 50):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM items ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return {"habits": [dict(r) for r in rows]}

@nervus._api.post("/habits")
async def create_habit(body: dict):
    return await action_log_habit(body.get("habit_id", ""), body.get("date", ""))

# ── 事件订阅（可选）─────────────────────────
# @nervus.on("system.daily.morning")
# async def on_morning(event: Event):
#     # 每天早上触发
#     pass

# ── 状态快照（供前端 / Sense 面板）──────────
@nervus.state
async def get_state():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM items").fetchone()["c"]
    return {"total_logged": total}

# ── 启动 ──────────────────────────────────
if __name__ == "__main__":
    nervus.run(port=int(os.getenv("APP_PORT", "8016")))
```

---

## 6. Dockerfile 模板

```dockerfile
FROM nervus-python-base:latest
WORKDIR /app
COPY nervus-sdk /app/nervus-sdk
COPY apps/{app-id}/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
 && pip install --no-cache-dir /app/nervus-sdk -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY apps/{app-id}/manifest.json /app/manifest.json
COPY apps/{app-id}/. .
RUN mkdir -p /data
EXPOSE {PORT}
CMD ["python", "main.py"]
```

> 关键：`manifest.json` 必须复制到 `/app/manifest.json`，SDK 会从这里自动加载。

---

## 7. docker-compose.yml 服务块

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
      APP_INTERNAL_URL: "http://nervus-app-{short-name}:{PORT}"
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

> `APP_INTERNAL_URL` 是 Arbor 回调你的 App 时用的地址，必须填对。

---

## 8. Caddyfile 路由（两处都要加）

文件位置：`core/caddy/Caddyfile`。

有两个块（HTTPS `nervus.local` 和 HTTP `:8900`），**两处都要加**，且必须放在 `handle /api/*` 之前：

```caddyfile
    handle /api/{app-id}/* {
        uri strip_prefix /api/{app-id}
        reverse_proxy nervus-app-{short-name}:{PORT}
    }
```

---

## 9. 部署命令

```bash
cd ~/nervus

# 构建新镜像
docker compose build app-{app-id}

# 启动
docker compose up -d app-{app-id}

# 重载 Caddy 路由
docker restart nervus-caddy

# 验证
curl -s http://localhost:8900/api/{app-id}/health
# 期望: {"status":"ok","app_id":"{app-id}"}

# 确认已注册到 Arbor
curl -s http://localhost:8900/api/apps | python3 -m json.tool | grep "{app-id}"
```

---

## 10. SDK 能力速查

### 10.1 调用 LLM

推荐走平台 Chat 网关（`/api/models/chat`），避免直连 llama.cpp：

```python
# 方式 A：通过 SDK（内部走 llama.cpp）
text = await nervus.llm.chat(
    prompt="用户输入",
    system="你是专业助手，简洁回答。",
    temperature=0.3,
    max_tokens=512,
)

# 方式 B：调用平台 Chat 网关（推荐，模型不可用时返回结构化错误）
import httpx
async with httpx.AsyncClient() as client:
    resp = await client.post(
        f"{os.getenv('ARBOR_URL')}/models/chat",
        json={
            "model": "qwen3.5",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 512,
        }
    )
    content = resp.json()["content"]
```

### 10.2 视觉识别

```python
data = await nervus.llm.vision_json(
    image_path="/data/photo.jpg",
    prompt="返回 {items: [{name, kcal}]}",
)
```

### 10.3 发布 / 订阅事件

```python
# 发布
await nervus.emit("health.calorie.logged", {"kcal": 500})

# 订阅（在顶层声明）
@nervus.on("media.photo.classified", filter={"tags_contains": ["food"]})
async def on_food_photo(event: Event):
    payload = event.payload
```

**常用事件主题：**

| 主题 | 含义 |
|------|------|
| `media.photo.classified` | 照片已分类 |
| `meeting.recording.processed` | 录音转写完成 |
| `health.calorie.meal_logged` | 饮食记录写入 |
| `knowledge.document.indexed` | 文档向量化完成 |
| `schedule.reminder.triggered` | 提醒时间到达 |
| `system.daily.morning` | 每日早间触发 |

### 10.4 Context Graph（Redis）

```python
from nervus_sdk import Context

await Context.set("physical.calorie_remaining", 800)
val = await Context.get("physical.calorie_remaining")
await Context.set("temp.processing", True, ttl=300)
```

### 10.5 写入平台知识库

```python
import httpx

async with httpx.AsyncClient() as client:
    await client.post(
        f"{os.getenv('ARBOR_URL')}/platform/knowledge",
        json={
            "type": "note",
            "title": "今日会议要点",
            "content": transcript,
            "summary": summary,
            "source_app": "meeting-notes",
            "tags": ["meeting", "2026"],
        }
    )
```

---

## 11. 接入 Checklist

```
□ 1. apps/{app-id}/manifest.json 已创建（schema_version: "0.1"）
□ 2. main.py 完成，NervusApp("{app-id}") 与 manifest.id 一致
□ 3. Dockerfile 中 manifest.json 复制到 /app/manifest.json
□ 4. docker-compose.yml 服务块已添加（含 APP_INTERNAL_URL）
□ 5. Caddyfile 两处路由块均已添加
□ 6. docker compose build app-{app-id}  ← 构建成功
□ 7. docker compose up -d app-{app-id}  ← 容器已 Up
□ 8. curl /health 返回 {"status":"ok"}
□ 9. docker restart nervus-caddy
□ 10. curl http://localhost:8900/api/{app-id}/health  ← 通过 Caddy 验证
□ 11. curl http://localhost:8900/api/apps | grep "{app-id}"  ← 已注册到 Arbor
□ 12. 主要接口手动测试通过
```

---

## 12. 常见问题

**Q: App 启动后没有出现在 /api/apps？**
检查 `APP_INTERNAL_URL` 是否填对；检查 Arbor 是否健康（`curl /api/health`）；查看 App 日志 `docker logs nervus-app-{name}`。

**Q: LLM 返回空字符串？**
SDK 内置 `chat_template_kwargs: {"enable_thinking": false}`。自己手写 httpx 调用时记得加这个参数。

**Q: SQLite 并发写入报错？**
改用 `check_same_thread=False`，或换用 Postgres（`POSTGRES_URL` 已注入，用 `asyncpg` 连接）。

**Q: Caddyfile 改了但路由不生效？**
执行 `docker restart nervus-caddy`，然后查看日志 `docker logs nervus-caddy`。

**Q: 镜像构建失败（pip 超时）？**
所有 pip 已走清华镜像。如仍超时检查网络，或在 requirements.txt 中固定版本号。
