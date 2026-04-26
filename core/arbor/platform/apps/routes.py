from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from .schemas import RegisterAppRequest

router = APIRouter()


@router.get("")
async def list_apps(request: Request):
    apps = request.app.state.app_registry.list_apps()
    return {"count": len(apps), "apps": [app.model_dump(mode="json") for app in apps]}


@router.post("/register")
async def register_app(req: RegisterAppRequest, request: Request):
    app = await request.app.state.app_registry.register(req.manifest, req.endpoint_url)
    return {"status": "ok", "app": app.model_dump(mode="json")}


@router.get("/list")
async def list_apps_legacy(request: Request):
    apps = request.app.state.app_registry.list_apps()
    return {
        "count": len(apps),
        "apps": [
            {
                "app_id": app.id,
                "name": app.name,
                "version": app.version,
                "endpoint_url": app.endpoint_url,
                "status": app.status.value,
            }
            for app in apps
        ],
    }


@router.get("/{app_id}")
async def get_app(app_id: str, request: Request):
    app = request.app.state.app_registry.get_app(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail=f"App {app_id} is not registered")
    return app.model_dump(mode="json")


@router.get("/{app_id}/status")
async def get_app_status(app_id: str, request: Request):
    status = await request.app.state.app_registry.get_status(app_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"App {app_id} is not registered")
    return status.model_dump(mode="json")


@router.post("/{app_id}/heartbeat")
async def heartbeat(app_id: str, request: Request):
    ok = await request.app.state.app_registry.update_heartbeat(app_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"App {app_id} is not registered")
    return {"status": "ok", "app_id": app_id}
