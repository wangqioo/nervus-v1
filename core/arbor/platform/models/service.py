from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from .schemas import ChatRequest, ChatResponse, ModelConfig, ModelInfo, ModelStatus

logger = logging.getLogger("nervus.platform.models")


class ModelService:
    def __init__(self, llm_url: str, models_config_path: str = "") -> None:
        self._llm_url = llm_url.rstrip("/")
        self._configs: dict[str, ModelConfig] = {}
        self._default_text = "qwen3.5"
        self._default_vision = "qwen3.5"
        self._load_config(models_config_path)

    # ── config loading ────────────────────────────────────────────────────────

    def _load_config(self, path: str) -> None:
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text())
        except Exception as exc:
            logger.warning("models config not loaded (%s): %s", path, exc)
            self._ensure_default_local()
            return

        self._default_text = data.get("default_text", "qwen3.5")
        self._default_vision = data.get("default_vision", "qwen3.5")

        for raw in data.get("models", []) + data.get("cloud", []):
            cfg = ModelConfig.model_validate(raw)
            self._configs[cfg.id] = cfg

        self._ensure_default_local()
        logger.info("models loaded: %s", list(self._configs.keys()))

    def _ensure_default_local(self) -> None:
        if "qwen3.5" not in self._configs:
            self._configs["qwen3.5"] = ModelConfig(
                id="qwen3.5",
                name="Qwen 3.5 4B（本地）",
                provider="llama.cpp",
                vision=True,
                context_length=4096,
                auto_extra={"chat_template_kwargs": {"enable_thinking": False}},
            )

    # ── public API ────────────────────────────────────────────────────────────

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                id=c.id,
                name=c.name,
                provider=c.provider,
                vision=c.vision,
                context_length=c.context_length,
            )
            for c in self._configs.values()
        ]

    async def check_status(self) -> list[ModelInfo]:
        results: list[ModelInfo] = []
        async with httpx.AsyncClient(timeout=3.0) as client:
            for cfg in self._configs.values():
                if cfg.provider == "llama.cpp":
                    status = await self._ping_local(client)
                else:
                    api_key = os.getenv(cfg.api_key_env, "") if cfg.api_key_env else ""
                    status = ModelStatus.online if api_key else ModelStatus.offline
                results.append(ModelInfo(
                    id=cfg.id,
                    name=cfg.name,
                    provider=cfg.provider,
                    vision=cfg.vision,
                    context_length=cfg.context_length,
                    status=status,
                ))
        return results

    async def _ping_local(self, client: httpx.AsyncClient) -> ModelStatus:
        try:
            resp = await client.get(f"{self._llm_url}/health")
            body = resp.json()
            if resp.status_code == 200 and body.get("status") in ("ok", "online"):
                return ModelStatus.online
        except Exception as exc:
            logger.debug("local model health check failed: %s", exc)
        return ModelStatus.offline

    async def chat(self, req: ChatRequest) -> ChatResponse:
        model_id = req.model or (
            self._default_vision if req.vision else self._default_text
        )
        cfg = self._configs.get(model_id) or self._configs.get(self._default_text)
        if cfg is None:
            return ChatResponse(model=model_id, content="", error="no model available")

        if cfg.provider == "llama.cpp":
            return await self._chat_local(req, cfg)
        else:
            return await self._chat_cloud(req, cfg)

    # ── provider implementations ──────────────────────────────────────────────

    async def _chat_local(self, req: ChatRequest, cfg: ModelConfig) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": cfg.id,
            "messages": [m.model_dump() for m in req.messages],
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "stream": False,
        }
        # merge model auto_extra first, then request extra (request wins)
        merged_extra = {**cfg.auto_extra, **req.extra}
        payload.update(merged_extra)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self._llm_url}/v1/chat/completions", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            return ChatResponse(model=cfg.id, provider=cfg.provider, content="",
                                error=f"llama.cpp {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            return ChatResponse(model=cfg.id, provider=cfg.provider, content="", error=str(exc))

        return _parse_openai_response(data, cfg)

    async def _chat_cloud(self, req: ChatRequest, cfg: ModelConfig) -> ChatResponse:
        api_key = os.getenv(cfg.api_key_env, "") if cfg.api_key_env else ""
        if not api_key:
            return ChatResponse(model=cfg.id, provider=cfg.provider, content="",
                                error=f"API key not set (env: {cfg.api_key_env})")

        endpoint = cfg.endpoint.rstrip("/")
        payload: dict[str, Any] = {
            "model": cfg.id,
            "messages": [m.model_dump() for m in req.messages],
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "stream": False,
            **cfg.auto_extra,
            **req.extra,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{endpoint}/v1/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            return ChatResponse(model=cfg.id, provider=cfg.provider, content="",
                                error=f"cloud {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            return ChatResponse(model=cfg.id, provider=cfg.provider, content="", error=str(exc))

        return _parse_openai_response(data, cfg)


def _parse_openai_response(data: dict, cfg: ModelConfig) -> ChatResponse:
    try:
        content = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {})
    except (KeyError, IndexError) as exc:
        return ChatResponse(model=cfg.id, provider=cfg.provider, content="",
                            error=f"unexpected response shape: {exc}")
    return ChatResponse(model=cfg.id, provider=cfg.provider, content=content, usage=usage)
