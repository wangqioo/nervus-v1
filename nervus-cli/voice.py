"""讯飞实时语音识别 — WebSocket API"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import struct
import time
from datetime import datetime
from typing import Callable
from urllib.parse import urlencode, urlunparse

import pyaudio
import websockets

import config

logger = logging.getLogger("nervus.cli.voice")

# 讯飞实时语音识别 WebSocket 地址
XUNFEI_WSS = "wss://iat-api.xfyun.cn/v2/iat"

# 音频参数
CHUNK     = 1280    # 每帧字节数（16kHz 16bit mono，40ms）
FORMAT    = pyaudio.paInt16
CHANNELS  = 1
RATE      = 16000
MAX_SECS  = 60      # 最长录音时间


def _build_auth_url() -> str:
    """生成带鉴权的 WebSocket URL"""
    now = datetime.utcnow()
    date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    host = "iat-api.xfyun.cn"
    path = "/v2/iat"

    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature = base64.b64encode(
        hmac.new(
            config.XUNFEI_SECRET.encode(),
            signature_origin.encode(),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode()

    auth = base64.b64encode(
        f'api_key="{config.XUNFEI_API_KEY}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'.encode()
    ).decode()

    params = urlencode({"authorization": auth, "date": date, "host": host})
    return f"{XUNFEI_WSS}?{params}"


def _frame_params(is_first: bool, is_last: bool, audio_b64: str) -> dict:
    """构造讯飞帧格式"""
    frame: dict = {"data": {"status": 1, "format": "audio/L16;rate=16000",
                             "encoding": "raw", "audio": audio_b64}}
    if is_first:
        frame["common"] = {"app_id": config.XUNFEI_APP_ID}
        frame["business"] = {
            "language": "zh_cn", "domain": "iat",
            "accent": "mandarin", "dwa": "wpgs",  # 动态修正
            "pd": "game", "ptt": 0,
        }
        frame["data"]["status"] = 0
    if is_last:
        frame["data"]["status"] = 2
    return frame


class VoiceRecorder:
    """
    按住说话录音 + 讯飞实时 ASR。
    用法：
        async for text in recorder.listen():
            print(text)   # 中间结果
    最终结果在 listen() 返回后通过 result 属性取得。
    """

    def __init__(self):
        self.result = ""
        self._recording = False
        self._pa: pyaudio.PyAudio | None = None
        self._stream = None

    def start(self):
        self._recording = True
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=FORMAT, channels=CHANNELS,
            rate=RATE, input=True,
            frames_per_buffer=CHUNK,
        )

    def stop(self):
        self._recording = False

    def _cleanup(self):
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pa:
            self._pa.terminate()
            self._pa = None

    async def listen(self, on_partial: Callable[[str], None] | None = None) -> str:
        """
        开始录音并实时返回 ASR 结果。
        录音结束（调用 stop() 或超时）后返回最终识别文本。
        """
        if not config.XUNFEI_APP_ID:
            # 没有配置讯飞，返回模拟结果（开发调试用）
            await asyncio.sleep(0.5)
            return "[未配置讯飞 ASR，请设置 XUNFEI_APP_ID]"

        url = _build_auth_url()
        self.result = ""
        frames: list[bytes] = []

        # 读取音频帧（在线程池里，不阻塞事件循环）
        loop = asyncio.get_event_loop()

        async def _read_audio():
            start = time.time()
            while self._recording and time.time() - start < MAX_SECS:
                data = await loop.run_in_executor(
                    None, self._stream.read, CHUNK, False
                )
                frames.append(data)
                await asyncio.sleep(0)

        read_task = asyncio.ensure_future(_read_audio())

        try:
            async with websockets.connect(url) as ws:
                send_idx = 0

                async def _send_loop():
                    nonlocal send_idx
                    while self._recording or send_idx < len(frames):
                        if send_idx < len(frames):
                            chunk = frames[send_idx]
                            b64 = base64.b64encode(chunk).decode()
                            is_first = send_idx == 0
                            is_last  = not self._recording and send_idx == len(frames) - 1
                            await ws.send(json.dumps(_frame_params(is_first, is_last, b64)))
                            send_idx += 1
                        else:
                            await asyncio.sleep(0.04)

                send_task = asyncio.ensure_future(_send_loop())

                # 接收 ASR 结果
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("code") != 0:
                        logger.warning("讯飞 ASR 错误: %s", msg.get("message"))
                        break
                    data = msg.get("data", {})
                    words = ""
                    for item in data.get("result", {}).get("ws", []):
                        for cw in item.get("cw", []):
                            words += cw.get("w", "")
                    if words:
                        # pgs=rpl 时替换，否则追加
                        pgs = data.get("result", {}).get("pgs", "")
                        if pgs == "rpl":
                            rg = data.get("result", {}).get("rg", [0, 0])
                            parts = list(self.result)
                            parts[rg[0]:rg[1]+1] = list(words)
                            self.result = "".join(parts)
                        else:
                            self.result += words
                        if on_partial:
                            on_partial(self.result)
                    if data.get("status") == 2:
                        break

                send_task.cancel()
        except Exception as e:
            logger.error("讯飞 ASR 失败: %s", e)
            self.result = ""
        finally:
            await read_task
            self._cleanup()

        return self.result
