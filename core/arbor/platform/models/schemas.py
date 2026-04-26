from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ModelStatus(str, Enum):
    online = "online"
    offline = "offline"
    unknown = "unknown"


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str = "llama.cpp"
    vision: bool = False
    context_length: int = 4096
    status: ModelStatus = ModelStatus.unknown


class ModelConfig(BaseModel):
    id: str
    name: str
    provider: str = "llama.cpp"   # "llama.cpp" | "openai_compat"
    endpoint: str = ""            # cloud endpoint; empty = use llm_url
    api_key_env: str = ""         # env var name holding the API key
    vision: bool = False
    context_length: int = 4096
    auto_extra: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: str
    # str for text-only; list for multimodal (OpenAI image_url format)
    content: str | list[Any]


class ChatRequest(BaseModel):
    model: str = ""               # empty → platform picks default
    messages: list[ChatMessage]
    max_tokens: int = 512
    temperature: float = 0.7
    stream: bool = False
    vision: bool = False          # hint: route to default_vision model if model is empty
    extra: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    model: str
    content: str
    provider: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
