from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .schemas import ChatRequest

router = APIRouter()


@router.get("")
async def list_models(request: Request):
    svc = request.app.state.model_service
    models = svc.list_models()
    return {"count": len(models), "models": [m.model_dump() for m in models]}


@router.get("/defaults")
async def model_defaults(request: Request):
    svc = request.app.state.model_service
    return {
        "default_text": svc._default_text,
        "default_vision": svc._default_vision,
    }


@router.get("/status")
async def models_status(request: Request):
    models = await request.app.state.model_service.check_status()
    return {"models": [m.model_dump() for m in models]}


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    result = await request.app.state.model_service.chat(req)
    if result.error:
        raise HTTPException(status_code=502, detail=result.error)
    return result.model_dump()
