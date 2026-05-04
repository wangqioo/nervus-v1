"""
语音录音 + STT 模块
直接复用 voice-keyboard 项目（github.com/wangqioo/voice-keyboard）的 STT 架构，
支持多 provider：xunfei / aliyun / volcengine / zhipuai / openai

录音使用 sounddevice（比 pyaudio 更简洁），
讯飞等 WebSocket 类 provider 使用 websocket-client + threading（非 asyncio）。
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import threading
import time
from typing import Callable

import sounddevice as sd

import config

logger = logging.getLogger("nervus.cli.voice")

SAMPLE_RATE = 16000
CHUNK_SIZE  = 1024


# ── STT 多 provider 实现（来自 voice-keyboard/agent/stt.py）──────────────

import io, wave

def _pcm_to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


class _XunfeiSTT:
    _HOST = "iat-api.xfyun.cn"
    _PATH = "/v2/iat"

    def __init__(self):
        try:
            import websocket as _ws
            self._ws = _ws
        except ImportError:
            raise ImportError("pip install websocket-client")
        self._app_id     = config.XUNFEI_APP_ID
        self._api_key    = config.XUNFEI_API_KEY
        self._api_secret = config.XUNFEI_SECRET

    def _build_url(self) -> str:
        import hashlib, hmac as _hmac
        from datetime import datetime, timezone
        from urllib.parse import urlencode
        date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        sig_origin = f"host: {self._HOST}\ndate: {date}\nGET {self._PATH} HTTP/1.1"
        sig = base64.b64encode(
            _hmac.new(self._api_secret.encode(), sig_origin.encode(), hashlib.sha256).digest()
        ).decode()
        auth = base64.b64encode(
            f'api_key="{self._api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{sig}"'.encode()
        ).decode()
        return f"wss://{self._HOST}{self._PATH}?" + urlencode({
            "authorization": auth, "date": date, "host": self._HOST,
        })

    def transcribe(self, pcm: bytes) -> str:
        CHUNK  = 1280
        chunks = [pcm[i:i + CHUNK] for i in range(0, len(pcm), CHUNK)]
        segments: dict[int, str] = {}
        err  = [None]
        done = threading.Event()

        def on_open(ws):
            def _send():
                n = len(chunks)
                for idx, chunk in enumerate(chunks):
                    status = 0 if idx == 0 else (2 if idx == n - 1 else 1)
                    frame: dict = {"data": {
                        "status":   status,
                        "format":   "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio":    base64.b64encode(chunk).decode(),
                    }}
                    if idx == 0:
                        frame["common"]   = {"app_id": self._app_id}
                        frame["business"] = {
                            "language": "zh_cn",
                            "domain":   "iat",
                            "accent":   "mandarin",
                            "ptt":      1,
                            "nunum":    1,
                            "dwa":      "wpgs",
                        }
                    ws.send(json.dumps(frame))
                    time.sleep(0.005)
                if n == 1:
                    ws.send(json.dumps({"data": {
                        "status": 2, "format": "audio/L16;rate=16000",
                        "encoding": "raw", "audio": "",
                    }}))
            threading.Thread(target=_send, daemon=True).start()

        def on_message(ws, msg):
            data   = json.loads(msg)
            code   = data.get("code", -1)
            if code != 0:
                err[0] = f"讯飞 code={code}: {data.get('message', '')}"
                ws.close(); return
            body   = data.get("data", {})
            result = body.get("result", {})
            pgs    = result.get("pgs", "apd")
            rg     = result.get("rg", [])
            sn     = result.get("sn", 0)
            text   = "".join(
                cw.get("w", "")
                for w in result.get("ws", [])
                for cw in w.get("cw", [])
            )
            if pgs == "rpl" and len(rg) >= 2:
                for i in range(rg[0], rg[1] + 1):
                    segments.pop(i, None)
            segments[sn] = text
            if body.get("status") == 2:
                ws.close(); done.set()

        def on_error(ws, e):
            err[0] = str(e); done.set()

        def on_close(ws, *_):
            done.set()

        app = self._ws.WebSocketApp(
            self._build_url(),
            on_open=on_open, on_message=on_message,
            on_error=on_error, on_close=on_close,
        )
        threading.Thread(target=app.run_forever, daemon=True).start()
        done.wait(timeout=15)
        if err[0]:
            raise RuntimeError(err[0])
        return "".join(segments[k] for k in sorted(segments)).strip()


class _AliyunSTT:
    """阿里云 NLS 一句话识别（REST）"""
    _TOKEN_URL = "https://nls-gateway.{region}.aliyuncs.com/token"
    _ASR_URL   = "https://nls-gateway.{region}.aliyuncs.com/stream/v1/asr"

    def __init__(self):
        import requests as _req
        self._req    = _req
        self._key_id = config.ALIYUN_ACCESS_KEY_ID
        self._secret = config.ALIYUN_ACCESS_KEY_SECRET
        self._app_key= config.ALIYUN_APP_KEY
        self._region = getattr(config, "ALIYUN_REGION", "cn-shanghai")
        self._token  = None
        self._expiry = 0.0

    def _get_token(self) -> str:
        if self._token and time.time() < self._expiry - 60:
            return self._token
        resp = self._req.post(
            self._TOKEN_URL.format(region=self._region),
            json={"AccessKeyId": self._key_id, "AccessKeySecret": self._secret},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token  = data["Token"]["Id"]
        self._expiry = float(data["Token"]["ExpireTime"])
        return self._token

    def transcribe(self, pcm: bytes) -> str:
        wav  = _pcm_to_wav(pcm)
        resp = self._req.post(
            self._ASR_URL.format(region=self._region),
            params={"appkey": self._app_key, "format": "wav",
                    "sample_rate": SAMPLE_RATE,
                    "enable_punctuation_prediction": "true",
                    "enable_inverse_text_normalization": "true"},
            headers={"X-NLS-Token": self._get_token(),
                     "Content-Type": "application/octet-stream"},
            data=wav, timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("status") == 20000000:
            return result.get("result", "").strip()
        raise RuntimeError(f"阿里云 NLS 错误: {result.get('message', result)}")


class _MockSTT:
    """未配置时的占位，避免崩溃"""
    def transcribe(self, pcm: bytes) -> str:
        return "[未配置 STT provider，请在 .env 中填写 XUNFEI 或 ALIYUN 配置]"


def _build_stt():
    """根据 config 选择 STT provider"""
    provider = getattr(config, "STT_PROVIDER", "").strip()
    if not provider:
        # 自动检测：有讯飞 key 用讯飞，有阿里云 key 用阿里云
        if config.XUNFEI_APP_ID:
            provider = "xunfei"
        elif getattr(config, "ALIYUN_APP_KEY", ""):
            provider = "aliyun"
    if provider == "xunfei":
        return _XunfeiSTT()
    if provider == "aliyun":
        return _AliyunSTT()
    return _MockSTT()


# ── 录音器 ────────────────────────────────────────────────────────────────────

class VoiceRecorder:
    """
    按住说话录音 + 异步 STT。
    start() 开始录音，stop() 结束录音并触发识别。
    结果通过 listen() 协程返回。
    """

    def __init__(self):
        self._stt         = _build_stt()
        self._recording   = False
        self._buf: list[bytes] = []
        self._stream      = None
        self.result       = ""

    def start(self):
        self._recording = True
        self._buf = []
        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK_SIZE,
            callback=self._cb,
        )
        self._stream.start()

    def stop(self):
        self._recording = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _cb(self, indata, frames, time_info, status):
        if self._recording:
            self._buf.append(bytes(indata))

    async def listen(self, on_partial: Callable[[str], None] | None = None) -> str:
        """录音结束后调用，在线程池里跑 STT，不阻塞事件循环。"""
        pcm = b"".join(self._buf)
        self._buf = []

        if len(pcm) < SAMPLE_RATE * 2 * 0.3:
            return ""

        loop = asyncio.get_event_loop()
        try:
            text = await loop.run_in_executor(None, self._stt.transcribe, pcm)
        except Exception as e:
            logger.error("STT 识别失败: %s", e)
            text = ""

        self.result = text
        return text
