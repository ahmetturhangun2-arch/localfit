from __future__ import annotations

import io
import math
import os
import sqlite3
from datetime import datetime, date
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "app.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-this-secret")


# -----------------------------
# Database helpers
# -----------------------------
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            age INTEGER,
            gender TEXT,
            height REAL,
            weight REAL,
            target_weight REAL,
            goal TEXT,
            activity_level TEXT,
            experience_level TEXT,
            workout_days INTEGER,
            equipment TEXT,
            diet_preference TEXT,
            meals_per_day INTEGER,
            injuries TEXT,
            health_notes TEXT,
            sleep_hours REAL,
            water_goal_liters REAL,
            supplement_preference TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            calorie_target INTEGER NOT NULL,
            protein_g INTEGER NOT NULL,
            carbs_g INTEGER NOT NULL,
            fats_g INTEGER NOT NULL,
            bmi REAL,
            bmr INTEGER,
            tdee INTEGER,
            water_goal_liters REAL,
            meal_plan TEXT NOT NULL,
            meal_alternatives TEXT NOT NULL,
            workout_plan TEXT NOT NULL,
            supplement_notes TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS progress_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            weight REAL,
            waist REAL,
            chest REAL,
            hips REAL,
            arms REAL,
            thighs REAL,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """
    )
    db.commit()

    admin_email = "admin@localfit.com"
    row = db.execute("SELECT id FROM users WHERE email = ?", (admin_email,)).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO users (full_name, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                "Local Admin",
                admin_email,
                generate_password_hash("147258.Atgn"),
                "admin",
                now_str(),
            ),
        )
        db.commit()


# -----------------------------
# Utilities
# -----------------------------
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return date.today().isoformat()


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Bu sayfayi goruntulemek icin giris yapmalisin.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped



def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Bu alan sadece admin icindir.", "danger")
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)

    return wrapped



def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_managed_user_id() -> int:
    if session.get("role") == "admin":
        return int(session.get("client_user_id") or session.get("user_id"))
    return int(session["user_id"])


def get_managed_user():
    user_id = get_managed_user_id()
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_profile(user_id: int):
    return get_db().execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()


def profile_form_data() -> dict:
    return {
        "age": request.form.get("age") or None,
        "gender": request.form.get("gender") or None,
        "height": request.form.get("height") or None,
        "weight": request.form.get("weight") or None,
        "target_weight": request.form.get("target_weight") or None,
        "goal": request.form.get("goal") or None,
        "activity_level": request.form.get("activity_level") or None,
        "experience_level": request.form.get("experience_level") or None,
        "workout_days": request.form.get("workout_days") or None,
        "equipment": request.form.get("equipment") or None,
        "diet_preference": request.form.get("diet_preference") or None,
        "meals_per_day": request.form.get("meals_per_day") or None,
        "injuries": request.form.get("injuries") or None,
        "health_notes": request.form.get("health_notes") or None,
        "sleep_hours": request.form.get("sleep_hours") or None,
        "water_goal_liters": request.form.get("water_goal_liters") or None,
        "supplement_preference": request.form.get("supplement_preference") or None,
        "updated_at": now_str(),
    }


def upsert_profile(user_id: int, data: dict) -> None:
    db = get_db()
    existing = get_profile(user_id)
    if existing:
        db.execute(
            """
            UPDATE profiles SET
                age=:age, gender=:gender, height=:height, weight=:weight,
                target_weight=:target_weight, goal=:goal, activity_level=:activity_level,
                experience_level=:experience_level, workout_days=:workout_days,
                equipment=:equipment, diet_preference=:diet_preference,
                meals_per_day=:meals_per_day, injuries=:injuries,
                health_notes=:health_notes, sleep_hours=:sleep_hours,
                water_goal_liters=:water_goal_liters,
                supplement_preference=:supplement_preference, updated_at=:updated_at
            WHERE user_id=:user_id
            """,
            {**data, "user_id": user_id},
        )
    else:
        db.execute(
            """
            INSERT INTO profiles (
                user_id, age, gender, height, weight, target_weight, goal,
                activity_level, experience_level, workout_days, equipment,
                diet_preference, meals_per_day, injuries, health_notes,
                sleep_hours, water_goal_liters, supplement_preference, updated_at
            ) VALUES (
                :user_id, :age, :gender, :height, :weight, :target_weight, :goal,
                :activity_level, :experience_level, :workout_days, :equipment,
                :diet_preference, :meals_per_day, :injuries, :health_notes,
                :sleep_hours, :water_goal_liters, :supplement_preference, :updated_at
            )
            """,
            {**data, "user_id": user_id},
        )
    db.commit()



def activity_multiplier(level: str) -> float:
    mapping = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }
    return mapping.get(level, 1.375)



def goal_adjustment(goal: str) -> int:
    mapping = {
        "lose": -450,
        "recomp": -150,
        "maintain": 0,
        "gain": 300,
    }
    return mapping.get(goal, 0)



def calculate_metrics(profile: sqlite3.Row) -> dict:
    weight = float(profile["weight"] or 0)
    height_cm = float(profile["height"] or 0)
    age = int(profile["age"] or 18)
    gender = (profile["gender"] or "male").lower()
    height_m = height_cm / 100 if height_cm else 0
    bmi = round(weight / (height_m ** 2), 1) if height_m else 0

    if gender == "female":
        bmr = 10 * weight + 6.25 * height_cm - 5 * age - 161
    else:
        bmr = 10 * weight + 6.25 * height_cm - 5 * age + 5
    bmr = int(round(bmr))
    tdee = int(round(bmr * activity_multiplier(profile["activity_level"])))
    calorie_target = max(1200, tdee + goal_adjustment(profile["goal"]))

    goal = profile["goal"]
    if goal == "gain":
        protein = round(weight * 2.0)
        fats = round(weight * 0.9)
    elif goal == "lose":
        protein = round(weight * 2.1)
        fats = round(weight * 0.8)
    else:
        protein = round(weight * 1.8)
        fats = round(weight * 0.8)

    calories_from_protein = protein * 4
    calories_from_fats = fats * 9
    remaining = max(0, calorie_target - calories_from_protein - calories_from_fats)
    carbs = round(remaining / 4)

    water_goal = profile["water_goal_liters"]
    if not water_goal:
        water_goal = round(weight * 0.035 + (profile["workout_days"] or 3) * 0.15, 1)

    return {
        "bmi": bmi,
        "bmr": bmr,
        "tdee": tdee,
        "calorie_target": int(calorie_target),
        "protein_g": int(protein),
        "fats_g": int(fats),
        "carbs_g": int(carbs),
        "water_goal_liters": float(water_goal),
    }



def goal_label(goal: str) -> str:
    return {
        "lose": "Yag kaybi",
        "maintain": "Koruma",
        "gain": "Kas kazanimi",
        "recomp": "Vucut kompozisyonu iyilestirme",
    }.get(goal, "Genel fitness")


def experience_label(level: str) -> str:
    return {
        "beginner": "Baslangic",
        "intermediate": "Orta",
        "advanced": "Ileri",
    }.get(level, "Baslangic")


def equipment_label(value: str) -> str:
    return {
        "home": "Ev ekipmani",
        "gym": "Spor salonu",
        "bodyweight": "Ekipmansiz",
    }.get(value, "Karisik")


def workout_split(profile: sqlite3.Row) -> list[dict]:
    days = int(profile["workout_days"] or 3)
    level = profile["experience_level"] or "beginner"
    equipment = profile["equipment"] or "bodyweight"

    bodyweight = equipment == "bodyweight"
    home = equipment == "home"
    gym = equipment == "gym"

    exercise_bank = {
        "push": [
            "Sinav / incline push-up 4x8-15",
            "Dumbbell bench press 4x8-12" if (gym or home) else "Diamond push-up 3x8-12",
            "Shoulder press 3x10-12" if (gym or home) else "Pike push-up 3x6-10",
            "Lateral raise 3x12-15" if (gym or home) else "Bench dip 3x10-15",
            "Triceps extension 3x12-15" if (gym or home) else "Close push-up 2xAMRAP",
        ],
        "pull": [
            "Lat pulldown 4x8-12" if gym else "Band row 4x10-15" if home else "Towel row 4x8-12",
            "Seated row 3x10-12" if gym else "One-arm dumbbell row 3x10-12" if home else "Superman hold 3x30 sn",
            "Face pull 3x12-15" if (gym or home) else "Reverse snow angel 3x12",
            "Biceps curl 3x10-15" if (gym or home) else "Isometric curl hold 3x20 sn",
            "Dead hang / grip work 3 set",
        ],
        "legs": [
            "Squat 4x8-12" if gym else "Goblet squat 4x10-15" if home else "Bodyweight squat 4x15-20",
            "Romanian deadlift 4x8-12" if (gym or home) else "Hip hinge drill 4x12",
            "Walking lunge 3x10-12 her bacak",
            "Leg curl 3x12" if gym else "Glute bridge 3x15-20",
            "Calf raise 4x15-20",
            "Core: plank 3x45-60 sn",
        ],
        "full": [
            "Squat varyasyonu 4 set",
            "Push varyasyonu 4 set",
            "Row / cekis varyasyonu 4 set",
            "Hip hinge 3 set",
            "Core 3 set",
            "10-15 dk dusuk tempolu kardiyo",
        ],
        "upper": [
            "Bench / push varyasyonu 4 set",
            "Row varyasyonu 4 set",
            "Shoulder press 3 set",
            "Lat pulldown / band pull 3 set",
            "Biceps + triceps 2-3 set",
            "Core 2 set",
        ],
        "lower": [
            "Squat 4 set",
            "Romanian deadlift 4 set",
            "Lunge 3 set",
            "Hamstring / glute hareketi 3 set",
            "Calf raise 3 set",
            "Core 2 set",
        ],
    }

    plan = []
    if days <= 3:
        for i in range(days):
            plan.append({
                "day": f"Gun {i + 1}",
                "title": "Full Body",
                "focus": f"{experience_label(level)} seviye - tum vucut",
                "exercises": exercise_bank["full"],
            })
    elif days == 4:
        titles = [("Gun 1", "Upper"), ("Gun 2", "Lower"), ("Gun 3", "Upper"), ("Gun 4", "Lower")]
        for day, title in titles:
            key = title.lower()
            plan.append({
                "day": day,
                "title": title,
                "focus": f"{equipment_label(equipment)} - {title}",
                "exercises": exercise_bank[key],
            })
    else:
        titles = [
            ("Gun 1", "Push"),
            ("Gun 2", "Pull"),
            ("Gun 3", "Legs"),
            ("Gun 4", "Upper"),
            ("Gun 5", "Lower"),
        ]
        for day, title in titles[:days]:
            key = title.lower()
            if key not in exercise_bank:
                key = "full"
            plan.append({
                "day": day,
                "title": title,
                "focus": f"{equipment_label(equipment)} - {title}",
                "exercises": exercise_bank[key],
            })
    return plan



def meal_framework(profile: sqlite3.Row, metrics: dict) -> tuple[list[dict], list[dict]]:
    meals = int(profile["meals_per_day"] or 4)
    pref = profile["diet_preference"] or "balanced"
    calorie_target = int(metrics["calorie_target"])
    meal_calories = [round(calorie_target / meals) for _ in range(meals)]
    meal_names = ["Kahvalti", "Ara Ogun", "Ogle", "Ikinci Ara Ogun", "Aksam", "Gece Ogunu"]

    food_sets = {
        "balanced": {
            "breakfast": [
                {"name": "yumurta", "unit": "adet", "qty": 3, "kcal": 78},
                {"name": "yulaf", "unit": "g", "qty": 80, "kcal": 3.9},
                {"name": "muz", "unit": "adet", "qty": 1, "kcal": 105},
                {"name": "fistik ezmesi", "unit": "g", "qty": 20, "kcal": 5.9},
            ],
            "main": [
                {"name": "tavuk gogus", "unit": "g", "qty": 180, "kcal": 1.65},
                {"name": "pirinc", "unit": "g", "qty": 120, "kcal": 1.3},
                {"name": "zeytinyagi", "unit": "g", "qty": 10, "kcal": 9},
                {"name": "salata", "unit": "g", "qty": 150, "kcal": 0.2},
            ],
            "snack": [
                {"name": "yogurt", "unit": "g", "qty": 250, "kcal": 0.62},
                {"name": "badem", "unit": "g", "qty": 25, "kcal": 5.8},
                {"name": "elma", "unit": "adet", "qty": 1, "kcal": 95},
            ],
            "dinner": [
                {"name": "somon", "unit": "g", "qty": 170, "kcal": 2.08},
                {"name": "patates", "unit": "g", "qty": 250, "kcal": 0.87},
                {"name": "sebze", "unit": "g", "qty": 200, "kcal": 0.3},
            ],
        },
        "vegetarian": {
            "breakfast": [
                {"name": "yumurta", "unit": "adet", "qty": 3, "kcal": 78},
                {"name": "lor peyniri", "unit": "g", "qty": 120, "kcal": 1.2},
                {"name": "tam bugday ekmegi", "unit": "dilim", "qty": 4, "kcal": 75},
                {"name": "domates salatalik", "unit": "g", "qty": 150, "kcal": 0.2},
            ],
            "main": [
                {"name": "tofu", "unit": "g", "qty": 220, "kcal": 0.76},
                {"name": "bulgur", "unit": "g", "qty": 160, "kcal": 0.83},
                {"name": "yogurt", "unit": "g", "qty": 200, "kcal": 0.62},
                {"name": "zeytinyagi", "unit": "g", "qty": 10, "kcal": 9},
            ],
            "snack": [
                {"name": "kefir", "unit": "ml", "qty": 300, "kcal": 0.55},
                {"name": "ceviz", "unit": "g", "qty": 20, "kcal": 6.5},
                {"name": "muz", "unit": "adet", "qty": 1, "kcal": 105},
            ],
            "dinner": [
                {"name": "mercimek", "unit": "g", "qty": 250, "kcal": 1.16},
                {"name": "pirinc", "unit": "g", "qty": 120, "kcal": 1.3},
                {"name": "salata", "unit": "g", "qty": 150, "kcal": 0.2},
                {"name": "zeytinyagi", "unit": "g", "qty": 10, "kcal": 9},
            ],
        },
        "vegan": {
            "breakfast": [
                {"name": "yulaf", "unit": "g", "qty": 90, "kcal": 3.9},
                {"name": "soya yogurt", "unit": "g", "qty": 250, "kcal": 0.5},
                {"name": "muz", "unit": "adet", "qty": 1, "kcal": 105},
                {"name": "chia", "unit": "g", "qty": 15, "kcal": 4.9},
            ],
            "main": [
                {"name": "tofu", "unit": "g", "qty": 250, "kcal": 0.76},
                {"name": "pirinc", "unit": "g", "qty": 150, "kcal": 1.3},
                {"name": "sebze", "unit": "g", "qty": 200, "kcal": 0.3},
                {"name": "zeytinyagi", "unit": "g", "qty": 10, "kcal": 9},
            ],
            "snack": [
                {"name": "edamame", "unit": "g", "qty": 180, "kcal": 1.2},
                {"name": "elma", "unit": "adet", "qty": 1, "kcal": 95},
                {"name": "badem", "unit": "g", "qty": 20, "kcal": 5.8},
            ],
            "dinner": [
                {"name": "nohut", "unit": "g", "qty": 240, "kcal": 1.64},
                {"name": "bulgur", "unit": "g", "qty": 160, "kcal": 0.83},
                {"name": "salata", "unit": "g", "qty": 150, "kcal": 0.2},
                {"name": "avokado", "unit": "g", "qty": 70, "kcal": 1.6},
            ],
        },
    }

    meal_types = ["breakfast", "snack", "main", "snack", "dinner", "snack"]
    selected_set = food_sets[pref]
    base = []
    alternatives = []

    def item_kcal(item: dict, scale: float) -> int:
        return int(round(item["qty"] * scale * item["kcal"]))

    def scaled_display(item: dict, scale: float) -> str:
        qty = item["qty"] * scale
        if item["unit"] in {"adet", "dilim"}:
            return f"{max(1, int(round(qty)))} {item['unit']}"
        if item["unit"] == "ml":
            return f"{int(round(qty / 10.0) * 10)} ml"
        return f"{int(round(qty / 5.0) * 5)} g"

    for i in range(meals):
        meal_type = meal_types[i]
        items = selected_set[meal_type]
        target_kcal = meal_calories[i]
        base_total = sum(item_kcal(item, 1) for item in items)
        scale = max(0.75, min(1.45, target_kcal / max(base_total, 1)))
        lines = [f"- {item['name'].title()}: {scaled_display(item, scale)} (~{item_kcal(item, scale)} kcal)" for item in items]
        total_kcal = sum(item_kcal(item, scale) for item in items)
        base.append({
            "name": meal_names[i],
            "content": "<br/>".join(lines),
            "portion_hint": f"Hedef: yaklasik {target_kcal} kcal | Ogun toplam: {total_kcal} kcal",
        })

        pool = selected_set["main"] if meal_type in {"main", "dinner"} else selected_set["snack"]
        options = []
        for idx, alt in enumerate(pool[:3], start=1):
            alt_scale = max(0.7, min(1.35, target_kcal / max(item_kcal(alt, 1), 1)))
            options.append(f"Alternatif {idx}: {alt['name'].title()} {scaled_display(alt, alt_scale)} (~{item_kcal(alt, alt_scale)} kcal)")
        alternatives.append({"name": meal_names[i], "options": options})
    return base, alternatives


def supplement_suggestions(profile: sqlite3.Row) -> list[str]:
    goal = profile["goal"]
    pref = profile["diet_preference"]
    notes = [
        "Kreatin monohidrat: gunde 3-5 g, performans ve guc destegi icin dusunulebilir.",
        "Whey / bitkisel protein tozu: protein hedefi tamamlanamiyorsa pratik cozum olabilir.",
        "Omega-3: yagli balik tuketimi dusukse degerlendirilebilir.",
        "Magnezyum: uyku ve toparlanma kalitesi dusukse yararli olabilir.",
    ]
    if pref == "vegan":
        notes.append("Vegan beslenmede B12 destegi ozellikle degerlendirilebilir.")
        notes.append("D vitamini ve demir duzeyleri icin donemsel kontrol dusunulebilir.")
    if goal == "lose":
        notes.append("Kafein, antrenman oncesi enerji ve istah yonetimi icin kontrollu kullanilabilir.")
    if goal == "gain":
        notes.append("Kalori artisi once normal ogunlerle kurulursa surec daha surdurulebilir olur.")
    return notes


def build_plan(profile: sqlite3.Row) -> dict:
    metrics = calculate_metrics(profile)
    meals, alternatives = meal_framework(profile, metrics)
    workouts = workout_split(profile)
    supplements = supplement_suggestions(profile)
    return {
        **metrics,
        "meal_plan": meals,
        "meal_alternatives": alternatives,
        "workout_plan": workouts,
        "supplement_notes": supplements,
        "goal_label": goal_label(profile["goal"]),
    }



def serialize_meals(meals: list[dict]) -> str:
    parts = []
    for meal in meals:
        parts.append(f"{meal['name']}::{meal.get('content', '')}::{meal.get('portion_hint', '')}")
    return "||".join(parts)



def deserialize_meals(raw: str) -> list[dict]:
    items = []
    if not raw:
        return items
    for piece in raw.split("||"):
        seg = piece.split("::")
        items.append({
            "name": seg[0] if len(seg) > 0 else "Ogun",
            "content": seg[1] if len(seg) > 1 else "",
            "portion_hint": seg[2] if len(seg) > 2 else "",
        })
    return items



def serialize_alternatives(items: list[dict]) -> str:
    parts = []
    for item in items:
        parts.append(item["name"] + "::" + "##".join(item["options"]))
    return "||".join(parts)



def deserialize_alternatives(raw: str) -> list[dict]:
    output = []
    if not raw:
        return output
    for piece in raw.split("||"):
        seg = piece.split("::")
        output.append({
            "name": seg[0],
            "options": seg[1].split("##") if len(seg) > 1 else [],
        })
    return output



def serialize_workouts(workouts: list[dict]) -> str:
    parts = []
    for w in workouts:
        parts.append(f"{w['day']}::{w['title']}::{w['focus']}::{'##'.join(w['exercises'])}")
    return "||".join(parts)



def deserialize_workouts(raw: str) -> list[dict]:
    output = []
    if not raw:
        return output
    for piece in raw.split("||"):
        seg = piece.split("::")
        output.append({
            "day": seg[0],
            "title": seg[1] if len(seg) > 1 else "Antrenman",
            "focus": seg[2] if len(seg) > 2 else "",
            "exercises": seg[3].split("##") if len(seg) > 3 else [],
        })
    return output



def serialize_supplements(notes: list[str]) -> str:
    return "||".join(notes)



def deserialize_supplements(raw: str) -> list[str]:
    return raw.split("||") if raw else []



def save_plan(user_id: int, plan: dict) -> int:
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO plans (
            user_id, calorie_target, protein_g, carbs_g, fats_g, bmi, bmr, tdee,
            water_goal_liters, meal_plan, meal_alternatives, workout_plan,
            supplement_notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            plan["calorie_target"],
            plan["protein_g"],
            plan["carbs_g"],
            plan["fats_g"],
            plan["bmi"],
            plan["bmr"],
            plan["tdee"],
            plan["water_goal_liters"],
            serialize_meals(plan["meal_plan"]),
            serialize_alternatives(plan["meal_alternatives"]),
            serialize_workouts(plan["workout_plan"]),
            serialize_supplements(plan["supplement_notes"]),
            now_str(),
        ),
    )
    db.commit()
    return int(cursor.lastrowid)



def fetch_plan(plan_id: int, user_id: int | None = None):
    db = get_db()
    if user_id is None:
        row = db.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    else:
        row = db.execute("SELECT * FROM plans WHERE id = ? AND user_id = ?", (plan_id, user_id)).fetchone()
    if row is None:
        return None
    return {
        **dict(row),
        "meal_plan": deserialize_meals(row["meal_plan"]),
        "meal_alternatives": deserialize_alternatives(row["meal_alternatives"]),
        "workout_plan": deserialize_workouts(row["workout_plan"]),
        "supplement_notes": deserialize_supplements(row["supplement_notes"]),
    }


# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not full_name or not email or not password:
            flash("Tum alanlari doldurman gerekiyor.", "danger")
            return redirect(url_for("register"))

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("Bu e-posta zaten kayitli.", "warning")
            return redirect(url_for("register"))

        db.execute(
            "INSERT INTO users (full_name, email, password_hash, role, created_at) VALUES (?, ?, ?, 'user', ?)",
            (full_name, email, generate_password_hash(password), now_str()),
        )
        db.commit()
        flash("Kayit olusturuldu. Simdi giris yapabilirsin.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("E-posta veya sifre hatali.", "danger")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["full_name"] = user["full_name"]
        if user["role"] == "admin":
            session["client_user_id"] = user["id"]
        flash("Giris basarili.", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Cikis yapildi.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user_id = get_managed_user_id()
    managed_user = get_managed_user()
    profile = get_profile(user_id)
    plans = db.execute(
        "SELECT id, calorie_target, protein_g, carbs_g, fats_g, created_at FROM plans WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    progress = db.execute(
        "SELECT * FROM progress_logs WHERE user_id = ? ORDER BY log_date DESC LIMIT 6",
        (user_id,),
    ).fetchall()
    latest_plan = fetch_plan(plans[0]["id"], user_id) if plans else None
    comparison = None
    if len(progress) >= 2:
        current, previous = progress[0], progress[1]
        def diff(field):
            if current[field] is None or previous[field] is None:
                return None
            return round(float(current[field]) - float(previous[field]), 1)
        comparison = {"weight": diff("weight"), "waist": diff("waist")}
    clients = []
    if session.get("role") == "admin":
        clients = db.execute("SELECT id, full_name, email, role FROM users ORDER BY full_name").fetchall()
    return render_template("dashboard.html", profile=profile, plans=plans, progress=progress, managed_user=managed_user, clients=clients, latest_plan=latest_plan, comparison=comparison)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = get_managed_user_id()
    existing = get_profile(user_id)

    if request.method == "POST":
        upsert_profile(user_id, profile_form_data())
        flash("Profil bilgileri kaydedildi.", "success")
        return redirect(url_for("dashboard"))

    return render_template("profile.html", profile=existing)


@app.route("/generate-plan", methods=["POST"])
@login_required
def generate_plan():
    user_id = get_managed_user_id()
    form_keys = {"age", "gender", "height", "weight", "goal", "activity_level", "experience_level", "workout_days", "equipment", "diet_preference", "meals_per_day"}
    if form_keys.intersection(request.form.keys()):
        upsert_profile(user_id, profile_form_data())

    profile = get_profile(user_id)
    if not profile:
        flash("Once profil bilgilerini doldurmalisin.", "warning")
        return redirect(url_for("dashboard"))

    required_fields = ["age", "gender", "height", "weight", "goal", "activity_level", "experience_level", "workout_days", "equipment", "diet_preference", "meals_per_day"]
    missing = [field for field in required_fields if not profile[field]]
    if missing:
        flash("Plan olusturmak icin profil alanlarini eksiksiz doldurmalisin.", "danger")
        return redirect(url_for("dashboard"))

    plan = build_plan(profile)
    save_plan(user_id, plan)
    flash("Yeni diyet ve fitness programi olusturuldu.", "success")
    return redirect(url_for("dashboard"))


@app.route("/plan/<int:plan_id>")
@login_required
def view_plan(plan_id: int):
    plan = fetch_plan(plan_id, get_managed_user_id())
    if not plan:
        flash("Plan bulunamadi.", "danger")
        return redirect(url_for("dashboard"))
    profile = get_profile(get_managed_user_id())
    return render_template("plan.html", plan=plan, profile=profile)


@app.route("/plan/<int:plan_id>/pdf")
@login_required
def download_plan_pdf(plan_id: int):
    plan = fetch_plan(plan_id, get_managed_user_id())
    if not plan:
        flash("Plan bulunamadi.", "danger")
        return redirect(url_for("dashboard"))
    profile = get_profile(get_managed_user_id())

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Diyet ve Fitness Programi", styles["Title"]))
    story.append(Spacer(1, 12))
    managed_user = get_managed_user()
    story.append(Paragraph(f"Kullanici: {(managed_user['full_name'] if managed_user else session.get('full_name', 'Kullanici'))}", styles["Normal"]))
    story.append(Paragraph(f"Hedef: {goal_label(profile['goal']) if profile else 'Belirtilmedi'}", styles["Normal"]))
    story.append(Paragraph(f"Olusturulma: {plan['created_at']}", styles["Normal"]))
    story.append(Spacer(1, 12))

    summary_lines = [
        f"Kalori hedefi: {plan['calorie_target']} kcal",
        f"Protein: {plan['protein_g']} g",
        f"Karbonhidrat: {plan['carbs_g']} g",
        f"Yag: {plan['fats_g']} g",
        f"BMI: {plan['bmi']}",
        f"Su hedefi: {plan['water_goal_liters']} L",
    ]
    for line in summary_lines:
        story.append(Paragraph(line, styles["BodyText"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Ogun Plani", styles["Heading2"]))
    for meal in plan["meal_plan"]:
        story.append(Paragraph(f"<b>{meal['name']}</b>: {meal['content']}", styles["BodyText"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Antrenman Plani", styles["Heading2"]))
    for workout in plan["workout_plan"]:
        story.append(Paragraph(f"<b>{workout['day']} - {workout['title']}</b>: {workout['focus']}", styles["BodyText"]))
        for ex in workout["exercises"]:
            story.append(Paragraph(f"- {ex}", styles["BodyText"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Supplement Notlari", styles["Heading2"]))
    for note in plan["supplement_notes"]:
        story.append(Paragraph(f"- {note}", styles["BodyText"]))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Bu plan genel bilgilendirme amaclidir; medikal oneri yerine gecmez.", styles["Italic"]))

    doc.build(story)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"plan_{plan_id}.pdf",
        mimetype="application/pdf",
    )


@app.route("/progress", methods=["GET", "POST"])
@login_required
def progress():
    db = get_db()
    user_id = get_managed_user_id()
    if request.method == "POST":
        db.execute(
            """
            INSERT INTO progress_logs (user_id, log_date, weight, waist, chest, hips, arms, thighs, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                request.form.get("log_date") or today_str(),
                request.form.get("weight") or None,
                request.form.get("waist") or None,
                request.form.get("chest") or None,
                request.form.get("hips") or None,
                request.form.get("arms") or None,
                request.form.get("thighs") or None,
                request.form.get("notes") or None,
            ),
        )
        db.commit()
        flash("Haftalik ilerleme kaydi eklendi.", "success")
        return redirect(url_for("progress"))

    logs = db.execute(
        "SELECT * FROM progress_logs WHERE user_id = ? ORDER BY log_date DESC",
        (user_id,),
    ).fetchall()
    latest_two = db.execute(
        "SELECT * FROM progress_logs WHERE user_id = ? ORDER BY log_date DESC LIMIT 2",
        (user_id,),
    ).fetchall()

    comparison = None
    if len(latest_two) == 2:
        current, previous = latest_two[0], latest_two[1]
        def diff(field):
            if current[field] is None or previous[field] is None:
                return None
            return round(float(current[field]) - float(previous[field]), 1)
        comparison = {"weight": diff("weight"), "waist": diff("waist")}

    return render_template("progress.html", logs=logs, comparison=comparison)


@app.route("/history")
@login_required
def history():
    plans = get_db().execute(
        "SELECT id, calorie_target, protein_g, carbs_g, fats_g, created_at FROM plans WHERE user_id = ? ORDER BY id DESC",
        (get_managed_user_id(),),
    ).fetchall()
    return render_template("history.html", plans=plans)




@app.route("/select-client", methods=["POST"])
@login_required
@admin_required
def select_client():
    client_user_id = request.form.get("client_user_id", type=int)
    if not client_user_id:
        flash("Musteri secilemedi.", "warning")
        return redirect(url_for("dashboard"))
    user = get_db().execute("SELECT id, full_name FROM users WHERE id = ?", (client_user_id,)).fetchone()
    if not user:
        flash("Musteri bulunamadi.", "danger")
        return redirect(url_for("dashboard"))
    session["client_user_id"] = user["id"]
    flash(f"Aktif musteri: {user['full_name']}", "success")
    return redirect(url_for("dashboard"))


@app.route("/quick-create-client", methods=["POST"])
@login_required
@admin_required
def quick_create_client():
    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    phone_token = (request.form.get("phone_token") or "").strip()

    if not full_name:
        flash("Yeni musteri icin ad soyad gerekli.", "warning")
        return redirect(url_for("dashboard"))

    db = get_db()
    if email:
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            session["client_user_id"] = existing["id"]
            flash("Bu e-posta zaten kayitli. Mevcut musteri secildi.", "info")
            return redirect(url_for("dashboard"))
    else:
        base = ''.join(ch.lower() for ch in full_name if ch.isalnum())[:18] or 'musteri'
        email = f"{base}_{int(datetime.now().timestamp())}@localclient.test"

    password_seed = phone_token or "123456"
    db.execute(
        "INSERT INTO users (full_name, email, password_hash, role, created_at) VALUES (?, ?, ?, 'user', ?)",
        (full_name, email, generate_password_hash(password_seed), now_str()),
    )
    db.commit()
    new_id = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
    session["client_user_id"] = new_id
    flash(f"Yeni musteri olusturuldu: {full_name}", "success")
    return redirect(url_for("dashboard"))
@app.route("/admin")
@login_required
@admin_required
def admin_panel():
    db = get_db()
    users = db.execute(
        """
        SELECT u.id, u.full_name, u.email, u.role, u.created_at,
               (SELECT COUNT(*) FROM plans p WHERE p.user_id = u.id) AS plan_count,
               (SELECT COUNT(*) FROM progress_logs pr WHERE pr.user_id = u.id) AS progress_count
        FROM users u
        ORDER BY u.id DESC
        """
    ).fetchall()
    return render_template("admin.html", users=users)


@app.context_processor
def inject_globals():
    return {"current_user": get_current_user()}


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="127.0.0.1", port=5001, debug=True)
