"""
热量管理 App — Nervus 生态接入示例
拍照 → AI 识别食物 → 自动记录热量，零手动输入
"""

import os
import sqlite3
from datetime import datetime, date
from pathlib import Path

from fastapi.responses import HTMLResponse

import sys
sys.path.insert(0, "/app/nervus-sdk")
from nervus_sdk import NervusApp, Context, emit
from nervus_sdk.models import Event

# ── 初始化 ────────────────────────────────────────────────

nervus = NervusApp("calorie-tracker")

_HTML = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


@nervus._api.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_HTML)

# SQLite 数据库（每个 App 自治）
DB_PATH = os.getenv("DB_PATH", "/data/calorie-tracker.db")

DEFAULT_BUDGET = 2000  # 默认每日热量预算 kcal


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id          TEXT PRIMARY KEY,
            date        TEXT NOT NULL,
            meal_type   TEXT,             -- breakfast / lunch / dinner / snack
            food_name   TEXT NOT NULL,
            calories    REAL NOT NULL,
            protein     REAL DEFAULT 0,
            carbs       REAL DEFAULT 0,
            fat         REAL DEFAULT 0,
            photo_path  TEXT,
            source      TEXT DEFAULT 'auto',  -- auto / manual
            created_at  TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_budget', ?)",
        (str(DEFAULT_BUDGET),)
    )
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── 核心业务逻辑 ──────────────────────────────────────────

async def analyze_meal_with_ai(photo_path: str, tags: list = None) -> dict:
    """调用 llama.cpp 视觉模型分析食物照片"""
    prompt = """请分析这张食物图片，返回以下信息（JSON格式）：
{
  "food_name": "食物名称（中文）",
  "meal_type": "breakfast/lunch/dinner/snack 之一",
  "calories": 估算热量数值（整数，单位kcal）,
  "nutrition": {
    "protein": 蛋白质克数,
    "carbs": 碳水化合物克数,
    "fat": 脂肪克数
  },
  "confidence": 0到1之间的置信度
}
只返回JSON，不要其他文字。"""

    try:
        result = await nervus.llm.vision_json(photo_path, prompt)
        return result
    except Exception as e:
        # 降级：根据 tags 估算
        food_name = tags[0] if tags else "未知食物"
        return {
            "food_name": food_name,
            "meal_type": _guess_meal_type(),
            "calories": 500,
            "nutrition": {"protein": 20, "carbs": 60, "fat": 15},
            "confidence": 0.3,
        }


def _guess_meal_type() -> str:
    hour = datetime.now().hour
    if 6 <= hour < 10:
        return "breakfast"
    elif 11 <= hour < 14:
        return "lunch"
    elif 17 <= hour < 21:
        return "dinner"
    return "snack"


def get_daily_budget() -> int:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'daily_budget'").fetchone()
        return int(row["value"]) if row else DEFAULT_BUDGET


def get_today_total() -> float:
    today = date.today().isoformat()
    with get_db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(calories), 0) as total FROM meals WHERE date = ?", (today,)
        ).fetchone()
        return float(row["total"])


# ── 事件处理 ──────────────────────────────────────────────

@nervus.on("media.photo.classified", filter={"tags_contains": ["food"]})
async def handle_food_photo(event: Event):
    """接收食物照片分类事件，自动记录热量"""
    payload = event.payload
    photo_path = payload.get("photo_path", "")
    tags = payload.get("tags", [])

    # AI 分析食物
    analysis = await analyze_meal_with_ai(photo_path, tags)

    food_name = analysis.get("food_name", "未知食物")
    calories = float(analysis.get("calories", 0))
    nutrition = analysis.get("nutrition", {})
    meal_type = analysis.get("meal_type", _guess_meal_type())

    # 写入数据库
    import uuid
    meal_id = str(uuid.uuid4())
    today = date.today().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO meals (id, date, meal_type, food_name, calories, protein, carbs, fat, photo_path, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'auto', ?)
        """, (
            meal_id, today, meal_type, food_name, calories,
            nutrition.get("protein", 0), nutrition.get("carbs", 0), nutrition.get("fat", 0),
            photo_path, event.timestamp.isoformat() if hasattr(event.timestamp, "isoformat") else str(event.timestamp),
        ))
        conn.commit()

    # 更新 Context Graph
    budget = get_daily_budget()
    today_total = get_today_total()
    remaining = budget - today_total

    await Context.set("physical.last_meal", str(event.timestamp))
    await Context.set("physical.calorie_remaining", remaining)
    await Context.set("physical.daily_calorie_budget", budget)

    # 发布热量记录事件
    result = {
        "meal_id": meal_id,
        "food_name": food_name,
        "calories": calories,
        "meal_type": meal_type,
        "today_total": today_total,
        "remaining": remaining,
        "budget": budget,
    }
    await emit("health.calorie.meal_logged", result)

    # 超出预算警告
    if remaining < 0:
        await emit("health.calorie.budget_alert", {
            "message": f"今日热量已超出预算 {abs(remaining):.0f} kcal",
            "today_total": today_total,
            "budget": budget,
        })

    return result


# ── Action 注册 ───────────────────────────────────────────

@nervus.action("analyze_meal")
async def action_analyze_meal(photo_path: str = "", tags: list = None):
    return await analyze_meal_with_ai(photo_path, tags or [])


@nervus.action("get_today_summary")
async def action_get_today_summary():
    today = date.today().isoformat()
    budget = get_daily_budget()
    with get_db() as conn:
        meals = conn.execute(
            "SELECT * FROM meals WHERE date = ? ORDER BY created_at ASC", (today,)
        ).fetchall()
    total = sum(m["calories"] for m in meals)
    return {
        "date": today,
        "total_calories": total,
        "budget": budget,
        "remaining": budget - total,
        "meals": [dict(m) for m in meals],
    }


@nervus.action("set_daily_budget")
async def action_set_budget(calories: int = DEFAULT_BUDGET):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('daily_budget', ?)", (str(calories),))
        conn.commit()
    await Context.set("physical.daily_calorie_budget", calories)
    return {"success": True, "budget": calories}


@nervus.state
async def get_state():
    today_total = get_today_total()
    budget = get_daily_budget()
    return {
        "today_calories": today_total,
        "budget": budget,
        "remaining": budget - today_total,
        "percentage": round(today_total / budget * 100, 1) if budget > 0 else 0,
    }


# ── 额外 REST API（前端用） ────────────────────────────────

@nervus._api.get("/today")
async def today_summary():
    return await action_get_today_summary()


@nervus._api.get("/history")
async def meal_history(days: int = 7):
    from datetime import timedelta
    dates = [(date.today() - timedelta(days=i)).isoformat() for i in range(days)]
    with get_db() as conn:
        meals = conn.execute(
            f"SELECT * FROM meals WHERE date IN ({','.join('?' for _ in dates)}) ORDER BY created_at DESC",
            dates
        ).fetchall()
    return {"meals": [dict(m) for m in meals]}


@nervus._api.post("/meals/manual")
async def add_manual_meal(body: dict):
    """手动添加饮食记录"""
    import uuid
    meal_id = str(uuid.uuid4())
    today = date.today().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO meals (id, date, meal_type, food_name, calories, protein, carbs, fat, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?)
        """, (
            meal_id, today,
            body.get("meal_type", _guess_meal_type()),
            body.get("food_name", "手动记录"),
            body.get("calories", 0),
            body.get("protein", 0), body.get("carbs", 0), body.get("fat", 0),
            datetime.utcnow().isoformat(),
        ))
        conn.commit()
    return {"success": True, "meal_id": meal_id}


from fastapi import UploadFile, File

@nervus._api.post("/meals/photo")
async def analyze_photo_upload_v2(file: UploadFile = File(...)):
    """接收前端上传的食物图片，AI 分析返回识别结果"""
    import tempfile
    content = await file.read()
    suffix = Path(file.filename or "photo.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = await analyze_meal_with_ai(tmp_path, [])
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return result


if __name__ == "__main__":
    init_db()
    nervus.run(port=int(os.getenv("APP_PORT", "8001")))
