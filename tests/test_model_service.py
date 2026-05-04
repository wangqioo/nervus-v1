"""
ModelService 独立测试脚本
无需启动完整 Arbor，直接测试 ModelService 逻辑

用法（需要对应云端 API Key）：

  # 测试云端模型（OpenAI compat）
  DEEPSEEK_API_KEY=sk-xxx python tests/test_model_service.py cloud deepseek-chat

  # 测试 Anthropic
  ANTHROPIC_API_KEY=sk-ant-xxx python tests/test_model_service.py anthropic claude-sonnet-4-6

  # 查看所有模型状态
  python tests/test_model_service.py status

  # 只测试 models.json 加载，无需网络
  python tests/test_model_service.py config
"""

from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# 加入 core/arbor 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "core" / "arbor"))

MODELS_CONFIG = str(Path(__file__).parent.parent / "config" / "models.json")


async def test_cloud(model_id: str):
    print(f"\n[云端模型] model_id={model_id}")
    with patch("infra.redis_client.get", new=AsyncMock(return_value=None)):
        from nervus_platform.models.service import ModelService
        from nervus_platform.models.schemas import ChatRequest, ChatMessage
        svc = ModelService("", MODELS_CONFIG)
        req = ChatRequest(
            model=model_id,
            messages=[ChatMessage(role="user", content="用一句话介绍你自己")],
            max_tokens=64,
            temperature=0.3,
        )
        result = await svc.chat(req)
    if result.error:
        print(f"  FAIL: {result.error}")
    else:
        print(f"  OK: {result.content[:100]}")
        print(f"  provider={result.provider}, model={result.model}")


async def test_anthropic(model_id: str = "claude-sonnet-4-6"):
    print(f"\n[Anthropic] model_id={model_id}")
    with patch("infra.redis_client.get", new=AsyncMock(return_value=None)):
        from nervus_platform.models.service import ModelService
        from nervus_platform.models.schemas import ChatRequest, ChatMessage
        svc = ModelService("", MODELS_CONFIG)
        req = ChatRequest(
            model=model_id,
            messages=[
                ChatMessage(role="system", content="你是一个简洁的助手"),
                ChatMessage(role="user", content="用一句话介绍你自己"),
            ],
            max_tokens=64,
            temperature=0.3,
        )
        result = await svc.chat(req)
    if result.error:
        print(f"  FAIL: {result.error}")
    else:
        print(f"  OK: {result.content[:100]}")
        print(f"  provider={result.provider}, model={result.model}")


async def test_status():
    print("\n[模型状态]")
    with patch("infra.redis_client.get", new=AsyncMock(return_value=None)):
        from nervus_platform.models.service import ModelService
        svc = ModelService("", MODELS_CONFIG)
        models = await svc.check_status()
    for m in models:
        print(f"  {m.id:30s}  provider={m.provider:15s}  status={m.status}")


async def test_config():
    """不需要任何网络，只测试 models.json 加载是否正确"""
    print("\n[配置加载测试]")
    with patch("infra.redis_client.get", new=AsyncMock(return_value=None)):
        from nervus_platform.models.service import ModelService
        svc = ModelService("", MODELS_CONFIG)
    models = svc.list_models()
    print(f"  加载 {len(models)} 个模型:")
    for m in models:
        print(f"  {m.id:30s}  provider={m.provider}")
    print(f"  default_text={svc._default_text}")
    print(f"  default_vision={svc._default_vision}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "config"

    if cmd == "config":
        asyncio.run(test_config())
    elif cmd == "cloud":
        model_id = sys.argv[2] if len(sys.argv) > 2 else "deepseek-chat"
        asyncio.run(test_cloud(model_id))
    elif cmd == "anthropic":
        model_id = sys.argv[2] if len(sys.argv) > 2 else "claude-sonnet-4-6"
        asyncio.run(test_anthropic(model_id))
    elif cmd == "status":
        asyncio.run(test_status())
    else:
        print("用法: python tests/test_model_service.py [config|cloud|anthropic|status]")
        print()
        print("  config     — 只测试 models.json 加载，无需网络")
        print("  cloud      — 测试云端 OpenAI-compat（需对应 API Key 环境变量）")
        print("  anthropic  — 测试 Anthropic Claude（需 ANTHROPIC_API_KEY）")
        print("  status     — 检测所有模型连通性")
