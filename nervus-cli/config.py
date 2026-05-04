import os
from dotenv import load_dotenv

load_dotenv()

# Arbor Core
ARBOR_URL = os.getenv("ARBOR_URL", "http://localhost:8090")

# NATS
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

# 各 App 地址
APP_PORTS = {
    "calorie-tracker":  8001,
    "meeting-notes":    8002,
    "knowledge-base":   8003,
    "life-memory":      8004,
    "sense":            8005,
    "photo-scanner":    8006,
    "personal-notes":   8007,
    "pdf-extractor":    8008,
    "video-transcriber":8009,
    "rss-reader":       8010,
    "calendar":         8011,
    "reminder":         8012,
    "status-sense":     8013,
    "workflow-viewer":  8014,
    "file-manager":     8015,
    "model-manager":    8016,
}

def app_url(app_id: str) -> str:
    host = os.getenv("APP_HOST", "localhost")
    port = APP_PORTS.get(app_id, 8090)
    return f"http://{host}:{port}"

# 讯飞 ASR
XUNFEI_APP_ID  = os.getenv("XUNFEI_APP_ID", "")
XUNFEI_API_KEY = os.getenv("XUNFEI_API_KEY", "")
XUNFEI_SECRET  = os.getenv("XUNFEI_SECRET", "")

# 语音按钮 GPIO（H618 上用）
VOICE_GPIO_PIN = int(os.getenv("VOICE_GPIO_PIN", "0"))

# 界面
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "1.5"))  # 秒
MAX_CHAT_LINES = int(os.getenv("MAX_CHAT_LINES", "200"))
