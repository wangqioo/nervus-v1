"""
热量管理 App — 移植自 heat-identification，接入 Nervus 生态
拍照 → AI 识别多种食物 → 自动记录热量，支持健康/减脂/增肌三种模式
"""

import json
import os
import re
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import File, UploadFile

import sys
sys.path.insert(0, "/app/nervus-sdk")
from nervus_sdk import NervusApp, Context, emit
from nervus_sdk.models import Event

# ── 初始化 ────────────────────────────────────────────────

nervus = NervusApp("calorie-tracker")


async def index():

DB_PATH = os.getenv("DB_PATH", "/data/calorie-tracker.db")
PHOTO_DIR = "/data/meal_photos"
DEFAULT_BUDGET = 2000


# ── 数据库 ────────────────────────────────────────────────

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(PHOTO_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id             TEXT PRIMARY KEY,
            date           TEXT NOT NULL,
            meal_type      TEXT,
            food_name      TEXT NOT NULL,
            calories       REAL NOT NULL,
            protein        REAL DEFAULT 0,
            carbs          REAL DEFAULT 0,
            fat            REAL DEFAULT 0,
            food_items     TEXT DEFAULT '[]',
            image_filename TEXT DEFAULT '',
            photo_path     TEXT,
            source         TEXT DEFAULT 'auto',
            created_at     TEXT NOT NULL
        )
    """)
    # Migrate older DB: add new columns if missing
    for col, defval in [("food_items", "'[]'"), ("image_filename", "''")]:
        try:
            conn.execute(f"ALTER TABLE meals ADD COLUMN {col} TEXT DEFAULT {defval}")
        except Exception:
            pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    defaults = [
        ("daily_budget", str(DEFAULT_BUDGET)),
        ("profile_gender", "male"),
        ("profile_age", "25"),
        ("profile_height", "0"),
        ("profile_weight", "0"),
        ("profile_activity", "1.55"),
        ("profile_mode", "health"),
    ]
    for k, v in defaults:
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_setting(key: str, default: str = "") -> str:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        conn.commit()


init_db()


# ── 计算 BMR / TDEE ───────────────────────────────────────

def calc_bmr(gender, age, height, weight) -> int:
    if not height or not weight:
        return 0
    base = 10 * weight + 6.25 * height - 5 * age
    return round(base + 5 if gender == "male" else base - 161)


def calc_tdee(gender, age, height, weight, activity) -> int:
    bmr = calc_bmr(gender, age, height, weight)
    return round(bmr * activity) if bmr else 0


def get_profile() -> dict:
    return {
        "gender":   get_setting("profile_gender", "male"),
        "age":      int(get_setting("profile_age", "25") or 25),
        "height":   float(get_setting("profile_height", "0") or 0),
        "weight":   float(get_setting("profile_weight", "0") or 0),
        "activity": float(get_setting("profile_activity", "1.55") or 1.55),
        "mode":     get_setting("profile_mode", "health"),
    }


def get_daily_budget() -> int:
    return int(get_setting("daily_budget", str(DEFAULT_BUDGET)) or DEFAULT_BUDGET)


def get_today_total() -> float:
    today = date.today().isoformat()
    with get_db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(calories), 0) as total FROM meals WHERE date=?", (today,)
        ).fetchone()
        return float(row["total"])


# ── AI 分析 ───────────────────────────────────────────────

async def analyze_meal_with_ai(photo_path: str, tags: list = None) -> dict:
    """调用视觉模型识别图片中的多种食物，返回 food_items 数组"""
    prompt = """请分析这张图片中的食物，以JSON格式返回：
{
  "food_items": [
    {"name": "食物名称（中文）", "quantity": "份量", "calories": 数字, "protein": 蛋白质克数, "carbs": 碳水克数, "fat": 脂肪克数}
  ],
  "total_calories": 总热量整数,
  "meal_type": "breakfast/lunch/dinner/snack 之一",
  "health_note": "健康提示1-2句"
}
只返回JSON。若无食物则返回 {"error": "未检测到食物"}。"""
    try:
        result = await nervus.llm.vision_json(photo_path, prompt, max_tokens=800)
        if "error" in result:
            raise ValueError(result["error"])
        # Normalise
        items = result.get("food_items", [])
        total = result.get("total_calories") or sum(i.get("calories", 0) for i in items)
        # Build legacy single-food fields from first item or totals
        first = items[0] if items else {}
        return {
            "food_items":     items,
            "food_name":      "、".join(i.get("name", "") for i in items) or first.get("name", tags[0] if tags else "未知食物"),
            "total_calories": int(total),
            "calories":       int(total),
            "meal_type":      result.get("meal_type", _guess_meal_type()),
            "health_note":    result.get("health_note", ""),
            "protein":        round(sum(i.get("protein", 0) for i in items), 1),
            "carbs":          round(sum(i.get("carbs", 0) for i in items), 1),
            "fat":            round(sum(i.get("fat", 0) for i in items), 1),
            "confidence":     0.85,
        }
    except Exception:
        food_name = tags[0] if tags else "未知食物"
        return {
            "food_items":     [{"name": food_name, "quantity": "1份", "calories": 500, "protein": 20, "carbs": 60, "fat": 15}],
            "food_name":      food_name,
            "total_calories": 500,
            "calories":       500,
            "meal_type":      _guess_meal_type(),
            "health_note":    "",
            "protein":        20.0,
            "carbs":          60.0,
            "fat":            15.0,
            "confidence":     0.3,
        }


def _guess_meal_type() -> str:
    hour = datetime.now().hour
    if 6 <= hour < 10:   return "breakfast"
    elif 11 <= hour < 14: return "lunch"
    elif 17 <= hour < 21: return "dinner"
    return "snack"


# ── 事件处理 ──────────────────────────────────────────────

@nervus.on("media.photo.classified", filter={"tags_contains": ["food"]})
async def handle_food_photo(event: Event):
    payload     = event.payload
    photo_path  = payload.get("photo_path", "")
    tags        = payload.get("tags", [])
    analysis    = await analyze_meal_with_ai(photo_path, tags)
    meal_type   = analysis["meal_type"]
    calories    = float(analysis["calories"])
    meal_id     = str(uuid.uuid4())
    today       = date.today().isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO meals (id, date, meal_type, food_name, calories, protein, carbs, fat,
               food_items, source, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (meal_id, today, meal_type, analysis["food_name"], calories,
             analysis["protein"], analysis["carbs"], analysis["fat"],
             json.dumps(analysis["food_items"], ensure_ascii=False),
             "auto", event.timestamp.isoformat() if hasattr(event.timestamp, "isoformat") else str(event.timestamp)),
        )
        conn.commit()
    p       = get_profile()
    budget  = get_daily_budget()
    today_total = get_today_total()
    remaining   = budget - today_total
    await Context.set("physical.last_meal", str(event.timestamp))
    await Context.set("physical.calorie_remaining", remaining)
    await emit("health.calorie.meal_logged", {"meal_id": meal_id, "calories": calories, "today_total": today_total})
    if remaining < 0:
        await emit("health.calorie.budget_alert", {"message": f"今日热量超出预算 {abs(remaining):.0f} kcal", "today_total": today_total, "budget": budget})
    return {"meal_id": meal_id, "calories": calories}


# ── Actions ───────────────────────────────────────────────

@nervus.action("analyze_meal")
async def action_analyze_meal(photo_path: str = "", tags: list = None):
    return await analyze_meal_with_ai(photo_path, tags or [])


@nervus.action("get_today_summary")
async def action_get_today_summary():
    today  = date.today().isoformat()
    budget = get_daily_budget()
    with get_db() as conn:
        meals = conn.execute(
            "SELECT * FROM meals WHERE date=? ORDER BY created_at ASC", (today,)
        ).fetchall()
    total = sum(m["calories"] for m in meals)
    return {"date": today, "total_calories": total, "budget": budget,
            "remaining": budget - total, "meals": [dict(m) for m in meals]}


@nervus.action("set_daily_budget")
async def action_set_budget(calories: int = DEFAULT_BUDGET):
    set_setting("daily_budget", str(calories))
    await Context.set("physical.daily_calorie_budget", calories)
    return {"success": True, "budget": calories}


@nervus.state
async def get_state():
    today_total = get_today_total()
    budget      = get_daily_budget()
    return {"today_calories": today_total, "budget": budget,
            "remaining": budget - today_total,
            "percentage": round(today_total / budget * 100, 1) if budget > 0 else 0}


# ── REST API ──────────────────────────────────────────────

@nervus._api.get("/today")
async def today_summary():
    return await action_get_today_summary()


@nervus._api.get("/history")
async def meal_history(days: int = 7):
    dates = [(date.today() - timedelta(days=i)).isoformat() for i in range(days)]
    with get_db() as conn:
        meals = conn.execute(
            f"SELECT * FROM meals WHERE date IN ({','.join('?' for _ in dates)}) ORDER BY created_at DESC",
            dates
        ).fetchall()
    return {"meals": [dict(m) for m in meals]}


@nervus._api.get("/stats")
async def get_stats(date_str: str = ""):
    target_date = date_str or date.today().isoformat()
    p     = get_profile()
    tdee  = calc_tdee(p["gender"], p["age"], p["height"], p["weight"], p["activity"])
    bmr   = calc_bmr(p["gender"], p["age"], p["height"], p["weight"])
    protein_goal = round(p["weight"] * 2.0) if p["weight"] else 0
    with get_db() as conn:
        meals = conn.execute("SELECT * FROM meals WHERE date=?", (target_date,)).fetchall()
    total_cal = total_protein = total_carbs = total_fat = 0.0
    meal_cal  = {"breakfast": 0.0, "lunch": 0.0, "dinner": 0.0, "snack": 0.0}
    for m in meals:
        cal = m["calories"]
        total_cal    += cal
        total_protein += m["protein"] or 0
        total_carbs   += m["carbs"]   or 0
        total_fat     += m["fat"]     or 0
        mt = m["meal_type"] or ""
        if mt in meal_cal:
            meal_cal[mt] += cal
    return {
        "date":           target_date,
        "meal_count":     len(meals),
        "total_calories": round(total_cal),
        "total_protein":  round(total_protein, 1),
        "total_carbs":    round(total_carbs, 1),
        "total_fat":      round(total_fat, 1),
        "tdee":           tdee,
        "bmr":            bmr,
        "budget":         get_daily_budget(),
        "protein_goal":   protein_goal,
        "calorie_gap":    round(total_cal - tdee) if tdee else 0,
        "mode":           p["mode"],
        "meal_calories":  {k: round(v) for k, v in meal_cal.items()},
    }


@nervus._api.get("/profile")
async def get_profile_api():
    p    = get_profile()
    bmr  = calc_bmr(p["gender"], p["age"], p["height"], p["weight"])
    tdee = calc_tdee(p["gender"], p["age"], p["height"], p["weight"], p["activity"])
    protein_goal = round(p["weight"] * 2.0) if p["weight"] else 0
    return {**p, "bmr": bmr, "tdee": tdee, "protein_goal": protein_goal}


@nervus._api.post("/profile")
async def set_profile_api(body: dict):
    mapping = {
        "gender": "profile_gender", "age": "profile_age",
        "height": "profile_height", "weight": "profile_weight",
        "activity": "profile_activity", "mode": "profile_mode",
    }
    for k, sk in mapping.items():
        if k in body:
            set_setting(sk, str(body[k]))
    p    = get_profile()
    bmr  = calc_bmr(p["gender"], p["age"], p["height"], p["weight"])
    tdee = calc_tdee(p["gender"], p["age"], p["height"], p["weight"], p["activity"])
    protein_goal = round(p["weight"] * 2.0) if p["weight"] else 0
    return {"success": True, "bmr": bmr, "tdee": tdee, "protein_goal": protein_goal, "mode": p["mode"]}


@nervus._api.get("/daily-report")
async def daily_report(date_str: str = ""):
    target_date = date_str or date.today().isoformat()
    p     = get_profile()
    tdee  = calc_tdee(p["gender"], p["age"], p["height"], p["weight"], p["activity"])
    mode_map = {"health": "健康维持", "loss": "减脂", "muscle": "增肌"}
    with get_db() as conn:
        meals = conn.execute("SELECT * FROM meals WHERE date=?", (target_date,)).fetchall()
    if not meals:
        return {"error": "今日暂无饮食记录，请先记录餐食"}
    meals_info = []
    total_cal = total_protein = total_carbs = total_fat = 0.0
    for m in meals:
        mt    = m["meal_type"] or "未知"
        items = json.loads(m["food_items"] or "[]")
        foods = "、".join(i.get("name", "") for i in items) if items else m["food_name"]
        cal   = m["calories"]
        meals_info.append(f"{mt}：{foods}（{cal:.0f} kcal）")
        total_cal    += cal
        total_protein += m["protein"] or 0
        total_carbs   += m["carbs"]   or 0
        total_fat     += m["fat"]     or 0
    prompt = f"""你是专业营养师，根据以下饮食记录生成简洁的每日健康日报。
日期：{target_date}
目标模式：{mode_map.get(p['mode'], '健康维持')}
每日总消耗 TDEE：{tdee} kcal
今日饮食：{chr(10).join(meals_info)}
今日营养：热量 {total_cal:.0f} kcal，蛋白质 {total_protein:.1f}g，碳水 {total_carbs:.1f}g，脂肪 {total_fat:.1f}g
请返回以下JSON（只返回JSON）：
{{"summary":"100字以内总结","score":0到100评分,"highlights":["亮点1","亮点2"],"suggestions":["建议1","建议2","建议3"],"tomorrow_tips":"明日建议一两句"}}"""
    try:
        result = await nervus.llm.chat_json(prompt, max_tokens=600)
        return result
    except Exception as e:
        return {"error": f"生成失败：{str(e)}"}


@nervus._api.get("/records")
async def get_records(date_str: str = ""):
    target_date = date_str or date.today().isoformat()
    with get_db() as conn:
        meals = conn.execute(
            "SELECT * FROM meals WHERE date=? ORDER BY created_at DESC", (target_date,)
        ).fetchall()
    result = []
    for m in meals:
        d = dict(m)
        try:
            d["food_items"] = json.loads(d.get("food_items") or "[]")
        except Exception:
            d["food_items"] = []
        result.append(d)
    return result


@nervus._api.delete("/records/{meal_id}")
async def delete_record(meal_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT image_filename FROM meals WHERE id=?", (meal_id,)).fetchone()
        if row and row["image_filename"]:
            img_path = Path(PHOTO_DIR) / row["image_filename"]
            img_path.unlink(missing_ok=True)
        conn.execute("DELETE FROM meals WHERE id=?", (meal_id,))
        conn.commit()
    return {"success": True}


@nervus._api.post("/meals/manual")
async def add_manual_meal(body: dict):
    meal_id   = str(uuid.uuid4())
    today_str = date.today().isoformat()
    food_name = body.get("food_name", "手动记录")
    calories  = float(body.get("calories", 0))
    meal_type = body.get("meal_type", _guess_meal_type())
    protein   = float(body.get("protein", 0))
    carbs     = float(body.get("carbs", 0))
    fat       = float(body.get("fat", 0))
    items     = [{"name": food_name, "quantity": "1份", "calories": calories,
                  "protein": protein, "carbs": carbs, "fat": fat}]
    with get_db() as conn:
        conn.execute(
            """INSERT INTO meals (id, date, meal_type, food_name, calories, protein, carbs, fat,
               food_items, source, created_at) VALUES (?,?,?,?,?,?,?,?,?,'manual',?)""",
            (meal_id, today_str, meal_type, food_name, calories, protein, carbs, fat,
             json.dumps(items, ensure_ascii=False), datetime.utcnow().isoformat()),
        )
        conn.commit()
    return {"success": True, "meal_id": meal_id}


@nervus._api.post("/meals/photo")
async def analyze_photo_upload(file: UploadFile = File(...), meal_type: str = ""):
    import tempfile
    content = await file.read()
    suffix  = Path(file.filename or "photo.jpg").suffix or ".jpg"
    # Save to meal_photos with permanent filename
    photo_filename = f"{uuid.uuid4().hex}{suffix}"
    photo_path     = Path(PHOTO_DIR) / photo_filename
    photo_path.write_bytes(content)
    try:
        result = await analyze_meal_with_ai(str(photo_path), [])
    except Exception:
        photo_path.unlink(missing_ok=True)
        return {"error": "分析失败，请重试"}
    # Auto-save to DB
    meal_id   = str(uuid.uuid4())
    today_str = date.today().isoformat()
    mt        = meal_type or result.get("meal_type", _guess_meal_type())
    with get_db() as conn:
        conn.execute(
            """INSERT INTO meals (id, date, meal_type, food_name, calories, protein, carbs, fat,
               food_items, image_filename, source, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,'auto',?)""",
            (meal_id, today_str, mt, result["food_name"], result["calories"],
             result["protein"], result["carbs"], result["fat"],
             json.dumps(result["food_items"], ensure_ascii=False),
             photo_filename, datetime.utcnow().isoformat()),
        )
        conn.commit()
    result["meal_id"]        = meal_id
    result["image_filename"] = photo_filename
    result["meal_type"]      = mt
    return result


@nervus._api.get("/meals/image/{filename}")
async def serve_meal_image(filename: str):
    # Prevent path traversal
    filename = Path(filename).name
    path = Path(PHOTO_DIR) / filename
    if not path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(path))


if __name__ == "__main__":
    init_db()
    nervus.run(port=int(os.getenv("APP_PORT", "8001")))
