"""
LLM Client — llama.cpp server 封装
兼容 OpenAI API 格式
文字理解 + 视觉识别用同一接口
"""

from __future__ import annotations
import base64
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("nervus.llm")


class LLMClient:
    """
    封装对 llama.cpp server 的调用。
    支持文字对话和视觉分析（同一个 Qwen3.5-4B 多模态模型）。

    用法：
        client = LLMClient("http://llama-cpp:8080")
        text = await client.chat("今天天气怎么样？")
        result = await client.vision("/path/to/image.jpg", "识别食物并估算热量")
    """

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def chat(
        self,
        prompt: str,
        system: str = "你是 Nervus 的 AI 助手，运行在边缘设备上，简洁准确地回答问题。",
        temperature: float = 0.3,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> str:
        """文字对话，返回模型回复文本"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": "qwen3.5",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        response = await self._client.post(
            f"{self.base_url}/v1/chat/completions",
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def chat_json(
        self,
        prompt: str,
        system: str = "你是 Nervus 的 AI 助手。请以 JSON 格式返回结果。",
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> dict:
        """文字对话，返回解析后的 JSON 对象"""
        import json
        text = await self.chat(
            prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON
            import re
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"模型返回的不是有效 JSON: {text[:200]}")

    async def vision(
        self,
        image_path: str | Path,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        """
        视觉分析，返回模型对图片的描述/分析。
        image_path: 本地文件路径或 http(s) URL
        """
        # 准备图片内容
        if str(image_path).startswith(("http://", "https://")):
            image_content = {"type": "image_url", "image_url": {"url": str(image_path)}}
        else:
            # 本地文件转 base64
            path = Path(image_path)
            suffix = path.suffix.lower()
            mime_map = {
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".webp": "image/webp",
                ".gif": "image/gif",
            }
            mime = mime_map.get(suffix, "image/jpeg")
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            image_content = {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"}
            }

        messages = [{
            "role": "user",
            "content": [
                image_content,
                {"type": "text", "text": prompt},
            ]
        }]

        body = {
            "model": "qwen3.5",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }

        response = await self._client.post(
            f"{self.base_url}/v1/chat/completions",
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def vision_json(
        self,
        image_path: str | Path,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 512,
    ) -> dict:
        """视觉分析，返回解析后的 JSON 对象"""
        import json, re
        # 在 prompt 中明确要求 JSON 格式
        json_prompt = f"{prompt}\n\n请以 JSON 格式返回结果。"
        text = await self.vision(image_path, json_prompt, temperature, max_tokens)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"模型返回的不是有效 JSON: {text[:200]}")

    async def embed(self, text: str) -> list[float]:
        """生成文本向量嵌入（用于 Memory Graph 语义检索）"""
        response = await self._client.post(
            f"{self.base_url}/v1/embeddings",
            json={"model": "qwen3.5", "input": text},
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]

    async def close(self) -> None:
        await self._client.aclose()
