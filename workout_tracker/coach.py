"""AI Coach: runs the Claude Code CLI with Joe's subscription token (no API fees)."""
import datetime
import json
import os
import sqlite3
import re
import shutil
import subprocess
import threading
import time

from db import DB_PATH

def persona(sports=("skiing", "snowboarding", "triathlon")):
    """Who the coach says it is, following the sports ticked in Settings."""
    roles = ["Physical Therapist", "Strength Coach"]
    if "triathlon" in sports:
        roles.append("Triathlon Coach")
    if {"skiing", "snowboarding"} & set(sports):
        roles.append("Ski and Snowboard Conditioning Coach")
    roles.append("Biomechanics Expert")
    text = f"You are an elite {', '.join(roles[:-1])} and {roles[-1]}. "
    if sports:
        text += "Joe is training for: " + ", ".join(sports) + ". Do not coach any sport that is not in this list. "
    else:
        text += "Joe is not training for a specific sport right now: keep to general strength, mobility and recovery. "
    return text


SYSTEM_INSTRUCTION = (
    "{persona}"
    "You have the 'gym-bro', 'physical-therapy-rehab-plan', and 'movement-systems' frameworks. "
    "1. PT HARD SAFETY GATE: Before planning anything, you must run a clinical safety screen on the user's symptoms. "
    "If Left Kidney Pain is > 6 or Pelvic Floor Tightness is > 7, you must issue a HARD CLINICAL STOP, refuse exercise progression, and enforce a pure recovery/breathing day. "
    "If Pelvic Floor Tightness > 7, you MUST ALSO explicitly refer the user to find a clinical professional using the Pelvic Floor PT Directory (https://github.com/pete0585/pelvic-floor-pt-directory). "
    "2. BIOMECHANICAL ANALYSIS (movement-systems): When prescribing any exercise, you must explain the movement system mechanics to ensure no compensatory spinal compression or asymmetric torque occurs due to the Pyeloplasty adhesions. "
    "3. CRITICAL COMMAND OVERRIDE: The user uses Garmin, NOT Strava. DO NOT attempt to run `endurance-coach auth` or sync Strava. "
    "Instead, use the TRAINING DATA given below (Garmin resting heart rate, logged effort and symptoms, completed sets). "
    "Never run commands or open files: you cannot, and everything you need is in this message. "
    "If a section says no data, say so plainly. "
    "4. MEDICAL CONSTRAINTS: Left Kidney Pyeloplasty Adhesions (NO heavy axial load, NO asymmetric torque) and hypertonic pelvic floor (limit high-impact running). "
    "5. EXPLAINABLE PLANNING: When you propose or alter a workout, you must explain exactly which past verified data points or PT constraints led to that decision. "
    "Keep answers short and easy to read on a phone."
)

REPORT_INSTRUCTION = (
    "You are an expert AI data analyst. Using the TRAINING DATA below, generate a beautiful, portable, single-file HTML "
    "dashboard summarizing the user's progress, effort (RPE) trends, symptoms, weights lifted and Garmin data. "
    "Output only the raw HTML (starting with <!doctype html>), nothing else. You cannot run commands or open files."
)


def _table(conn, sql, params=()):
    try:
        cur = conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except sqlite3.Error:
        return None  # table missing


def training_data(days=21):
    """Recent data, read here so the coach never needs to run a database command (the CLI can't ask for approval)."""
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    except sqlite3.Error:
        return "TRAINING DATA: the database could not be opened."
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    logs = _table(conn, "SELECT id, date, rpe, pelvic_floor_tightness, kidney_flank_pain, notes FROM daily_logs "
                        "WHERE date >= ? ORDER BY id DESC LIMIT 30", (since,))
    sets = _table(conn, "SELECT date, exercise, set_number, weight_lbs, reps FROM workout_sets WHERE date >= ? AND done = 1 "
                        "ORDER BY id DESC LIMIT 150", (since,))
    garmin = (_table(conn, "SELECT date, resting_hr, hrv_avg, sleep_secs, body_battery, latest_activity_type, duration_secs, "
                           "avg_hr, max_hr FROM garmin_metrics ORDER BY id DESC LIMIT 14")
              or _table(conn, "SELECT date, resting_hr, latest_activity_type, duration_secs, avg_hr, max_hr FROM garmin_metrics "
                              "ORDER BY id DESC LIMIT 14"))  # older databases have no hrv/sleep columns
    bio = _table(conn, "SELECT date, data, unit, notes FROM biofeedback ORDER BY date DESC LIMIT 6")
    conn.close()

    def section(title, rows, empty):
        if not rows:
            return f"{title}: {empty}"
        return f"{title} ({len(rows)} rows, newest first):\n" + "\n".join(json.dumps(r, default=str) for r in rows)

    return "TRAINING DATA (last %d days)\n" % days + "\n\n".join([
        section("Logged workouts (effort and symptoms, 1-10)", logs, "no workouts logged in this period."),
        section("Completed sets", sets, "no sets logged in this period."),
        section("Garmin metrics", garmin, "none. The Garmin sync has not stored anything yet, so tell Joe the Garmin "
                                           "connection still needs setting up (do not guess his heart rate)."),
        section("Pelvic floor manometric biofeedback with his pelvic PT, about every two weeks (data keys: resting = "
                "resting tone, peak = max squeeze, hold = endurance seconds, relax = seconds to return to rest, quick = "
                "quick flicks in 10 s, rest_end = resting tone after down-training). His floor is hypertonic, so falling "
                "resting tone and faster relaxing are the main signs of progress", bio, "none logged yet."),
    ])


# Sign-in happens inside the app (same flow as the Trading Terminal): `claude auth login --claudeai`
# prints a link, Joe approves it in a browser and pastes the code back. The login lives in
# CLAUDE_CONFIG_DIR (/data/claude in the add-on) so it survives updates.
CONFIG_DIR = os.getenv("CLAUDE_CONFIG_DIR", "")
_status_cache = (0.0, {})
_login = None


def binary():
    return shutil.which("claude")


def _env():
    env = dict(os.environ, DISABLE_AUTOUPDATER="1", BROWSER="none", NO_COLOR="1")
    env.pop("ANTHROPIC_API_KEY", None)  # an API key would override the subscription login
    if CONFIG_DIR:
        env["CLAUDE_CONFIG_DIR"] = CONFIG_DIR
    # A saved (possibly expired) Configuration-tab token beats the in-app login, so drop it once signed in
    if signed_in():
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    return env


def status(max_age=600):
    """`claude auth status` as a dict ({} if the CLI is missing or fails); cached because it starts a program."""
    global _status_cache
    if time.time() - _status_cache[0] < max_age:
        return _status_cache[1]
    result = {}
    if binary():
        try:
            env = dict(os.environ, NO_COLOR="1")
            env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
            if CONFIG_DIR:
                env["CLAUDE_CONFIG_DIR"] = CONFIG_DIR
            out = subprocess.run([binary(), "auth", "status"], capture_output=True, text=True, timeout=20,
                                 env=env, stdin=subprocess.DEVNULL).stdout
            result = json.loads(out[out.find("{"):]) if "{" in out else {}
        except Exception:
            result = {}
    _status_cache = (time.time(), result)
    return result


def forget_status():
    global _status_cache
    _status_cache = (0.0, {})


def signed_in():
    s = status()
    return bool(s.get("loggedIn")) and s.get("authMethod") in ("claude.ai", "oauth_token", "claude_ai")


def has_token():
    """True when the coach has some way to sign in: the in-app login or a Configuration-tab token."""
    return signed_in() or bool(os.getenv("CLAUDE_CODE_OAUTH_TOKEN"))


def logout():
    if binary():
        subprocess.run([binary(), "auth", "logout"], capture_output=True, text=True, timeout=20, env=_env(),
                       stdin=subprocess.DEVNULL)
    forget_status()


class Login:
    """One run of `claude auth login --claudeai`, driven from the web page."""

    def __init__(self):
        self.output = ""
        self.started = time.time()
        self.proc = subprocess.Popen([binary(), "auth", "login", "--claudeai"], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                                     env=_env())
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            self.output += _ANSI.sub("", line)

    @property
    def url(self):
        m = re.search(r"https://\S+", self.output)
        return m.group(0) if m else None

    @property
    def done(self):
        return self.proc.poll() is not None

    @property
    def result(self):
        lines = [ln.strip() for ln in self.output.splitlines() if ln.strip() and "http" not in ln]
        return lines[-1] if lines else ""

    def send_code(self, code):
        if not self.done:
            self.proc.stdin.write("".join(code.split()) + "\n")
            self.proc.stdin.flush()

    def cancel(self):
        if not self.done:
            self.proc.kill()


def login_state():
    """What the page needs to draw the connect card."""
    global _login
    if _login and not _login.done and time.time() - _login.started > 600:
        _login.cancel()
    if _login and _login.done:
        forget_status()
    return {"signed_in": signed_in(), "cli": binary() is not None,
            "login": None if not _login else {"url": _login.url, "done": _login.done, "result": _login.result}}


def start_login():
    global _login
    if _login:
        _login.cancel()
    _login = Login() if binary() else None
    return login_state()


def send_code(code):
    if _login:
        _login.send_code(code)
        time.sleep(3)  # give the CLI a moment to finish before the page asks again
    return login_state()


def cancel_login():
    global _login
    if _login:
        _login.cancel()
    _login = None
    return login_state()


_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_AUTH_WORDS = ("authenticate", "oauth", "log in", "login", "not logged", "unauthorized", "401")


def _run(prompt, timeout=300):
    """Returns (reply, error)."""
    try:
        # No stdin: otherwise the CLI waits for piped input and prints a warning instead of answering
        result = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, check=True,
                                timeout=timeout, stdin=subprocess.DEVNULL, env=_env())
        return result.stdout.strip(), None
    except subprocess.CalledProcessError as e:
        # The Claude CLI prints most errors to stdout; stderr is mostly warnings
        detail = _ANSI.sub("", (e.stdout or "").strip() or (e.stderr or "").strip()) or f"exit code {e.returncode}"
        print(f"Claude CLI failed (exit {e.returncode}): {detail}", flush=True)
        if any(w in detail.lower() for w in _AUTH_WORDS):
            global _status_cache  # `claude auth status` can still say logged in after the login expires
            _status_cache = (time.time() + 3600, {"loggedIn": False})
            return None, "Claude sign-in expired or invalid. Reconnect in the Coach tab."
        return None, detail
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"Claude CLI did not run: {e}", flush=True)
        return None, str(e)


def ask(message, recent=(), plan_context="", season="", sports=("skiing", "snowboarding", "triathlon")):
    """One coach reply. `recent` is the last few chat turns, for continuity."""
    conversation = "\n".join(f"{'Joe' if m.get('role') == 'user' else 'Coach'}: {m.get('content', '')}"
                             for m in list(recent)[-6:])
    prompt = SYSTEM_INSTRUCTION.replace("{persona}", persona(sports))
    import library  # late import: library is heavy and only the coach needs the notes
    prompt += "\n\nEquipment available at home: " + ", ".join(library.selected_equipment()) + ".\n" + \
        library.load_settings().get("gear_notes", library.DEFAULT_GEAR_NOTES)
    prompt += "\n\n" + training_data()
    if season:
        prompt += f"\n\nSki or snowboard season starts: {season}. Plan the build-up to it."
    if plan_context:
        prompt += "\n\n" + plan_context
    if conversation:
        prompt += f"\n\nConversation so far:\n{conversation}"
    prompt += f"\n\nUser Update: {message}"
    return _run(prompt)


def meditation_script(minutes, focus=""):
    """A short spoken meditation script (the phone's browser reads it aloud)."""
    words = int(minutes) * 110  # slow speaking pace
    prompt = (
        f"Write a guided meditation script of about {words} words (it will be read aloud slowly, about {minutes} minutes). "
        "For Joe, who has a sensitive left kidney area after surgery and a tight pelvic floor. "
        "Use slow breathing with LONG, soft exhales, relaxed belly and jaw, no breath holds and no bearing down. "
        "Do not ask him to clench, squeeze or hold tension anywhere. Plain spoken language, short sentences, "
        "pauses written as '...' and a new paragraph for each phase (settle, breath, body, focus, close). "
        f"{'Theme: ' + focus.strip()[:200] + '. ' if focus and focus.strip() else ''}"
        "Output only the script, with no title, notes or stage directions."
    )
    return _run(prompt, timeout=240)


def report():
    os.makedirs("/config/workout_tracker", exist_ok=True)
    html, error = _run(REPORT_INSTRUCTION + "\n\n" + training_data(days=90), timeout=600)
    if error:
        return None, error
    start = html.lower().find("<!doctype")
    html = html[start:] if start >= 0 else html
    with open("/config/workout_tracker/progress_report.html", "w", encoding="utf-8") as f:
        f.write(html)
    return html, None
