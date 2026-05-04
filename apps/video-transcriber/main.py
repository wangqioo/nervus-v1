"""
Video Transcriber App — 视频转录器
提取视频音轨并调用云端 ASR 转写，发布到知识总线
支持：mp4, mkv, mov, avi, webm
"""

import os
import subprocess
import tempfile
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

import sys
sys.path.insert(0, "/app/nervus-sdk")
from nervus_sdk import NervusApp, emit
from nervus_sdk.models import Event

nervus = NervusApp("video-transcriber")

DB_PATH = os.getenv("DB_PATH", "/data/video-transcriber.db")

SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}

# ── 数据库初始化 ──────────────────────────────────────────


def get_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS transcriptions (
                id              TEXT PRIMARY KEY,
                video_path      TEXT,
                title           TEXT,
                transcript      TEXT,
                language        TEXT,
                duration_sec    REAL DEFAULT 0,
                status          TEXT DEFAULT 'pending',
                error           TEXT,
                created_at      TEXT NOT NULL,
                completed_at    TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_trans_created ON transcriptions(created_at DESC);
        """)


init_db()


# ── 工具函数 ──────────────────────────────────────────────

def _make_id() -> str:
    import uuid
    return str(uuid.uuid4())


def _guess_title(video_path: str) -> str:
    return Path(video_path).stem.replace("_", " ").replace("-", " ").strip()


async def _extract_audio(video_path: str, tmp_dir: str) -> str:
    """用 ffmpeg 从视频中提取 16kHz 单声道 WAV"""
    audio_path = os.path.join(tmp_dir, "audio.wav")
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn",                   # 不要视频流
        "-acodec", "pcm_s16le",  # PCM 16-bit
        "-ar", "16000",          # 16kHz（ASR 标准采样率）
        "-ac", "1",              # 单声道
        "-y", audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 音频提取失败: {result.stderr[:500]}")
    return audio_path


async def _get_video_duration(video_path: str) -> float:
    """用 ffprobe 获取视频时长（秒）"""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


async def _transcribe_with_cloud_asr(audio_path: str) -> tuple[str, str]:
    """
    调用云端 ASR 转写音频，返回 (transcript, language)。
    TODO: 集成讯飞云端 ASR，参考 nervus-cli/voice.py 中的 _XunfeiSTT 实现。
    """
    # TODO: 读取 audio_path，调用讯飞 WebSocket ASR，返回 (转写文本, "zh")
    return ("[ASR 待集成]", "zh")


async def _transcribe_video(job_id: str, video_path: str, title: Optional[str]) -> dict:
    """完整的视频转录流程"""
    now = datetime.utcnow().isoformat()
    tmp_dir = tempfile.mkdtemp()

    try:
        # 获取视频时长
        duration = await _get_video_duration(video_path)

        # 提取音轨
        audio_path = await _extract_audio(video_path, tmp_dir)

        # 调用云端 ASR
        transcript, language = await _transcribe_with_cloud_asr(audio_path)

        detected_title = title or _guess_title(video_path)
        completed_at = datetime.utcnow().isoformat()

        with get_db() as conn:
            conn.execute(
                """UPDATE transcriptions
                   SET title=?, transcript=?, language=?, duration_sec=?,
                       status='done', completed_at=?
                   WHERE id=?""",
                (detected_title, transcript, language, duration, completed_at, job_id)
            )

        # 发布到知识总线
        await emit("knowledge.video.transcribed", {
            "job_id": job_id,
            "video_path": video_path,
            "title": detected_title,
            "transcript": transcript[:8000],
            "full_length": len(transcript),
            "language": language,
            "duration_sec": duration,
            "created_at": now,
        })

        return {
            "job_id": job_id,
            "title": detected_title,
            "language": language,
            "duration_sec": duration,
            "transcript_length": len(transcript),
            "status": "done",
        }

    except Exception as e:
        with get_db() as conn:
            conn.execute(
                "UPDATE transcriptions SET status='error', error=? WHERE id=?",
                (str(e), job_id)
            )
        return {"job_id": job_id, "status": "error", "error": str(e)}

    finally:
        # 清理临时文件
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Actions ───────────────────────────────────────────────

@nervus.action("transcribe_video")
async def action_transcribe_video(payload: dict) -> dict:
    """转写视频文件"""
    video_path = payload.get("video_path", "").strip()
    title = payload.get("title")

    if not video_path:
        return {"error": "video_path 不能为空"}

    ext = Path(video_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return {"error": f"不支持的视频格式: {ext}，支持: {', '.join(SUPPORTED_EXTENSIONS)}"}

    if not os.path.exists(video_path):
        return {"error": f"视频文件不存在: {video_path}"}

    job_id = _make_id()
    now = datetime.utcnow().isoformat()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO transcriptions (id, video_path, status, created_at) VALUES (?,?,'processing',?)",
            (job_id, video_path, now)
        )

    import asyncio
    asyncio.create_task(_transcribe_video(job_id, video_path, title))

    return {"job_id": job_id, "status": "processing", "message": "转录任务已提交，请轮询 /jobs/{job_id} 查看进度"}


@nervus.action("get_transcript")
async def action_get_transcript(payload: dict) -> dict:
    job_id = payload.get("job_id")
    with get_db() as conn:
        row = conn.execute("SELECT * FROM transcriptions WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return {"error": "任务不存在"}
    return dict(row)


# ── REST API ──────────────────────────────────────────────

@nervus._api.post("/transcribe")
async def transcribe_api(body: dict):
    """提交视频转录任务"""
    return await action_transcribe_video(body)


@nervus._api.get("/jobs")
async def list_jobs(limit: int = 20):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, video_path, title, language, duration_sec, status, created_at, completed_at "
            "FROM transcriptions ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return {"jobs": [dict(r) for r in rows]}


@nervus._api.get("/jobs/{job_id}")
async def get_job(job_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM transcriptions WHERE id = ?", (job_id,)).fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="任务不存在")
    return dict(row)


@nervus._api.get("/jobs/{job_id}/transcript")
async def get_transcript_api(job_id: str):
    """仅返回转录文本"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT transcript, status FROM transcriptions WHERE id = ?", (job_id,)
        ).fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="任务不存在")
    if row["status"] != "done":
        return {"status": row["status"], "transcript": None}
    return {"status": "done", "transcript": row["transcript"]}


@nervus.state
async def get_state():
    with get_db() as conn:
        stats = conn.execute(
            "SELECT status, COUNT(*) as c FROM transcriptions GROUP BY status"
        ).fetchall()
    return {"jobs": {r["status"]: r["c"] for r in stats}}


if __name__ == "__main__":
    nervus.run(port=int(os.getenv("APP_PORT", "8008")))
