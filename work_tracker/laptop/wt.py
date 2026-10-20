"""Laptop client for the Work Tracker add-on on the Home Assistant Green.

Needs two Windows user environment variables (set them yourself in your terminal, never in chat):
  WT_URL  e.g. http://192.168.1.50:8505   (the Green's address and the host port set in the add-on's Network tab)
  WT_KEY  the add-on's api_key option

  python wt.py state
  python wt.py start KISS [CASE] [note ...]       python wt.py stop
  python wt.py add KISS CASE MINUTES [note ...] [--date 2026-10-19]
  python wt.py task "Title" [--due 2026-10-25] [--client KISS] [--case 123]
  python wt.py tasks      python wt.py done ID      python wt.py snooze ID
  python wt.py case CASE "short status"            (case number + status only, 40 characters max)
  python wt.py csv [--from D] [--to D]
Standard library only. The key is never printed."""
import json
import os
import sys
import urllib.error
import urllib.request


def env(name):
    v = os.environ.get(name)
    if not v and sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                v = winreg.QueryValueEx(k, name)[0]
        except OSError:
            pass
    return (v or "").strip()


def call(method, path, body=None, raw=False):
    url, key = env("WT_URL").rstrip("/"), env("WT_KEY")
    if not url or not key:
        sys.exit("Set the WT_URL and WT_KEY user environment variables first (see the top of wt.py).")
    req = urllib.request.Request(f"{url}/api/{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read().decode()
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("detail")
        except Exception:
            msg = e.reason
        sys.exit(f"Error {e.code}: {msg}")
    except OSError as e:
        sys.exit(f"Cannot reach the Green at {url}: {e}")
    return data if raw else json.loads(data)


def flag(args, name):
    if name in args:
        i = args.index(name)
        v = args[i + 1] if i + 1 < len(args) else sys.exit(f"{name} needs a value")
        del args[i:i + 2]
        return v
    return None


def hm(m):
    return f"{m // 60}h{m % 60:02d}m"


def main(a):
    if not a:
        sys.exit(__doc__)
    cmd, args = a[0], a[1:]
    if cmd == "state":
        s = call("GET", "state")
        r = s["running"]
        print("Running: " + (f"{r['client']} {r['case_no']} since {r['start'][11:16]}" if r else "none"))
        print(f"Today {hm(s['totals']['day_minutes'])}, week {hm(s['totals']['week_minutes'])}")
        for c in s["totals"]["week"]:
            print(f"  {c['client']}: {c['hours']:.2f} h")
        print(f"Open tasks: {len(s['tasks'])}")
    elif cmd == "start":
        d = call("POST", "timer/start", {"client": args[0], "case_no": args[1] if len(args) > 1 else "",
                                         "note": " ".join(args[2:])})
        print(f"Started {d['running']['client']} {d['running']['case_no']}" +
              (f" (stopped {d['stopped']['client']})" if d["stopped"] else ""))
    elif cmd == "stop":
        d = call("POST", "timer/stop")["stopped"]
        print("Stopped " + d["client"] if d else "Nothing was running")
    elif cmd == "add":
        day = flag(args, "--date") or __import__("datetime").date.today().isoformat()
        e = call("POST", "entries", {"client": args[0], "case_no": args[1], "minutes": int(args[2]),
                                     "note": " ".join(args[3:]), "date": day})
        print(f"Added {args[2]} min to {e['client']} {e['case_no']} on {day}")
    elif cmd == "task":
        due, client, case = flag(args, "--due"), flag(args, "--client"), flag(args, "--case")
        t = call("POST", "tasks", {"title": " ".join(args), "due": due, "client": client or "", "case_no": case or ""})
        print(f"Task {t['id']}: {t['title']} (due {t['due'] or 'no date'})")
    elif cmd == "tasks":
        for t in call("GET", "tasks"):
            print(f"{t['id']}  {t['due'] or '----------'}  {t['title']}  {t['client']} {t['case_no']}".rstrip())
    elif cmd in ("done", "snooze"):
        call("POST", f"tasks/{int(args[0])}/{cmd}")
        print("OK")
    elif cmd == "case":
        c = call("PUT", f"cases/{args[0]}", {"status": " ".join(args[1:])})
        print(f"Case {c['case_no']}: {c['status']}")
    elif cmd == "csv":
        q = "&".join(f"{k}={v}" for k, v in (("frm", flag(args, "--from")), ("to", flag(args, "--to"))) if v)
        print(call("GET", "export.csv" + ("?" + q if q else ""), raw=True))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
