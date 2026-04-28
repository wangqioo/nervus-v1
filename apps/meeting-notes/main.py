"""
会议纪要 App
录音转写 + 白板照片 + AI 纪要生成
核心特色：白板照片与录音时间窗口交叉匹配，自动整合成完整报告
"""

import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import httpx

import sys
sys.path.insert(0, "/app/nervus-sdk")
from nervus_sdk import NervusApp, Context, emit
from nervus_sdk.models import Event

# ── 初始化 ────────────────────────────────────────────────

nervus = NervusApp("meeting-notes")

DB_PATH = os.getenv("DB_PATH", "/data/meeting-notes.db")
WHISPER_URL = os.getenv("WHISPER_URL", "http://localhost:8081")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meetings (
            id              TEXT PRIMARY KEY,
            title           TEXT,
            transcript      TEXT,
            summary_json    TEXT,       -- JSON: {overview, decisions, action_items, keywords}
            whiteboard_text TEXT,
            audio_path      TEXT,
            start_time      TEXT,
            end_time        TEXT,
            duration_sec    REAL,
            status          TEXT DEFAULT 'processing',  -- processing / completed
            created_at      TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS whiteboard_photos (
            id          TEXT PRIMARY KEY,
            meeting_id  TEXT NOT NULL,
            photo_path  TEXT NOT NULL,
            ocr_text    TEXT,
            timestamp   TEXT NOT NULL,
            FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        );
    """)
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── 核心逻辑 ──────────────────────────────────────────────

async def transcribe_audio(audio_path: str) -> dict:
    """调用 Whisper 服务转写录音"""
    try:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        import base64
        b64 = base64.b64encode(audio_bytes).decode()
        ext = Path(audio_path).suffix.lstrip(".")

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{WHISPER_URL}/transcribe/base64",
                json={"audio_b64": b64, "format": ext or "wav", "language": "zh"},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return {"text": f"[转写失败: {e}]", "segments": [], "duration": 0}


async def generate_meeting_summary(transcript: str, whiteboard_text: str = "") -> dict:
    """用 llama.cpp 生成结构化会议纪要"""
    extra = f"\n\n白板内容：\n{whiteboard_text}" if whiteboard_text else ""
    prompt = f"""请根据以下会议录音转写内容，生成结构化会议纪要（JSON格式）：

转写内容：
{transcript[:3000]}{extra}

请返回：
{{
  "title": "会议标题（简洁，15字以内）",
  "overview": "会议概要（2-3句话）",
  "key_decisions": ["决策1", "决策2"],
  "action_items": [
    {{"owner": "负责人", "task": "任务描述", "deadline": "截止时间（如有）"}}
  ],
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "sentiment": "positive/neutral/negative"
}}
只返回JSON。"""

    try:
        return await nervus.llm.chat_json(prompt, temperature=0.2, max_tokens=1024)
    except Exception as e:
        return {
            "title": "会议纪要",
            "overview": transcript[:200] + "...",
            "key_decisions": [],
            "action_items": [],
            "keywords": [],
            "sentiment": "neutral",
        }


async def ocr_whiteboard(photo_path: str) -> str:
    """用 llama.cpp 视觉模型 OCR 白板内容"""
    prompt = "请识别白板上的所有文字内容，保持原有格式，包括标题、要点、图表说明等。只返回识别到的文字，不要其他解释。"
    try:
        return await nervus.llm.vision(photo_path, prompt)
    except Exception as e:
        return f"[OCR失败: {e}]"


# ── 事件处理 ──────────────────────────────────────────────

@nervus.on("meeting.whiteboard.detected")
async def handle_whiteboard(event: Event):
    """接收到白板照片，整合进时间窗口内的会议纪要"""
    payload = event.payload
    photo_path = payload.get("photo_path", "")
    photo_time = payload.get("timestamp", str(datetime.utcnow()))

    # 找到时间窗口内的最近会议（±3小时）
    with get_db() as conn:
        meeting = conn.execute("""
            SELECT id FROM meetings
            WHERE status IN ('processing', 'completed')
            AND ABS(JULIANDAY(start_time) - JULIANDAY(?)) < 0.125
            ORDER BY created_at DESC LIMIT 1
        """, (photo_time,)).fetchone()

    if meeting:
        meeting_id = meeting["id"]
        await action_integrate_whiteboard(meeting_id=meeting_id, photo_path=photo_path)
    else:
        # 存储待关联
        wb_id = str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                "INSERT INTO whiteboard_photos (id, meeting_id, photo_path, timestamp) VALUES (?, 'pending', ?, ?)",
                (wb_id, photo_path, photo_time)
            )
            conn.commit()

    return {"status": "ok"}


# ── Action 注册 ───────────────────────────────────────────

@nervus.action("transcribe_and_summarize")
async def action_transcribe(audio_path: str = "", meeting_id: str = ""):
    """转写录音并生成纪要"""
    if not meeting_id:
        meeting_id = str(uuid.uuid4())

    # 转写
    transcription = await transcribe_audio(audio_path)
    transcript = transcription.get("text", "")
    duration = transcription.get("duration", 0)
    segments = transcription.get("segments", [])

    # 推算时间范围
    start_time = datetime.utcnow().isoformat()
    if segments:
        start_time = segments[0].get("start", 0)

    # 生成纪要
    summary = await generate_meeting_summary(transcript)
    title = summary.get("title", "会议纪要")

    # 保存到数据库
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO meetings
            (id, title, transcript, summary_json, audio_path, start_time, duration_sec, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?)
        """, (
            meeting_id, title, transcript, json.dumps(summary, ensure_ascii=False),
            audio_path, start_time, duration, datetime.utcnow().isoformat()
        ))
        conn.commit()

    # 检查是否有待关联的白板照片
    await _link_pending_whiteboards(meeting_id, start_time)

    # 更新 Context Graph
    await Context.set("social.recent_meeting", {
        "meeting_id": meeting_id,
        "title": title,
        "timestamp": start_time,
    })

    # 发布事件
    result = {
        "meeting_id": meeting_id,
        "title": title,
        "transcript": transcript[:500] + "..." if len(transcript) > 500 else transcript,
        "summary": summary,
        "timestamp_range": {"start": start_time, "duration_sec": duration},
    }
    await emit("meeting.recording.processed", result)

    return result


@nervus.action("integrate_whiteboard")
async def action_integrate_whiteboard(meeting_id: str = "", photo_path: str = ""):
    """将白板 OCR 整合进会议纪要"""
    ocr_text = await ocr_whiteboard(photo_path)

    wb_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO whiteboard_photos (id, meeting_id, photo_path, ocr_text, timestamp) VALUES (?, ?, ?, ?, ?)",
            (wb_id, meeting_id, photo_path, ocr_text, datetime.utcnow().isoformat())
        )

        # 获取现有转写内容重新生成纪要
        meeting = conn.execute("SELECT transcript, whiteboard_text FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if meeting:
            existing_wb = (meeting["whiteboard_text"] or "") + "\n" + ocr_text
            conn.execute(
                "UPDATE meetings SET whiteboard_text = ? WHERE id = ?",
                (existing_wb.strip(), meeting_id)
            )

            # 重新生成纪要（包含白板内容）
            transcript = meeting["transcript"] or ""
            if transcript:
                new_summary = await generate_meeting_summary(transcript, existing_wb)
                conn.execute(
                    "UPDATE meetings SET summary_json = ?, title = ? WHERE id = ?",
                    (json.dumps(new_summary, ensure_ascii=False), new_summary.get("title", "会议纪要"), meeting_id)
                )
        conn.commit()

    return {"success": True, "ocr_text": ocr_text, "whiteboard_id": wb_id}


@nervus.action("get_meeting")
async def action_get_meeting(meeting_id: str = ""):
    with get_db() as conn:
        meeting = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not meeting:
            return {"error": "会议不存在"}
        whiteboards = conn.execute(
            "SELECT * FROM whiteboard_photos WHERE meeting_id = ?", (meeting_id,)
        ).fetchall()
    result = dict(meeting)
    result["summary"] = json.loads(result.get("summary_json") or "{}")
    result["whiteboards"] = [dict(w) for w in whiteboards]
    return result


async def _link_pending_whiteboards(meeting_id: str, start_time: str):
    """关联待处理的白板照片"""
    with get_db() as conn:
        pending = conn.execute(
            "SELECT * FROM whiteboard_photos WHERE meeting_id = 'pending'"
        ).fetchall()
        for wb in pending:
            conn.execute(
                "UPDATE whiteboard_photos SET meeting_id = ? WHERE id = ?",
                (meeting_id, wb["id"])
            )
        conn.commit()


@nervus.state
async def get_state():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM meetings").fetchone()["c"]
        recent = conn.execute(
            "SELECT id, title, created_at FROM meetings ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
    return {
        "total_meetings": total,
        "recent": [dict(r) for r in recent],
    }


# ── 额外接口 ──────────────────────────────────────────────

@nervus._api.get("/meetings")
async def list_meetings(limit: int = 20):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, start_time, duration_sec, status, created_at FROM meetings ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return {"meetings": [dict(r) for r in rows]}


@nervus._api.get("/meetings/{meeting_id}")
async def get_meeting_detail(meeting_id: str):
    return await action_get_meeting(meeting_id=meeting_id)


if __name__ == "__main__":
    init_db()
    nervus.run(port=int(os.getenv("APP_PORT", "8002")))
