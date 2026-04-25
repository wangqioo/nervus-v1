import base64
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from zhipuai import ZhipuAI

from backend.models.file import FileSummary, FileType, FileStatus
from backend.services.storage import get_file_absolute_path, save_meta
from backend.services.url_classifier import (
    classify_url, fetch_bilibili_summary, fetch_wechat_summary, fetch_generic_summary
)
from backend.utils.config import GLM_API_KEY, GLM_MODEL, GLM_VISION_MODEL


def _client() -> ZhipuAI:
    return ZhipuAI(api_key=GLM_API_KEY)


def _extract_json(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _extract_text_from_file(file_path: Path, file_type: FileType) -> str:
    text = ""
    try:
        if file_type == FileType.document:
            suffix = file_path.suffix.lower()
            if suffix == ".pdf":
                text = _extract_pdf(file_path)
            elif suffix in (".docx", ".doc"):
                text = _extract_docx(file_path)
            elif suffix in (".txt", ".md", ".csv"):
                text = file_path.read_text(encoding="utf-8", errors="ignore")[:3000]
    except Exception as e:
        text = f"文件读取失败: {e}"
    return text[:3000]


def _extract_pdf(file_path: Path) -> str:
    try:
        from pdfminer.high_level import extract_text
        return extract_text(str(file_path))
    except ImportError:
        pass
    try:
        import pypdf
        reader = pypdf.PdfReader(str(file_path))
        return "\n".join(p.extract_text() or "" for p in reader.pages[:10])
    except ImportError:
        pass
    return "PDF文本提取需要安装 pdfminer.six 或 pypdf"


def _extract_docx(file_path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(file_path))
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        return "Word文档提取需要安装 python-docx"


async def analyze_file(meta: FileSummary) -> FileSummary:
    try:
        if meta.type == FileType.link:
            result = await _analyze_link(meta.url)
        elif meta.type == FileType.image:
            result = _analyze_image(meta)
        elif meta.type == FileType.document:
            result = _analyze_document(meta)
        elif meta.type == FileType.video:
            result = _analyze_video(meta)
        elif meta.type == FileType.audio:
            result = _analyze_audio(meta)
        else:
            result = _analyze_other(meta)

        meta.summary = result.get("summary", "")
        meta.description = result.get("description", "")
        meta.keywords = result.get("keywords", [])
        meta.highlights = result.get("highlights", [])
        meta.og_image = result.get("og_image")
        meta.favicon_url = result.get("favicon_url")
        meta.status = FileStatus.ready
        meta.analyzed_at = datetime.now()
    except Exception as e:
        meta.status = FileStatus.failed
        meta.error = str(e)

    save_meta(meta)
    from backend.services.events import emit as _emit
    await _emit({
        "type": "file_updated",
        "id": meta.id,
        "status": meta.status.value,
        "summary": meta.summary or "",
        "og_image": meta.og_image,
        "favicon_url": meta.favicon_url,
    })
    return meta


def _analyze_image(meta: FileSummary) -> dict:
    file_path = get_file_absolute_path(meta)
    if not file_path or not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {meta.filename}")

    suffix = file_path.suffix.lower().lstrip(".")
    media_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                 "gif": "image/gif", "webp": "image/webp"}
    media_type = media_map.get(suffix, "image/jpeg")

    with open(file_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    client = _client()
    response = client.chat.completions.create(
        model=GLM_VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{image_data}"},
                },
                {
                    "type": "text",
                    "text": (
                        "请分析这张图片，生成JSON格式简介：\n"
                        "{\n"
                        '  "summary": "一句话描述（20字内）",\n'
                        '  "description": "详细描述（100字内）",\n'
                        '  "keywords": ["关键词1", "关键词2", "关键词3"]\n'
                        "}\n只输出JSON，不要其他内容。"
                    ),
                },
            ],
        }],
    )
    return _extract_json(response.choices[0].message.content)


def _analyze_document(meta: FileSummary) -> dict:
    file_path = get_file_absolute_path(meta)
    text = _extract_text_from_file(file_path, meta.type) if file_path else ""
    if not text:
        text = f"文件名：{meta.original_filename}"

    client = _client()
    response = client.chat.completions.create(
        model=GLM_MODEL,
        messages=[
            {"role": "system", "content": "你是一个文档分析助手，专注于提取核心信息并生成结构化简介。"},
            {
                "role": "user",
                "content": (
                    f"请分析以下文档内容，生成JSON格式简介：\n\n{text}\n\n"
                    "要求生成JSON格式：\n"
                    "{\n"
                    '  "summary": "一句话描述文档主题（20字内）",\n'
                    '  "description": "文档核心内容概述（100字内）",\n'
                    '  "keywords": ["关键词1", "关键词2", "关键词3"],\n'
                    '  "highlights": ["亮点1", "亮点2"]\n'
                    "}\n只输出JSON，不要其他内容。"
                ),
            },
        ],
    )
    return _extract_json(response.choices[0].message.content)


def _analyze_video(meta: FileSummary) -> dict:
    return {
        "summary": f"视频文件：{meta.original_filename}",
        "description": f"视频大小：{(meta.file_size or 0) // 1024 // 1024:.1f}MB，视频内容分析暂不支持本地视频",
        "keywords": ["视频"],
        "highlights": [],
    }


def _analyze_audio(meta: FileSummary) -> dict:
    return {
        "summary": f"音频文件：{meta.original_filename}",
        "description": f"音频文件，大小：{(meta.file_size or 0) // 1024:.0f}KB",
        "keywords": ["音频"],
        "highlights": [],
    }


def _analyze_other(meta: FileSummary) -> dict:
    client = _client()
    response = client.chat.completions.create(
        model=GLM_MODEL,
        messages=[{
            "role": "user",
            "content": (
                f"根据文件名生成简介，文件名：{meta.original_filename}\n"
                "生成JSON：\n"
                '{"summary": "一句话简介", "description": "描述", "keywords": ["词1"], "highlights": []}\n'
                "只输出JSON。"
            ),
        }],
    )
    return _extract_json(response.choices[0].message.content)


async def _analyze_link(url: str) -> dict:
    link_type = classify_url(url)
    if link_type == "wechat":
        return await fetch_wechat_summary(url)
    elif link_type == "bilibili":
        return await fetch_bilibili_summary(url)
    else:
        return await fetch_generic_summary(url)


async def search_files(query: str, files: list[FileSummary]) -> list[dict]:
    if not files:
        return []

    file_list_text = "\n".join(
        f"- ID:{f.id} 文件名:{f.original_filename} 类型:{f.type.value} 简介:{f.summary or '无'} 关键词:{','.join(f.keywords)}"
        for f in files if f.status == FileStatus.ready
    )

    if not file_list_text:
        return []

    client = _client()
    response = client.chat.completions.create(
        model=GLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个严格的文件搜索助手。"
                    "只返回与搜索词有明确、直接关联的文件——文件的摘要或关键词中必须有清晰的证据。"
                    "如果某文件仅是模糊相关或你无法确定，不要包含它。"
                    "宁可少返回，不可滥返回。没有确信相关的文件时返回空数组。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"文件列表：\n{file_list_text}\n\n"
                    f"搜索词：{query}\n\n"
                    "规则：\n"
                    "1. 只返回摘要/关键词中有直接证据的文件\n"
                    "2. match_score 代表确信度（0~1），低于 0.6 的不要返回\n"
                    "3. match_reason 引用文件摘要/关键词中的具体内容说明为何匹配\n"
                    "4. 最多返回5个，没有匹配则 results 为空数组\n\n"
                    "返回JSON（只输出JSON）：\n"
                    '{"results": [{"id": "文件id", "match_score": 0.85, "match_reason": "摘要中提到..."}]}'
                ),
            },
        ],
    )
    data = _extract_json(response.choices[0].message.content)
    results = data.get("results", [])
    def _score(r):
        try:
            return float(r.get("match_score") or 0)
        except (TypeError, ValueError):
            return 0.0
    return [r for r in results if _score(r) >= 0.6]
