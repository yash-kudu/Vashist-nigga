"""
NutriHealth - Nutrition & Health Tracking App for Community Use
-----------------------------------------------------------------
A traditional server-rendered Flask application:
  - Flask handles routing (URLs -> Python functions)
  - Jinja2 templates (in templates/) render the actual HTML
  - SQLite (nutrition.db) stores users, food logs, health metrics,
    daily hydration/steps, and community posts
  - werkzeug.security hashes passwords -- we never store raw passwords

Every page is rendered on the server and sent as complete HTML.
Forms submit with a normal POST request and the page reloads --
this is the "traditional" pattern taught in most web dev courses,
as opposed to a single-page app that talks to a JSON API.
"""

import os
import re
import sqlite3
from datetime import date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# The secret key is used by Flask to cryptographically sign the
# session cookie, so users can't tamper with it. In a real deployment
# this should come from an environment variable, not be hardcoded.
app.secret_key = "replace-this-with-a-random-secret-key-before-deploying"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "nutrition.db")

STEPS_GOAL = 10000
WATER_GOAL = 8  # glasses

# ==========================================================
# Food database
# ==========================================================
# A master list of common foods with nutrition values already
# filled in ("verified" = pulled from standard nutrition
# references, not user guesses). This single list now powers
# three things:
#   1. The Quick-Add buttons on the dashboard (quick_add: True)
#   2. The live food-name search box on the Log Food page
#   3. The rule-based chatbot's food-logging + food-lookup replies
# "keywords" are the words/phrases someone might type or say for
# that food -- used for both the search box and the chatbot's
# text matching, so plurals and common nicknames are included.
FOOD_DB = [
    {"key": "banana",        "name": "Banana",                "keywords": ["banana", "bananas"],                              "meal_type": "Snack",     "calories": 105, "protein": 1,  "carbs": 27, "fats": 0,  "quick_add": True},
    {"key": "boiled_egg",    "name": "Boiled Egg",             "keywords": ["boiled egg", "boiled eggs", "egg", "eggs"],       "meal_type": "Breakfast", "calories": 78,  "protein": 6,  "carbs": 1,  "fats": 5,  "quick_add": True},
    {"key": "greek_yogurt",  "name": "Greek Yogurt Cup",       "keywords": ["greek yogurt", "yogurt", "curd"],                 "meal_type": "Snack",     "calories": 100, "protein": 17, "carbs": 6,  "fats": 0,  "quick_add": True},
    {"key": "grilled_chix",  "name": "Grilled Chicken Breast", "keywords": ["grilled chicken", "chicken breast", "chicken"],   "meal_type": "Lunch",     "calories": 165, "protein": 31, "carbs": 0,  "fats": 4,  "quick_add": True},
    {"key": "apple",         "name": "Apple",                  "keywords": ["apple", "apples"],                                "meal_type": "Snack",     "calories": 95,  "protein": 0,  "carbs": 25, "fats": 0,  "quick_add": True},
    {"key": "protein_shake", "name": "Protein Shake",          "keywords": ["protein shake", "whey shake", "whey protein"],    "meal_type": "Snack",     "calories": 150, "protein": 25, "carbs": 5,  "fats": 3,  "quick_add": True},
    {"key": "roti",          "name": "Roti",                   "keywords": ["roti", "rotis", "chapati", "chapatti"],           "meal_type": "Lunch",     "calories": 85,  "protein": 3,  "carbs": 18, "fats": 0.4},
    {"key": "dal",           "name": "Dal Tadka",               "keywords": ["dal tadka", "dal", "daal", "lentils"],           "meal_type": "Lunch",     "calories": 180, "protein": 9,  "carbs": 26, "fats": 5},
    {"key": "rice",          "name": "Steamed Rice",            "keywords": ["rice", "steamed rice", "white rice"],            "meal_type": "Lunch",     "calories": 205, "protein": 4,  "carbs": 45, "fats": 0.4},
    {"key": "paneer_bhurji", "name": "Paneer Bhurji",           "keywords": ["paneer bhurji", "paneer"],                       "meal_type": "Dinner",    "calories": 265, "protein": 14, "carbs": 6,  "fats": 20},
    {"key": "toast",         "name": "Toast",                   "keywords": ["toast", "slice of toast", "bread"],              "meal_type": "Breakfast", "calories": 75,  "protein": 3,  "carbs": 13, "fats": 1},
    {"key": "oats",          "name": "Oatmeal",                 "keywords": ["oats", "oatmeal", "porridge"],                   "meal_type": "Breakfast", "calories": 150, "protein": 5,  "carbs": 27, "fats": 3},
    {"key": "milk",          "name": "Milk (1 cup)",            "keywords": ["milk", "glass of milk"],                         "meal_type": "Breakfast", "calories": 122, "protein": 8,  "carbs": 12, "fats": 5},
    {"key": "tea",           "name": "Tea",                     "keywords": ["tea", "chai"],                                   "meal_type": "Snack",     "calories": 40,  "protein": 1,  "carbs": 5,  "fats": 1.5},
    {"key": "coffee",        "name": "Coffee",                  "keywords": ["coffee", "black coffee"],                        "meal_type": "Snack",     "calories": 5,   "protein": 0,  "carbs": 1,  "fats": 0},
    {"key": "idli",          "name": "Idli",                    "keywords": ["idli", "idlis"],                                 "meal_type": "Breakfast", "calories": 39,  "protein": 2,  "carbs": 8,  "fats": 0.2},
    {"key": "dosa",          "name": "Dosa",                    "keywords": ["dosa", "dosas"],                                 "meal_type": "Breakfast", "calories": 133, "protein": 4,  "carbs": 19, "fats": 4},
    {"key": "samosa",        "name": "Samosa",                  "keywords": ["samosa", "samosas"],                             "meal_type": "Snack",     "calories": 262, "protein": 4,  "carbs": 24, "fats": 17},
    {"key": "almonds",       "name": "Almonds (10)",            "keywords": ["almonds", "badam"],                              "meal_type": "Snack",     "calories": 70,  "protein": 3,  "carbs": 3,  "fats": 6},
    {"key": "peanut_butter", "name": "Peanut Butter (1 tbsp)",  "keywords": ["peanut butter", "pb"],                           "meal_type": "Snack",     "calories": 95,  "protein": 4,  "carbs": 3,  "fats": 8},
    {"key": "orange",        "name": "Orange",                  "keywords": ["orange", "oranges"],                             "meal_type": "Snack",     "calories": 62,  "protein": 1,  "carbs": 15, "fats": 0},
    {"key": "salad",         "name": "Mixed Veg Salad",         "keywords": ["salad", "veg salad"],                            "meal_type": "Lunch",     "calories": 50,  "protein": 2,  "carbs": 10, "fats": 0.5},
    {"key": "chicken_curry", "name": "Chicken Curry",           "keywords": ["chicken curry"],                                 "meal_type": "Dinner",    "calories": 285, "protein": 25, "carbs": 8,  "fats": 17},
    {"key": "paratha",       "name": "Paratha",                 "keywords": ["paratha", "parantha"],                           "meal_type": "Breakfast", "calories": 210, "protein": 4,  "carbs": 27, "fats": 10},
    {"key": "poha",          "name": "Poha",                    "keywords": ["poha"],                                          "meal_type": "Breakfast", "calories": 180, "protein": 4,  "carbs": 30, "fats": 5},
    {"key": "upma",          "name": "Upma",                    "keywords": ["upma"],                                          "meal_type": "Breakfast", "calories": 192, "protein": 5,  "carbs": 26, "fats": 8},
    {"key": "cheese_slice",  "name": "Cheese Slice",            "keywords": ["cheese slice", "cheese"],                        "meal_type": "Snack",     "calories": 70,  "protein": 4,  "carbs": 1,  "fats": 6},
    {"key": "ice_cream",     "name": "Ice Cream (1 scoop)",     "keywords": ["ice cream"],                                     "meal_type": "Snack",     "calories": 137, "protein": 2,  "carbs": 16, "fats": 7},
    {"key": "chocolate",     "name": "Chocolate Bar",           "keywords": ["chocolate bar", "chocolate"],                    "meal_type": "Snack",     "calories": 235, "protein": 3,  "carbs": 26, "fats": 13},
    {"key": "fries",         "name": "French Fries (small)",    "keywords": ["french fries", "fries"],                         "meal_type": "Snack",     "calories": 220, "protein": 3,  "carbs": 26, "fats": 11},
    {"key": "pizza",         "name": "Pizza Slice",             "keywords": ["pizza slice", "pizza"],                          "meal_type": "Dinner",    "calories": 285, "protein": 12, "carbs": 36, "fats": 10},
    {"key": "burger",        "name": "Burger",                  "keywords": ["burger", "hamburger"],                          "meal_type": "Dinner",    "calories": 350, "protein": 17, "carbs": 33, "fats": 17},
    {"key": "sandwich",      "name": "Sandwich",                "keywords": ["sandwich"],                                      "meal_type": "Lunch",     "calories": 250, "protein": 10, "carbs": 30, "fats": 9},
    {"key": "pasta",         "name": "Pasta",                   "keywords": ["pasta"],                                         "meal_type": "Dinner",    "calories": 220, "protein": 8,  "carbs": 43, "fats": 1.3},
    {"key": "watermelon",    "name": "Watermelon (1 cup)",      "keywords": ["watermelon"],                                    "meal_type": "Snack",     "calories": 46,  "protein": 1,  "carbs": 12, "fats": 0.2},
    {"key": "mango",         "name": "Mango",                   "keywords": ["mango", "mangoes"],                              "meal_type": "Snack",     "calories": 99,  "protein": 1,  "carbs": 25, "fats": 0.6},
    {"key": "cucumber",      "name": "Cucumber",                "keywords": ["cucumber"],                                      "meal_type": "Snack",     "calories": 16,  "protein": 1,  "carbs": 4,  "fats": 0},
    {"key": "boiled_potato", "name": "Boiled Potato",           "keywords": ["boiled potato", "potato", "aloo"],               "meal_type": "Lunch",     "calories": 87,  "protein": 2,  "carbs": 20, "fats": 0.1},
    {"key": "omelette",      "name": "Omelette (2 eggs)",       "keywords": ["omelette", "omelet"],                            "meal_type": "Breakfast", "calories": 190, "protein": 13, "carbs": 2,  "fats": 15},
]

# The Quick-Add panel is just the subset of FOOD_DB flagged
# quick_add: True, in the order they appear above.
QUICK_ADD_FOODS = [food for food in FOOD_DB if food.get("quick_add")]


# ==========================================================
# Database helpers
# ==========================================================

def get_db():
    """
    Return the database connection for the current request.
    Flask's 'g' object is a per-request storage bucket, so we only
    open one connection per request no matter how many times
    get_db() is called during that request.
    """
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row  # lets us access columns by name, e.g. row["username"]
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """Flask calls this automatically after every request finishes."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the tables from schema.sql if they don't exist yet."""
    with app.app_context():
        db = get_db()
        with open(os.path.join(BASE_DIR, "schema.sql")) as f:
            db.executescript(f.read())
        db.commit()


def get_or_create_daily_log(db, user_id, log_date):
    """
    Every user gets exactly one daily_logs row per day (hydration +
    steps). If today's row doesn't exist yet, create it with zeros
    before returning it, so callers never have to handle "no row yet"
    as a special case.
    """
    row = db.execute(
        "SELECT * FROM daily_logs WHERE user_id = ? AND log_date = ?",
        (user_id, log_date)
    ).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO daily_logs (user_id, log_date, water_glasses, steps) VALUES (?, ?, 0, 0)",
            (user_id, log_date)
        )
        db.commit()
        row = db.execute(
            "SELECT * FROM daily_logs WHERE user_id = ? AND log_date = ?",
            (user_id, log_date)
        ).fetchone()
    return row


def calculate_wellness_score(total_calories, calorie_goal, water_glasses, steps):
    """
    A simple 0-100 composite score blending three habits:
      - up to 40 points for how close today's calories are to goal
        (both under-eating and over-eating pull this down)
      - up to 30 points for hydration progress toward WATER_GOAL
      - up to 30 points for step progress toward STEPS_GOAL
    This is a teaching-friendly formula, not a clinical metric --
    worth saying so out loud if asked in a viva.
    """
    if calorie_goal > 0:
        calorie_diff_ratio = abs(total_calories - calorie_goal) / calorie_goal
        calorie_points = max(0, 40 - round(calorie_diff_ratio * 40))
    else:
        calorie_points = 0

    water_points = min(30, round((water_glasses / WATER_GOAL) * 30))
    step_points = min(30, round((steps / STEPS_GOAL) * 30))

    return min(100, calorie_points + water_points + step_points)


def compute_dashboard_stats(db, user_id, user):
    """
    Everything the dashboard needs about "today", in one place.
    Pulled out into its own function so the dashboard route and the
    chatbot (which needs to answer "how many calories do I have
    left?") can both call it instead of duplicating the math.
    """
    today = date.today().isoformat()

    todays_logs = db.execute(
        "SELECT * FROM food_logs WHERE user_id = ? AND log_date = ? ORDER BY id DESC",
        (user_id, today)
    ).fetchall()

    total_calories = sum(row["calories"] for row in todays_logs)
    total_protein = sum(row["protein"] for row in todays_logs)
    total_carbs = sum(row["carbs"] for row in todays_logs)
    total_fats = sum(row["fats"] for row in todays_logs)

    macro_gram_total = total_protein + total_carbs + total_fats
    if macro_gram_total > 0:
        protein_pct = round((total_protein / macro_gram_total) * 100)
        carbs_pct = round((total_carbs / macro_gram_total) * 100)
        fats_pct = 100 - protein_pct - carbs_pct
    else:
        protein_pct = carbs_pct = fats_pct = 0

    calorie_goal = user["calorie_goal"] or 2000
    remaining_calories = max(0, calorie_goal - total_calories)
    calorie_progress_pct = min(100, round((total_calories / calorie_goal) * 100)) if calorie_goal else 0

    daily_log = get_or_create_daily_log(db, user_id, today)
    water_glasses = daily_log["water_glasses"]
    steps = daily_log["steps"]
    water_pct = min(100, round((water_glasses / WATER_GOAL) * 100))
    steps_pct = min(100, round((steps / STEPS_GOAL) * 100))

    wellness_score = calculate_wellness_score(total_calories, calorie_goal, water_glasses, steps)

    return {
        "today": today,
        "todays_logs": todays_logs,
        "total_calories": total_calories,
        "total_protein": round(total_protein),
        "total_carbs": round(total_carbs),
        "total_fats": round(total_fats),
        "protein_pct": protein_pct,
        "carbs_pct": carbs_pct,
        "fats_pct": fats_pct,
        "calorie_goal": calorie_goal,
        "remaining_calories": remaining_calories,
        "calorie_progress_pct": calorie_progress_pct,
        "meals_logged_today": len(todays_logs),
        "water_glasses": water_glasses,
        "water_goal": WATER_GOAL,
        "water_pct": water_pct,
        "steps": steps,
        "steps_goal": STEPS_GOAL,
        "steps_pct": steps_pct,
        "wellness_score": wellness_score,
    }


def insert_food_log(db, user_id, food, qty, meal_type=None, log_date=None):
    """
    Insert one food_logs row for `qty` servings of a FOOD_DB entry.
    Shared by the quick-add buttons and the chatbot's food-logging
    replies, so both scale macros the same way and can't drift apart.
    """
    log_date = log_date or date.today().isoformat()
    meal_type = meal_type or food["meal_type"]
    calories = round(food["calories"] * qty)
    protein = round(food["protein"] * qty, 1)
    carbs = round(food["carbs"] * qty, 1)
    fats = round(food["fats"] * qty, 1)
    db.execute(
        """INSERT INTO food_logs (user_id, food_name, meal_type, calories, protein, carbs, fats, log_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, food["name"], meal_type, calories, protein, carbs, fats, log_date)
    )
    return {"name": food["name"], "qty": qty, "calories": calories, "meal_type": meal_type}


# ==========================================================
# Ragbot -- rule-based chat assistant (no external AI API)
# ==========================================================
# "Rule-based RAG" here means retrieval, not generation: every
# reply is built by *retrieving* facts straight from FOOD_DB or
# the user's own rows in the database and slotting them into a
# canned sentence. There is no language model involved, so it can
# only recognize the patterns coded below -- it's a fast, offline
# assistant, not a general chatbot.

NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "couple": 2, "few": 3, "some": 2,
}

GREETING_RE = re.compile(r"^\s*(hi+|hello+|hey+|yo|good\s?(morning|afternoon|evening))[\s!.,]*$", re.I)
HELP_RE = re.compile(r"\b(help|what can you do|commands|options)\b", re.I)
LOG_INTENT_RE = re.compile(r"\b(ate|eaten|eat|had|have|log(ged)?|add(ed|ing)?|consumed|drank|drink|finished)\b", re.I)
QUESTION_RE = re.compile(r"[?]|^\s*(how|what|when|where|why|calories? in)\b", re.I)
MEAL_TYPE_RE = re.compile(r"\b(breakfast|lunch|dinner|snack)\b", re.I)

# Longest keyword first, so "greek yogurt" matches before the
# generic "yogurt" and "boiled egg" before plain "egg".
_KEYWORD_INDEX = sorted(
    ((kw, food) for food in FOOD_DB for kw in food["keywords"]),
    key=lambda pair: -len(pair[0])
)


def find_food_mentions(text):
    """
    Scan `text` for FOOD_DB keywords and return a list of
    {"food": ..., "qty": ...} in the order they appear. A keyword
    already claimed by a longer match is skipped, so "greek yogurt"
    doesn't also register a second, overlapping "yogurt" hit.
    """
    claimed = []  # list of (start, end) spans already matched
    hits = []
    for keyword, food in _KEYWORD_INDEX:
        for m in re.finditer(r"\b" + re.escape(keyword) + r"\b", text):
            start, end = m.span()
            if any(start < c_end and end > c_start for c_start, c_end in claimed):
                continue
            claimed.append((start, end))

            qty = 1
            preceding_words = text[max(0, start - 20):start].split()
            if preceding_words:
                last_word = preceding_words[-1].strip(",.")
                if last_word.isdigit():
                    qty = int(last_word)
                elif last_word in NUMBER_WORDS:
                    qty = NUMBER_WORDS[last_word]

            hits.append({"food": food, "qty": qty, "start": start})

    hits.sort(key=lambda h: h["start"])
    return hits


def build_chat_reply(db, user, message):
    """
    The chatbot's entire brain. Returns (reply_text, logged_items).
    logged_items is a non-empty list only when food rows were
    actually inserted, so the caller knows whether to refresh stats.
    """
    text = (message or "").strip()
    lower = text.lower()

    if not text:
        return "Say something and I'll try to help -- try \"I ate a banana and 2 eggs\".", []

    if GREETING_RE.match(lower):
        return (f"Hi {user['username']}! You can tell me what you ate "
                f"(\"I had 2 rotis and dal for lunch\"), or ask about your "
                f"stats (\"how many calories do I have left?\")."), []

    if HELP_RE.search(lower):
        return ("Here's what I can do:\n"
                "- Log food: \"I ate a banana and 2 boiled eggs\"\n"
                "- Look up a food: \"calories in paneer bhurji?\"\n"
                "- Check your stats: \"how much water have I had?\", "
                "\"what's my wellness score?\", \"calories left today?\"\n"
                "I only know the foods in NutriHealth's database, and I "
                "don't use any external AI -- everything I say comes "
                "straight from your logged data."), []

    stats = compute_dashboard_stats(db, user["id"], user)

    if re.search(r"\bwater|hydration|glass(es)?\b", lower):
        return (f"You've had {stats['water_glasses']} of {stats['water_goal']} "
                f"glasses of water today ({stats['water_pct']}%)."), []

    if re.search(r"\bstep(s)?|walk(ed|ing)?\b", lower):
        return (f"You're at {stats['steps']:,} of {stats['steps_goal']:,} "
                f"steps today ({stats['steps_pct']}%)."), []

    if re.search(r"\bwellness\b", lower):
        return f"Your wellness score today is {stats['wellness_score']} out of 100.", []

    if re.search(r"\b(calorie|calories)\b.*\b(left|remain)|remain.*calorie", lower):
        return (f"You have {stats['remaining_calories']} kcal remaining "
                f"out of your {stats['calorie_goal']} kcal goal "
                f"({stats['total_calories']} kcal logged so far)."), []

    if re.search(r"\bcalorie goal\b", lower):
        return f"Your daily calorie goal is set to {stats['calorie_goal']} kcal.", []

    if re.search(r"\bbmi\b", lower):
        latest = db.execute(
            "SELECT * FROM health_metrics WHERE user_id = ? ORDER BY log_date DESC, id DESC LIMIT 1",
            (user["id"],)
        ).fetchone()
        if latest:
            return f"Your most recent BMI is {latest['bmi']} (logged {latest['log_date']}).", []
        return "You haven't logged a weight/height entry yet -- add one on the Health Metrics page to get your BMI.", []

    mentions = find_food_mentions(lower)

    if mentions and QUESTION_RE.search(lower) and not LOG_INTENT_RE.search(lower):
        # Informational lookup, e.g. "calories in 2 rotis?" -- don't log it.
        lines = []
        for hit in mentions:
            food, qty = hit["food"], hit["qty"]
            lines.append(
                f"{qty}x {food['name']}: {round(food['calories']*qty)} kcal, "
                f"{round(food['protein']*qty,1)}g protein, "
                f"{round(food['carbs']*qty,1)}g carbs, {round(food['fats']*qty,1)}g fat"
            )
        return "\n".join(lines), []

    if mentions:
        meal_match = MEAL_TYPE_RE.search(lower)
        meal_type = meal_match.group(1).capitalize() if meal_match else None
        logged = [insert_food_log(db, user["id"], hit["food"], hit["qty"], meal_type=meal_type) for hit in mentions]
        db.commit()
        summary = ", ".join(f"{item['qty']}x {item['name']}" for item in logged)
        total_kcal = sum(item["calories"] for item in logged)
        return f"Logged {summary} ({total_kcal} kcal). Nice work!", logged

    return ("I didn't catch a food I know or a question I can answer. "
            "Try \"I ate a banana\" or \"help\" to see what I can do."), []


# ==========================================================
# Authentication helper
# ==========================================================

def login_required(view_function):
    """
    A decorator we put above any route that should only be visible
    to logged-in users. It checks the session for a user_id; if it's
    missing, it bounces the visitor to the login page instead.
    """
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)
    return wrapped_view


# ==========================================================
# Routes: Home / Auth
# ==========================================================

@app.route("/")
def index():
    """Landing route: send logged-in users to their dashboard, others to login."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # --- Server-side validation ---
        # Client-side JS checks these too (for instant feedback), but
        # we NEVER trust the browser alone -- a user can disable JS or
        # send a request directly, so the server must re-check everything.
        error = None
        if not username or not email or not password:
            error = "All fields are required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters long."
        elif password != confirm_password:
            error = "Passwords do not match."

        if error is None:
            db = get_db()
            existing = db.execute(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (username, email)
            ).fetchone()
            if existing is not None:
                error = "That username or email is already registered."

        if error:
            flash(error, "error")
            return render_template("register.html", username=username, email=email)

        # Hash the password before storing it -- generate_password_hash()
        # produces a salted hash, so even if the database leaked, the
        # original passwords could not be read back out.
        password_hash = generate_password_hash(password)
        db = get_db()
        db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash)
        )
        db.commit()

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        # check_password_hash() re-hashes the submitted password with the
        # same salt and compares it to the stored hash -- the only way
        # to verify a password without ever storing it in plain text.
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect username or password.", "error")
            return render_template("login.html", username=username)

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ==========================================================
# Routes: Dashboard
# ==========================================================

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user_id = session["user_id"]

    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    stats = compute_dashboard_stats(db, user_id, user)

    recent_logs = db.execute(
        "SELECT * FROM food_logs WHERE user_id = ? ORDER BY log_date DESC, id DESC LIMIT 6",
        (user_id,)
    ).fetchall()

    latest_metric = db.execute(
        "SELECT * FROM health_metrics WHERE user_id = ? ORDER BY log_date DESC, id DESC LIMIT 1",
        (user_id,)
    ).fetchone()

    # --- Community preview: latest 3 posts ---
    community_preview = db.execute(
        "SELECT * FROM community_posts ORDER BY id DESC LIMIT 3"
    ).fetchall()

    return render_template(
        "dashboard.html",
        user=user,
        recent_logs=recent_logs,
        latest_metric=latest_metric,
        quick_add_foods=QUICK_ADD_FOODS,
        community_preview=community_preview,
        **stats
    )


# ==========================================================
# Routes: Food logging
# ==========================================================

@app.route("/log-food", methods=["GET", "POST"])
@login_required
def log_food():
    today = date.today().isoformat()

    if request.method == "POST":
        food_name = request.form.get("food_name", "").strip()
        meal_type = request.form.get("meal_type", "")
        calories = request.form.get("calories", type=int)
        protein = request.form.get("protein", type=float) or 0
        carbs = request.form.get("carbs", type=float) or 0
        fats = request.form.get("fats", type=float) or 0
        log_date = request.form.get("log_date") or today

        if not food_name or calories is None or meal_type not in ("Breakfast", "Lunch", "Dinner", "Snack"):
            flash("Please fill in the food name, meal type, and calories correctly.", "error")
            return render_template("log_food.html", today=today)

        db = get_db()
        db.execute(
            """INSERT INTO food_logs (user_id, food_name, meal_type, calories, protein, carbs, fats, log_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session["user_id"], food_name, meal_type, calories, protein, carbs, fats, log_date)
        )
        db.commit()
        flash(f'"{food_name}" was added to your log.', "success")
        return redirect(url_for("dashboard"))

    return render_template("log_food.html", today=today)


@app.route("/quick-add-food", methods=["POST"])
@login_required
def quick_add_food():
    """
    Handles the one-click buttons in the 'Quick-Add Verified Foods'
    panel on the dashboard. Each button submits the food's 'key' and
    we look up its pre-filled nutrition values from QUICK_ADD_FOODS,
    rather than trusting calorie/macro numbers from the request --
    otherwise someone could tamper with the hidden form values.
    """
    food_key = request.form.get("food_key")
    food = next((f for f in QUICK_ADD_FOODS if f["key"] == food_key), None)

    if food is None:
        flash("That quick-add food wasn't recognized.", "error")
        return redirect(url_for("dashboard"))

    db = get_db()
    db.execute(
        """INSERT INTO food_logs (user_id, food_name, meal_type, calories, protein, carbs, fats, log_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session["user_id"], food["name"], food["meal_type"], food["calories"],
         food["protein"], food["carbs"], food["fats"], date.today().isoformat())
    )
    db.commit()
    flash(f'"{food["name"]}" was added to your log.', "success")
    return redirect(url_for("dashboard"))


@app.route("/food-history")
@login_required
def food_history():
    db = get_db()
    logs = db.execute(
        "SELECT * FROM food_logs WHERE user_id = ? ORDER BY log_date DESC, id DESC",
        (session["user_id"],)
    ).fetchall()
    return render_template("food_history.html", logs=logs)


@app.route("/delete-food/<int:food_id>", methods=["POST"])
@login_required
def delete_food(food_id):
    db = get_db()
    # The "AND user_id = ?" check matters: without it, a user could
    # delete another user's entry just by guessing an id in the URL.
    db.execute(
        "DELETE FROM food_logs WHERE id = ? AND user_id = ?",
        (food_id, session["user_id"])
    )
    db.commit()
    flash("Entry deleted.", "success")
    return redirect(request.referrer or url_for("food_history"))


# ==========================================================
# Routes: JSON APIs (live search + chatbot)
# ==========================================================

@app.route("/api/foods/search")
@login_required
def api_food_search():
    """
    Powers the live-search dropdown on the Log Food page. Matches
    the query against FOOD_DB names/keywords and returns full
    nutrition info so the frontend can auto-fill the form fields.
    """
    query = request.args.get("q", "").strip().lower()
    if not query:
        return jsonify([])

    results = []
    for food in FOOD_DB:
        haystacks = [food["name"].lower()] + food["keywords"]
        if any(query in h or h in query for h in haystacks):
            results.append({
                "key": food["key"],
                "name": food["name"],
                "meal_type": food["meal_type"],
                "calories": food["calories"],
                "protein": food["protein"],
                "carbs": food["carbs"],
                "fats": food["fats"],
            })
        if len(results) >= 8:
            break

    return jsonify(results)


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    """
    The ragbot endpoint. Takes {"message": "..."} and returns
    {"reply": "...", "logged": bool} so the frontend knows whether
    to refresh the page's stats after a food-logging reply.
    """
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    message = (request.get_json(silent=True) or {}).get("message", "")

    reply, logged_items = build_chat_reply(db, user, message)
    return jsonify({"reply": reply, "logged": bool(logged_items)})


# ==========================================================
# Routes: Hydration + Daily Activity (steps)
# ==========================================================

@app.route("/hydration/update", methods=["POST"])
@login_required
def update_hydration():
    """+1 / -1 glass of water for today. Clamped between 0 and 16."""
    db = get_db()
    today = date.today().isoformat()
    daily_log = get_or_create_daily_log(db, session["user_id"], today)

    action = request.form.get("action")
    new_count = daily_log["water_glasses"] + (1 if action == "add" else -1)
    new_count = max(0, min(16, new_count))

    db.execute(
        "UPDATE daily_logs SET water_glasses = ? WHERE user_id = ? AND log_date = ?",
        (new_count, session["user_id"], today)
    )
    db.commit()
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/activity/add-steps", methods=["POST"])
@login_required
def add_steps():
    """Adds a batch of steps (e.g. +500 / +1000) to today's total."""
    db = get_db()
    today = date.today().isoformat()
    daily_log = get_or_create_daily_log(db, session["user_id"], today)

    amount = request.form.get("amount", type=int) or 0
    if amount > 0:
        new_total = daily_log["steps"] + amount
        db.execute(
            "UPDATE daily_logs SET steps = ? WHERE user_id = ? AND log_date = ?",
            (new_total, session["user_id"], today)
        )
        db.commit()
        flash(f"Added {amount} steps.", "success")

    return redirect(request.referrer or url_for("dashboard"))


# ==========================================================
# Routes: Health metrics (weight / height / BMI)
# ==========================================================

@app.route("/health-metrics", methods=["GET", "POST"])
@login_required
def health_metrics():
    db = get_db()
    today = date.today().isoformat()

    if request.method == "POST":
        weight = request.form.get("weight", type=float)
        height = request.form.get("height", type=float)
        log_date = request.form.get("log_date") or today

        if not weight or not height or weight <= 0 or height <= 0:
            flash("Please enter a valid weight and height.", "error")
        else:
            height_m = height / 100
            bmi = round(weight / (height_m ** 2), 1)
            db.execute(
                """INSERT INTO health_metrics (user_id, weight_kg, height_cm, bmi, log_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (session["user_id"], weight, height, bmi, log_date)
            )
            db.commit()
            flash(f"Saved. Your BMI is {bmi}.", "success")
        return redirect(url_for("health_metrics"))

    history = db.execute(
        "SELECT * FROM health_metrics WHERE user_id = ? ORDER BY log_date DESC, id DESC",
        (session["user_id"],)
    ).fetchall()
    return render_template("health_metrics.html", history=history, today=today)


# ==========================================================
# Routes: Community
# ==========================================================

@app.route("/community")
@login_required
def community():
    db = get_db()
    user_id = session["user_id"]
    today = date.today().isoformat()

    filter_tag = request.args.get("filter", "all")
    if filter_tag == "challenge":
        posts = db.execute(
            "SELECT * FROM community_posts WHERE tag = 'challenge' ORDER BY id DESC"
        ).fetchall()
    else:
        posts = db.execute("SELECT * FROM community_posts ORDER BY id DESC").fetchall()

    # Challenge progress uses the SAME live data as the dashboard --
    # there's no separate "challenge tracking" table. Progress bars
    # update automatically the moment you log water, steps, or food,
    # which is what the "Auto-Sync" label refers to.
    daily_log = get_or_create_daily_log(db, user_id, today)
    meals_today = db.execute(
        "SELECT COUNT(*) AS c FROM food_logs WHERE user_id = ? AND log_date = ?",
        (user_id, today)
    ).fetchone()["c"]

    challenges = [
        {
            "title": "Hydration Hero",
            "description": f"Drink {WATER_GOAL} glasses of water today.",
            "current": daily_log["water_glasses"],
            "target": WATER_GOAL,
            "pct": min(100, round((daily_log["water_glasses"] / WATER_GOAL) * 100)),
            "unit": "glasses",
        },
        {
            "title": "10K Steps",
            "description": f"Reach {STEPS_GOAL:,} steps today.",
            "current": daily_log["steps"],
            "target": STEPS_GOAL,
            "pct": min(100, round((daily_log["steps"] / STEPS_GOAL) * 100)),
            "unit": "steps",
        },
        {
            "title": "Balanced Plate",
            "description": "Log 3 meals today.",
            "current": meals_today,
            "target": 3,
            "pct": min(100, round((meals_today / 3) * 100)),
            "unit": "meals",
        },
    ]

    return render_template(
        "community.html",
        posts=posts,
        challenges=challenges,
        filter_tag=filter_tag
    )


@app.route("/community/post", methods=["POST"])
@login_required
def community_post():
    content = request.form.get("content", "").strip()
    tag = request.form.get("tag", "general")
    if tag not in ("general", "challenge"):
        tag = "general"

    if not content:
        flash("Write something before posting.", "error")
        return redirect(url_for("community"))

    db = get_db()
    db.execute(
        "INSERT INTO community_posts (user_id, author, content, tag) VALUES (?, ?, ?, ?)",
        (session["user_id"], session["username"], content, tag)
    )
    db.commit()
    flash("Posted to the community feed.", "success")
    return redirect(url_for("community"))


@app.route("/community/like/<int:post_id>", methods=["POST"])
@login_required
def like_post(post_id):
    db = get_db()
    db.execute("UPDATE community_posts SET likes = likes + 1 WHERE id = ?", (post_id,))
    db.commit()
    return redirect(request.referrer or url_for("community"))


# ==========================================================
# Routes: Profile
# ==========================================================

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()

    if request.method == "POST":
        calorie_goal = request.form.get("calorie_goal", type=int)
        if calorie_goal and calorie_goal > 0:
            db.execute(
                "UPDATE users SET calorie_goal = ? WHERE id = ?",
                (calorie_goal, session["user_id"])
            )
            db.commit()
            flash("Calorie goal updated.", "success")
        else:
            flash("Please enter a valid calorie goal.", "error")
        return redirect(url_for("profile"))

    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    return render_template("profile.html", user=user)


# ==========================================================
# Entry point
# ==========================================================

if __name__ == "__main__":
    init_db()  # safe to call every time -- uses CREATE TABLE IF NOT EXISTS
    print("NutriHealth running at http://127.0.0.1:5000")
    app.run(debug=True)
