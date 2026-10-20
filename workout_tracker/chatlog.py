"""The AI Coach conversation, kept on the add-on so the phone and the PC show the same chat."""
import json
import sqlite3
import time

import history

KEEP = 200            # messages kept; older ones are dropped
_busy = {"since": 0.0}


def set_busy(on):
    _busy["since"] = time.time() if on else 0.0


def busy():
    """True while the coach is writing a reply (a reply that takes over 8 minutes is treated as lost)."""
    return bool(_busy["since"]) and time.time() - _busy["since"] < 480


def messages(db_path, limit=80):
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, role, content, extra FROM coach_chat ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    out = []
    for mid, role, content, extra in reversed(rows):
        m = {"id": mid, "role": role, "content": content}
        try:
            m.update(json.loads(extra or "{}"))
        except ValueError:
            pass
        out.append(m)
    return out


def add(db_path, role, content, extra=None):
    conn = sqlite3.connect(db_path)
    cur = conn.execute("INSERT INTO coach_chat (role, content, extra, created) VALUES (?, ?, ?, ?)",
                       (role, content, json.dumps(extra or {}), history.local_now().isoformat(timespec="seconds")))
    mid = cur.lastrowid
    conn.execute("DELETE FROM coach_chat WHERE id <= ?", (mid - KEEP,))
    conn.commit()
    conn.close()
    return mid


def update(db_path, mid, **flags):
    """Adds flags such as applied or dismissed to a message (the Apply / No thanks buttons)."""
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT extra FROM coach_chat WHERE id = ?", (mid,)).fetchone()
    if row:
        try:
            extra = json.loads(row[0] or "{}")
        except ValueError:
            extra = {}
        extra.update(flags)
        conn.execute("UPDATE coach_chat SET extra = ? WHERE id = ?", (json.dumps(extra), mid))
        conn.commit()
    conn.close()


def clear(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM coach_chat")
    conn.commit()
    conn.close()


def count(db_path):
    conn = sqlite3.connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM coach_chat").fetchone()[0]
    conn.close()
    return n


def recent(db_path, n=6):
    """The last few turns as {"role", "content"}, for the coach's prompt."""
    return [{"role": m["role"], "content": m["content"]} for m in messages(db_path, n)]
