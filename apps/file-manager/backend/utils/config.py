import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent.parent
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data" / "files"
DATA_DIR.mkdir(parents=True, exist_ok=True)

GLM_API_KEY = os.getenv("GLM_API_KEY", "")
GLM_MODEL = os.getenv("GLM_MODEL", "glm-4-flash")
GLM_VISION_MODEL = os.getenv("GLM_VISION_MODEL", "glm-4v-flash")

# LinkBox API — 填入后自动接管公众号 / 通用链接解析
LINKBOX_API_URL = os.getenv("LINKBOX_API_URL", "")   # e.g. https://your-linkbox.com/api/parse
LINKBOX_API_KEY = os.getenv("LINKBOX_API_KEY", "")

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
ALLOWED_EXTENSIONS = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"},
    "video": {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"},
    "document": {".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".xls", ".xlsx", ".ppt", ".pptx"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
}

URL_PATTERNS = {
    "wechat": ["mp.weixin.qq.com"],
    "bilibili": ["bilibili.com", "b23.tv"],
}

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
