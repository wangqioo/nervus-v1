"""
知识库 App — 私人知识大脑
统一收录所有知识来源，向量化，语义检索，AI 问答
"""

import json
import os
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, "/app/nervus-sdk")
from nervus_sdk import NervusApp, Context, emit
from nervus_sdk.models import Event, Manifest
from nervus_sdk.memory import MemoryGraph

nervus = NervusApp("knowledge-base")
with open(Path(__file__).parent / "manifest.json") as f:
    nervus.set_manifest(Manifest(**json.load(f)))


# ── 核心逻辑 ──────────────────────────────────────────────

async def store_item(
    type: str,
    title: str,
    content: str = "",
    summary: str = "",
    source_url: str = "",
    tags: list = None,
    source_app: str = "knowledge-base",
) -> str:
    """向量化并存入 Memory Graph"""
    # 生成 embedding（用标题+摘要拼接，节省 token）
    embed_text = f"{title}\n{summary or content[:500]}"
    try:
        embedding = await nervus.llm.embed(embed_text)
    except Exception:
        embedding = None

    item_id = await MemoryGraph.write_knowledge_item(
        type=type,
        title=title,
        content=content,
        summary=summary,
        source_url=source_url,
        tags=tags or [],
        timestamp=datetime.utcnow(),
        source_app=source_app,
        embedding=embedding,
    )
    return item_id


async def generate_summary(content: str, type: str = "article") -> str:
    """用云端 LLM 生成内容摘要"""
    if len(content) < 200:
        return content

    type_hints = {
        "article": "文章",
        "pdf": "PDF文档",
        "meeting": "会议纪要",
        "video": "视频字幕",
        "note": "笔记",
    }
    type_name = type_hints.get(type, "内容")

    prompt = f"""请为以下{type_name}生成一段简洁的摘要（100-200字）：

{content[:2000]}

直接返回摘要文字，不需要标题或前缀。"""

    try:
        return await nervus.llm.chat(prompt, temperature=0.3, max_tokens=300)
    except Exception:
        return content[:200] + "..."


# ── 事件处理 ──────────────────────────────────────────────

@nervus.on("knowledge.document.indexed")
async def handle_document(event: Event):
    payload = event.payload
    title = payload.get("title", "未命名文档")
    content = payload.get("content", "")
    summary = payload.get("summary") or await generate_summary(content, "pdf")
    item_id = await store_item(
        type="pdf", title=title, content=content, summary=summary,
        source_url=payload.get("source_url", ""), source_app=payload.get("source_app", ""),
    )
    return {"item_id": item_id}


@nervus.on("knowledge.article.fetched")
async def handle_article(event: Event):
    payload = event.payload
    content = payload.get("content", "")
    summary = await generate_summary(content, "article")
    item_id = await store_item(
        type="article", title=payload.get("title", ""),
        content=content, summary=summary,
        source_url=payload.get("url", ""),
        tags=payload.get("tags", []),
        source_app="rss-reader",
    )
    return {"item_id": item_id}


@nervus.on("knowledge.note.created")
async def handle_note(event: Event):
    payload = event.payload
    item_id = await store_item(
        type="note", title=payload.get("title", "笔记"),
        content=payload.get("content", ""), source_app="personal-notes",
    )
    return {"item_id": item_id}


@nervus.on("knowledge.video.transcribed")
async def handle_video(event: Event):
    payload = event.payload
    transcript = payload.get("transcript", "")
    summary = await generate_summary(transcript, "video")
    item_id = await store_item(
        type="video", title=payload.get("title", "视频"),
        content=transcript, summary=summary,
        source_url=payload.get("source_url", ""),
        source_app="video-transcriber",
    )
    return {"item_id": item_id}


@nervus.on("meeting.recording.processed")
async def handle_meeting(event: Event):
    payload = event.payload
    summary_obj = payload.get("summary", {})
    summary_text = summary_obj.get("overview", "") if isinstance(summary_obj, dict) else str(summary_obj)
    item_id = await store_item(
        type="meeting", title=payload.get("title", "会议纪要"),
        content=payload.get("transcript", ""), summary=summary_text,
        tags=summary_obj.get("keywords", []) if isinstance(summary_obj, dict) else [],
        source_app="meeting-notes",
    )
    return {"item_id": item_id}


# ── Actions ───────────────────────────────────────────────

@nervus.action("embed_and_store")
async def action_embed_store(type: str = "article", title: str = "", content: str = "",
                              source_url: str = "", item_id: str = ""):
    summary = await generate_summary(content, type)
    stored_id = await store_item(type=type, title=title, content=content, summary=summary, source_url=source_url)
    return {"item_id": stored_id}


@nervus.action("semantic_search")
async def action_semantic_search(query: str = "", limit: int = 10, type_filter: str = ""):
    try:
        query_embedding = await nervus.llm.embed(query)
        results = await MemoryGraph.semantic_search(
            query_embedding=query_embedding,
            table="knowledge_items",
            limit=limit,
            type_filter=type_filter or None,
        )
        return {"results": results, "query": query}
    except Exception as e:
        return {"results": [], "error": str(e)}


@nervus.action("ask")
async def action_ask(question: str = ""):
    """基于知识库语义检索回答问题"""
    # 1. 语义检索相关内容
    search_result = await action_semantic_search(query=question, limit=5)
    context_items = search_result.get("results", [])

    if not context_items:
        return {"answer": "知识库中暂无相关内容。", "sources": []}

    # 2. 构建上下文
    context_text = "\n\n".join([
        f"[{item.get('type', '')}] {item.get('title', '')}\n{item.get('description', '')}"
        for item in context_items[:3]
    ])

    # 3. 生成回答
    prompt = f"""根据以下知识库内容回答问题。

知识库内容：
{context_text}

问题：{question}

请基于上面的内容给出准确的回答，如果内容不足以回答，请如实说明。"""

    try:
        answer = await nervus.llm.chat(prompt, temperature=0.3, max_tokens=512)
    except Exception as e:
        answer = f"生成回答失败: {e}"

    sources = [{"title": item.get("title"), "type": item.get("type"), "similarity": item.get("similarity")}
               for item in context_items]

    return {"answer": answer, "sources": sources}


@nervus.action("index_meeting")
async def action_index_meeting(meeting_id: str = "", transcript: str = "", summary: dict = None):
    summary_text = summary.get("overview", "") if summary else ""
    keywords = summary.get("keywords", []) if summary else []
    title = summary.get("title", "会议纪要") if summary else "会议纪要"
    item_id = await store_item(
        type="meeting", title=title, content=transcript, summary=summary_text,
        tags=keywords, source_app="meeting-notes",
    )
    return {"item_id": item_id}


@nervus.state
async def get_state():
    try:
        recent = await MemoryGraph.query_recent(table="knowledge_items", limit=5)
        return {"recent_items": len(recent), "status": "online"}
    except Exception:
        return {"status": "online"}


# ── REST API ──────────────────────────────────────────────

@nervus._api.post("/search")
async def search(body: dict):
    return await action_semantic_search(
        query=body.get("query", ""),
        limit=body.get("limit", 10),
        type_filter=body.get("type", ""),
    )


@nervus._api.post("/ask")
async def ask(body: dict):
    return await action_ask(question=body.get("question", ""))


@nervus._api.get("/recent")
async def recent_items(limit: int = 20, type_filter: str = ""):
    items = await MemoryGraph.query_recent(
        table="knowledge_items",
        type_filter=type_filter or None,
        limit=limit,
    )
    return {"items": items}


if __name__ == "__main__":
    nervus.run(port=int(os.getenv("APP_PORT", "8003")))
