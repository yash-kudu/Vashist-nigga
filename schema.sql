-- ==========================================================
-- NutriHealth Database Schema
-- This file is run once automatically by app.py to create
-- the tables if they don't already exist.
-- ==========================================================

-- Every registered person. Passwords are NEVER stored in plain
-- text -- only a one-way hash (see app.py, generate_password_hash).
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    calorie_goal  INTEGER DEFAULT 2000,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- One row per food item a user logs. user_id links each entry
-- back to exactly one account, so everyone's data stays separate.
CREATE TABLE IF NOT EXISTS food_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    food_name   TEXT NOT NULL,
    meal_type   TEXT NOT NULL CHECK (meal_type IN ('Breakfast', 'Lunch', 'Dinner', 'Snack')),
    calories    INTEGER NOT NULL,
    protein     REAL DEFAULT 0,
    carbs       REAL DEFAULT 0,
    fats        REAL DEFAULT 0,
    log_date    TEXT NOT NULL,          -- stored as 'YYYY-MM-DD'
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Weight / height / BMI entries logged over time per user.
CREATE TABLE IF NOT EXISTS health_metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    weight_kg   REAL NOT NULL,
    height_cm   REAL NOT NULL,
    bmi         REAL NOT NULL,
    log_date    TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- One row per user per day, holding that day's water and step
-- counts. UNIQUE(user_id, log_date) means each user has exactly
-- one row per calendar day, which we update in place with +1/-1
-- buttons instead of inserting a new row every time.
CREATE TABLE IF NOT EXISTS daily_logs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    log_date       TEXT NOT NULL,
    water_glasses  INTEGER DEFAULT 0,
    steps          INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, log_date)
);

-- Community feed: shared across ALL users (not filtered by
-- user_id the way the tables above are), since the whole point
-- of this table is that everyone can see everyone else's posts.
CREATE TABLE IF NOT EXISTS community_posts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    author      TEXT NOT NULL,
    content     TEXT NOT NULL,
    tag         TEXT DEFAULT 'general' CHECK (tag IN ('general', 'challenge')),
    likes       INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
