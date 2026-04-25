from fastapi import FastAPI, Query as QParam
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pathlib import Path

import httpx

from backend.routers import files
from backend.utils.config import CORS_ORIGINS

_WX_IMG_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "MicroMessenger/8.0.43 NetType/WIFI Language/zh_CN"
)

app = FastAPI(title="文件传输助手", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/image-proxy")
async def image_proxy(url: str = QParam(...)):
    """Proxy WeChat CDN images to bypass hotlink protection."""
    is_wechat = any(k in url for k in ("qpic.cn", "mmbiz", "weixin"))
    headers = {"Referer": "https://mp.weixin.qq.com/"}
    if is_wechat:
        headers["User-Agent"] = _WX_IMG_UA
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
        content_type = r.headers.get("content-type", "image/jpeg")
        return Response(content=r.content, media_type=content_type)
    except Exception:
        raise

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index = FRONTEND_DIST / "index.html"
        return FileResponse(str(index))
