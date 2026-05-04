"""
PDF Extractor App — PDF 提取器
解析 PDF 文件，提取文字内容，发布到知识总线
支持：本地文件路径、base64 上传
"""

import os
import base64
import tempfile
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, "/app/nervus-sdk")
from nervus_sdk import NervusApp, emit
from nervus_sdk.models import Event

nervus = NervusApp("pdf-extractor")

# ── 数据库初始化 ──────────────────────────────────────────

DB_PATH = os.getenv("DB_PATH", "/data/pdf-extractor.db")


def get_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id          TEXT PRIMARY KEY,
                file_path   TEXT,
                title       TEXT,
                content     TEXT,
                page_count  INTEGER DEFAULT 0,
                file_size   INTEGER DEFAULT 0,
                status      TEXT DEFAULT 'pending',
                error       TEXT,
                created_at  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_docs_created ON documents(created_at DESC);
        """)


init_db()


# ── PDF 提取核心逻辑 ──────────────────────────────────────

def _make_id() -> str:
    import uuid
    return str(uuid.uuid4())


async def _extract_text_from_pdf(file_path: str) -> tuple[str, int]:
    """
    使用 pypdf 提取 PDF 文本内容。
    返回 (content, page_count)
    """
    try:
        import pypdf
    except ImportError:
        # 如果没有 pypdf，尝试 PyPDF2
        try:
            import PyPDF2 as pypdf
        except ImportError:
            raise RuntimeError("未安装 PDF 解析库，请安装 pypdf: pip install pypdf")

    reader = pypdf.PdfReader(file_path)
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[第 {i+1} 页]\n{text.strip()}")
        except Exception:
            pass

    return "\n\n".join(pages), len(reader.pages)


def _guess_title_from_path(file_path: str) -> str:
    """从文件路径推断标题"""
    stem = Path(file_path).stem
    # 去掉常见后缀和下划线
    return stem.replace("_", " ").replace("-", " ").strip()


async def _extract_and_store(doc_id: str, file_path: str, title: Optional[str] = None) -> dict:
    """提取 PDF 并写入数据库，发布总线事件"""
    now = datetime.utcnow().isoformat()

    try:
        content, page_count = await _extract_text_from_pdf(file_path)
        file_size = os.path.getsize(file_path)
        detected_title = title or _guess_title_from_path(file_path)

        with get_db() as conn:
            conn.execute(
                """UPDATE documents SET title=?, content=?, page_count=?, file_size=?, status='done'
                   WHERE id=?""",
                (detected_title, content, page_count, file_size, doc_id)
            )

        # 发布到知识总线
        await emit("knowledge.document.indexed", {
            "doc_id": doc_id,
            "title": detected_title,
            "content": content[:8000],  # 前 8000 字符，供 knowledge-base 向量化
            "full_length": len(content),
            "page_count": page_count,
            "source": "pdf",
            "created_at": now,
        })

        return {
            "doc_id": doc_id,
            "title": detected_title,
            "page_count": page_count,
            "content_length": len(content),
            "status": "done",
        }

    except Exception as e:
        with get_db() as conn:
            conn.execute(
                "UPDATE documents SET status='error', error=? WHERE id=?",
                (str(e), doc_id)
            )
        return {"doc_id": doc_id, "status": "error", "error": str(e)}


# ── Actions ───────────────────────────────────────────────

@nervus.action("extract_pdf")
async def action_extract_pdf(payload: dict) -> dict:
    """提取 PDF 文件内容"""
    file_path = payload.get("file_path", "").strip()
    title = payload.get("title")

    if not file_path:
        return {"error": "file_path 不能为空"}
    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}

    doc_id = _make_id()
    now = datetime.utcnow().isoformat()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO documents (id, file_path, status, created_at) VALUES (?,?,'processing',?)",
            (doc_id, file_path, now)
        )

    return await _extract_and_store(doc_id, file_path, title)


@nervus.action("get_document")
async def action_get_document(payload: dict) -> dict:
    doc_id = payload.get("doc_id")
    with get_db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        return {"error": "文档不存在"}
    return dict(row)


# ── REST API ──────────────────────────────────────────────

@nervus._api.post("/extract")
async def extract_api(body: dict):
    """
    提取 PDF。接受两种形式：
    - { "file_path": "/path/to/file.pdf" }
    - { "base64": "<base64编码>", "filename": "doc.pdf" }
    """
    if "base64" in body:
        # base64 上传：先写临时文件再提取
        b64_data = body["base64"]
        filename = body.get("filename", "upload.pdf")
        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, filename)
        with open(tmp_path, "wb") as f:
            f.write(base64.b64decode(b64_data))
        body["file_path"] = tmp_path

    return await action_extract_pdf(body)


@nervus._api.post("/upload")
async def upload_pdf():
    """通过 multipart 上传 PDF（HTTP 客户端上传）"""
    from fastapi import Request, UploadFile, File
    # 注：实际 multipart 处理需要在路由签名中声明 UploadFile
    return {"error": "请使用 /extract 接口，提供 base64 字段"}


@nervus._api.get("/documents")
async def list_documents(limit: int = 20):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, file_path, title, page_count, file_size, status, created_at FROM documents ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return {"documents": [dict(r) for r in rows]}


@nervus._api.get("/documents/{doc_id}")
async def get_document_api(doc_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="文档不存在")
    return dict(row)


@nervus._api.get("/documents/{doc_id}/content")
async def get_document_content(doc_id: str, page: int = 0):
    """分页获取文档内容（每页约 2000 字）"""
    PAGE_SIZE = 2000
    with get_db() as conn:
        row = conn.execute("SELECT content FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row or not row["content"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="文档不存在或内容为空")
    content = row["content"]
    total_pages = (len(content) + PAGE_SIZE - 1) // PAGE_SIZE
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    return {
        "doc_id": doc_id,
        "page": page,
        "total_pages": total_pages,
        "content": content[start:end],
    }


@nervus.state
async def get_state():
    with get_db() as conn:
        stats = conn.execute(
            "SELECT status, COUNT(*) as c FROM documents GROUP BY status"
        ).fetchall()
    return {"documents": {r["status"]: r["c"] for r in stats}}


if __name__ == "__main__":
    nervus.run(port=int(os.getenv("APP_PORT", "8007")))
