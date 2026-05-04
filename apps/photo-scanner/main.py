"""
相册扫描器 — 感知层核心服务
定时扫描新照片，调用 AI 分类，发布到 Synapse Bus
是整个系统数据流的起点
"""

import asyncio
import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

import sys
sys.path.insert(0, "/app/nervus-sdk")
from nervus_sdk import NervusApp, Context, emit
from nervus_sdk.models import Manifest

# ── 配置 ─────────────────────────────────────────────────

nervus = NervusApp("photo-scanner")
with open(Path(__file__).parent / "manifest.json") as f:
    nervus.set_manifest(Manifest(**json.load(f)))

DB_PATH = os.getenv("DB_PATH", "/data/photo-scanner.db")
PHOTOS_DIR = os.getenv("PHOTOS_DIR", "/photos")  # 挂载相册目录
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "30"))  # 秒

# 场景 → tags 映射（AI 分类的补充规则）
SCENE_TAGS = {
    "food": ["food"],
    "restaurant": ["food", "restaurant"],
    "beach": ["outdoor", "travel", "beach"],
    "mountain": ["outdoor", "travel", "mountain"],
    "city": ["outdoor", "travel", "city"],
    "whiteboard": ["whiteboard", "meeting", "work"],
    "document": ["document", "work"],
    "nature": ["outdoor", "nature"],
    "indoor": ["indoor"],
    "people": ["people", "social"],
    "animal": ["animal"],
    "vehicle": ["vehicle", "travel"],
}


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scanned_photos (
            id          TEXT PRIMARY KEY,
            photo_path  TEXT UNIQUE NOT NULL,
            tags        TEXT,           -- JSON array
            scene       TEXT,
            objects     TEXT,           -- JSON array
            classified  INTEGER DEFAULT 0,
            event_published INTEGER DEFAULT 0,
            file_mtime  TEXT,
            created_at  TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── AI 分类 ───────────────────────────────────────────────

async def classify_photo(photo_path: str) -> dict:
    """调用 AI 对照片进行场景/对象分类"""
    prompt = """请分析这张照片，返回JSON格式的分类结果：
{
  "scene": "主要场景（food/restaurant/beach/mountain/city/whiteboard/document/nature/indoor/people/animal/vehicle/other）",
  "objects": ["识别到的主要对象1", "对象2"],
  "tags": ["标签1", "标签2", "标签3"],
  "location_type": "home/office/restaurant/outdoor/travel/other",
  "is_meeting_related": false
}
只返回JSON，不要其他文字。"""

    try:
        result = await nervus.llm.vision_json(photo_path, prompt)
        # 补充场景标签
        scene = result.get("scene", "other")
        extra_tags = SCENE_TAGS.get(scene, [])
        tags = list(set(result.get("tags", []) + extra_tags))
        result["tags"] = tags
        return result
    except Exception as e:
        return {
            "scene": "other",
            "objects": [],
            "tags": ["photo"],
            "location_type": "other",
            "is_meeting_related": False,
        }


# ── 扫描逻辑 ──────────────────────────────────────────────

async def scan_and_publish(photo_path: str) -> dict | None:
    """扫描单张照片并发布事件"""
    # 检查是否已处理
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id, event_published FROM scanned_photos WHERE photo_path = ?", (photo_path,)
        ).fetchone()
        if existing and existing["event_published"]:
            return None

    # AI 分类
    classification = await classify_photo(photo_path)
    tags = classification.get("tags", [])
    scene = classification.get("scene", "other")

    photo_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # 保存到数据库
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO scanned_photos
            (id, photo_path, tags, scene, objects, classified, event_published, created_at)
            VALUES (?, ?, ?, ?, ?, 1, 0, ?)
        """, (
            photo_id, photo_path,
            json.dumps(tags), scene,
            json.dumps(classification.get("objects", [])),
            now,
        ))
        conn.commit()

    # 读取上下文
    is_traveling = await Context.get("travel.is_traveling", False)
    recent_meeting = await Context.get("social.recent_meeting")

    # 构建事件 payload
    payload = {
        "photo_id": photo_id,
        "photo_path": photo_path,
        "tags": tags,
        "scene": scene,
        "objects": classification.get("objects", []),
        "location_type": classification.get("location_type", "other"),
        "is_traveling": is_traveling,
        "timestamp": now,
    }

    # 发布主事件
    await emit("media.photo.classified", payload)

    # 白板检测：检查是否与最近会议时间窗口重叠
    if classification.get("is_meeting_related") or "whiteboard" in tags:
        await emit("meeting.whiteboard.detected", {
            **payload,
            "context": "whiteboard",
            "recent_meeting": recent_meeting,
        })

    # 更新数据库已发布状态
    with get_db() as conn:
        conn.execute("UPDATE scanned_photos SET event_published = 1 WHERE id = ?", (photo_id,))
        conn.commit()

    return {"photo_id": photo_id, "tags": tags, "scene": scene}


async def background_scanner():
    """后台定时扫描任务"""
    photos_dir = Path(PHOTOS_DIR)
    if not photos_dir.exists():
        photos_dir.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            # 扫描目录中的图片文件
            image_extensions = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
            photo_files = [
                p for p in photos_dir.rglob("*")
                if p.suffix.lower() in image_extensions
            ]

            new_count = 0
            for photo_path in photo_files[-50:]:  # 每次最多处理 50 张
                result = await scan_and_publish(str(photo_path))
                if result:
                    new_count += 1
                    await asyncio.sleep(0.5)  # 避免 AI 调用过于密集

            if new_count > 0:
                # 发布批量处理完成事件
                await emit("media.photo.batch_processed", {
                    "processed_count": new_count,
                    "timestamp": datetime.utcnow().isoformat(),
                })

        except Exception as e:
            import logging
            logging.getLogger("nervus.photo-scanner").error(f"扫描任务异常: {e}")

        await asyncio.sleep(SCAN_INTERVAL)


# ── Action 注册 ───────────────────────────────────────────

@nervus.action("classify_photo")
async def action_classify_photo(photo_path: str = ""):
    return await classify_photo(photo_path)


@nervus.action("scan_batch")
async def action_scan_batch(directory: str = PHOTOS_DIR, since: str = ""):
    path = Path(directory)
    if not path.exists():
        return {"error": "目录不存在", "processed": 0}

    image_extensions = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
    photos = [p for p in path.rglob("*") if p.suffix.lower() in image_extensions]

    results = []
    for photo in photos[:100]:
        result = await scan_and_publish(str(photo))
        if result:
            results.append(result)
        await asyncio.sleep(0.3)

    return {"processed": len(results), "classified": results}


@nervus.state
async def get_state():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM scanned_photos").fetchone()["c"]
        published = conn.execute("SELECT COUNT(*) as c FROM scanned_photos WHERE event_published = 1").fetchone()["c"]
    return {"total_scanned": total, "events_published": published}


# ── API 端点 ──────────────────────────────────────────────

@nervus._api.post("/upload")
async def upload_photo(file: UploadFile = File(...)):
    """
    接收手机上传的照片（CLI 或 HTTP 客户端上传）
    保存到 /photos 目录并立即触发分类
    """
    import aiofiles
    photos_dir = Path(PHOTOS_DIR)
    photos_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "photo.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    save_path = photos_dir / filename

    async with aiofiles.open(save_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # 立即异步分类（不等待）
    asyncio.create_task(scan_and_publish(str(save_path)))

    return {"status": "ok", "photo_path": str(save_path), "filename": filename}


@nervus._api.get("/recent")
async def recent_photos(limit: int = 20):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, photo_path, tags, scene, created_at FROM scanned_photos ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return {"photos": [dict(r) for r in rows]}


# ── 启动后台任务 ──────────────────────────────────────────

original_startup = nervus._startup


async def extended_startup():
    await original_startup()
    asyncio.create_task(background_scanner())


nervus._startup = extended_startup


if __name__ == "__main__":
    init_db()
    nervus.run(port=int(os.getenv("APP_PORT", "8006")))
