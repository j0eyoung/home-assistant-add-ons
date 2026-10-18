"""Claude through the Claude Code CLI, so it runs on your Claude subscription (no API fees).

Sign-in happens inside the app, the same flow as the Workout Tracker: `claude auth login --claudeai` prints a
link, you approve it in a browser and paste the code back. The login lives in CLAUDE_CONFIG_DIR (/data/claude
in the add-on) so it survives updates. A token from `claude setup-token` in the Configuration tab also works."""
import json
import os
import re
import shutil
import subprocess
import threading
import time

CONFIG_DIR = os.getenv("CLAUDE_CONFIG_DIR", "")
_status_cache = (0.0, {})
_login = None
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_AUTH_WORDS = ("authenticate", "oauth", "log in", "login", "not logged", "unauthorized", "401")


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


def _forget_status():
    global _status_cache
    _status_cache = (0.0, {})


def signed_in():
    s = status()
    return bool(s.get("loggedIn")) and s.get("authMethod") in ("claude.ai", "oauth_token", "claude_ai")


def available():
    """True when Claude can run: the CLI is installed and there's an in-app login or a Configuration-tab token."""
    return binary() is not None and (signed_in() or bool(os.getenv("CLAUDE_CODE_OAUTH_TOKEN")))


def logout():
    if binary():
        subprocess.run([binary(), "auth", "logout"], capture_output=True, text=True, timeout=20, env=_env(),
                       stdin=subprocess.DEVNULL)
    _forget_status()


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
        _forget_status()
    return {"signed_in": signed_in(), "token": bool(os.getenv("CLAUDE_CODE_OAUTH_TOKEN")), "cli": binary() is not None,
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


def run(prompt, timeout=300):
    """One `claude -p` call. Returns (reply, error)."""
    if not binary():
        return None, "The Claude Code CLI isn't installed in this add-on."
    try:
        # No stdin: otherwise the CLI waits for piped input and prints a warning instead of answering
        result = subprocess.run([binary(), "-p", prompt], capture_output=True, text=True, check=True,
                                timeout=timeout, stdin=subprocess.DEVNULL, env=_env())
        return result.stdout.strip(), None
    except subprocess.CalledProcessError as e:
        # The Claude CLI prints most errors to stdout; stderr is mostly warnings
        detail = _ANSI.sub("", (e.stdout or "").strip() or (e.stderr or "").strip()) or f"exit code {e.returncode}"
        print(f"Claude CLI failed (exit {e.returncode}): {detail}", flush=True)
        if any(w in detail.lower() for w in _AUTH_WORDS):
            global _status_cache  # `claude auth status` can still say logged in after the login expires
            _status_cache = (time.time() + 3600, {"loggedIn": False})
            return None, "Claude sign-in expired or invalid. Reconnect in Settings."
        return None, detail
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"Claude CLI did not run: {e}", flush=True)
        return None, str(e)
