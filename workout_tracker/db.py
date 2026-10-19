import sqlite3
import json
import os

DB_PATH = os.getenv("DB_PATH", "workout_tracker.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. User Profile & Active Goals (Triathlon, Snowboard, etc.)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY,
            active_goals JSON,  -- e.g., ["snowboarding", "triathlon", "core_rehab"]
            fitness_level TEXT
        )
    ''')
    
    # Insert default profile if it doesn't exist
    c.execute('SELECT count(*) FROM user_profile')
    if c.fetchone()[0] == 0:
        default_goals = json.dumps(["snowboarding", "triathlon", "posture_restoration"])
        c.execute('INSERT INTO user_profile (id, active_goals, fitness_level) VALUES (1, ?, ?)', (default_goals, "intermediate"))
    
    # 2. Master Exercise Library: created and filled by library.build() below

    # 3. Daily Logs & Symptom Tracking (Auto-Regulation)
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            workout_type TEXT,
            completed BOOLEAN,
            rpe INTEGER,
            pelvic_floor_tightness INTEGER, -- 1-10 scale
            kidney_flank_pain INTEGER,      -- 1-10 scale
            notes TEXT,
            executed_workout JSON
        )
    ''')
    
    conn.commit()
    conn.close()

    # Set-by-set history and today's auto-saved draft
    import history
    history.ensure_schema(DB_PATH)

    # Merge the exercise databases (skipped when nothing changed since the last start)
    import library
    library.build(DB_PATH)

def get_last_log():
    """Latest logged session: effort, symptoms and the workout that was done."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT rpe, pelvic_floor_tightness, kidney_flank_pain, executed_workout FROM daily_logs ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if not row:
        return {"rpe": 5, "pelvic_floor_tightness": 1, "kidney_flank_pain": 1, "executed_workout": {}}
    try:
        executed_workout = json.loads(row[3] or "{}")
    except ValueError:
        executed_workout = {}
    return {"rpe": row[0], "pelvic_floor_tightness": row[1], "kidney_flank_pain": row[2], "executed_workout": executed_workout}

if __name__ == "__main__":
    init_db()
    print("Database ready: goals, symptom tracking and exercise library.")
