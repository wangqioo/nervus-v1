from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from backend.models.file import FileSummary, FileListItem, SearchResult, StatsResponse, FileType, FileStatus
from backend.services import storage, analyzer
from backend.utils.config import MAX_FILE_SIZE

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    analyze_now: bool = Form(False),
):
    if file:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(413, f"文件超过大小限制 {MAX_FILE_SIZE // 1024 // 1024}MB")
        meta = storage.save_file(content, file.filename or "unknown", file.content_type or "")
    elif url:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(400, "请输入有效的链接地址")
        meta = storage.save_link(url)
    elif text:
        meta = storage.save_text(text.strip())
        return {"id": meta.id, "status": meta.status, "created_at": meta.created_at, "type": meta.type}
    else:
        raise HTTPException(400, "请上传文件或提供链接")

    if analyze_now:
        meta = await analyzer.analyze_file(meta)
    else:
        background_tasks.add_task(analyzer.analyze_file, meta)

    return {"id": meta.id, "status": meta.status, "created_at": meta.created_at, "type": meta.type}


@router.get("/events")
async def file_events():
    from backend.services.events import subscribe, stream
    q = subscribe()
    return StreamingResponse(
        stream(q),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("", response_model=list[FileListItem])
async def list_files(
    date: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    files = storage.get_all_files(date_filter=date, type_filter=type)
    items = files[offset: offset + limit]
    return [
        FileListItem(
            id=f.id,
            filename=f.filename,
            original_filename=f.original_filename,
            type=f.type,
            url=f.url,
            summary=f.summary,
            keywords=f.keywords,
            og_image=f.og_image,
            favicon_url=f.favicon_url,
            created_at=f.created_at,
            status=f.status,
        )
        for f in items
    ]


@router.get("/search")
async def search(q: str = Query(..., min_length=1), date: Optional[str] = Query(None), type: Optional[str] = Query(None)):
    all_files = storage.get_all_files(date_filter=date, type_filter=type)
    results = await analyzer.search_files(q, all_files)

    output = []
    for r in results:
        meta = storage.get_file_by_id(r["id"])
        if meta:
            output.append({
                "id": meta.id,
                "filename": meta.filename,
                "original_filename": meta.original_filename,
                "type": meta.type,
                "url": meta.url,
                "summary": meta.summary,
                "match_score": r.get("match_score", 0),
                "match_reason": r.get("match_reason", ""),
            })
    return {"results": output, "query": q}


@router.get("/by-date/{date}")
async def files_by_date(date: str):
    files = storage.get_all_files(date_filter=date)
    return [
        FileListItem(
            id=f.id, filename=f.filename, original_filename=f.original_filename,
            type=f.type, url=f.url, summary=f.summary, keywords=f.keywords,
            og_image=f.og_image, favicon_url=f.favicon_url,
            created_at=f.created_at, status=f.status,
        )
        for f in files
    ]


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    files = storage.get_all_files()
    by_type: dict = {}
    by_status: dict = {}
    for f in files:
        by_type[f.type.value] = by_type.get(f.type.value, 0) + 1
        by_status[f.status.value] = by_status.get(f.status.value, 0) + 1
    recent = files[0].date_str() if files else None
    return StatsResponse(total=len(files), by_type=by_type, by_status=by_status, recent_date=recent)


@router.get("/{file_id}", response_model=FileSummary)
async def get_file(file_id: str):
    meta = storage.get_file_by_id(file_id)
    if not meta:
        raise HTTPException(404, "文件不存在")
    return meta


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    ok = storage.delete_file(file_id)
    if not ok:
        raise HTTPException(404, "文件不存在")
    return {"message": "删除成功"}


@router.post("/{file_id}/analyze")
async def trigger_analyze(file_id: str):
    meta = storage.get_file_by_id(file_id)
    if not meta:
        raise HTTPException(404, "文件不存在")
    meta = await analyzer.analyze_file(meta)
    return {"id": meta.id, "status": meta.status, "summary": meta.summary}


@router.get("/{file_id}/extract")
async def extract_content(file_id: str):
    meta = storage.get_file_by_id(file_id)
    if not meta:
        raise HTTPException(404, "文件不存在")
    if meta.type.value != "link" or not meta.url:
        raise HTTPException(400, "仅支持链接类型")
    from backend.services.url_classifier import classify_url, extract_wechat_markdown
    if classify_url(meta.url) != "wechat":
        raise HTTPException(400, "仅支持微信公众号链接")
    result = await extract_wechat_markdown(meta.url)
    if "error" in result:
        raise HTTPException(502, result["error"])
    return result


@router.get("/{file_id}/download")
async def download_file(file_id: str):
    meta = storage.get_file_by_id(file_id)
    if not meta:
        raise HTTPException(404, "文件不存在")
    file_path = storage.get_file_absolute_path(meta)
    if not file_path or not file_path.exists():
        raise HTTPException(404, "文件已被删除")
    return FileResponse(
        str(file_path),
        filename=meta.original_filename,
        media_type=meta.mime_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=604800, immutable"},
    )
