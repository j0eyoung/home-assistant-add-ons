"""Claude through the Claude Code CLI, signed in with a Claude subscription (no API key).

Sign-in uses the same flow as the CLI: `claude auth login --claudeai` prints a link, you approve
it in a browser, and paste the code it shows back in. Questions run with `claude -p` in a locked
down mode: no tools that run commands or edit files, web search only.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Iterator

# In the Home Assistant add-on this points at /data/claude so the login survives updates.
CONFIG_DIR = os.getenv("CLAUDE_CONFIG_DIR", "")
TOOLS = ["WebSearch", "WebFetch"]
_status_cache: tuple[float, dict] = (0.0, {})


def binary() -> str | None:
    return shutil.which("claude")


def _env() -> dict:
    env = dict(os.environ, DISABLE_AUTOUPDATER="1", BROWSER="none", NO_COLOR="1")
    # An API key in the environment would take priority over the subscription login.
    env.pop("ANTHROPIC_API_KEY", None)
    if CONFIG_DIR:
        env["CLAUDE_CONFIG_DIR"] = CONFIG_DIR
    return env


def status(max_age: float = 600) -> dict:
    """`claude auth status` as a dict ({} if the CLI is missing or fails); cached for 10 minutes (it starts a\n    separate program, which takes a few seconds on a small device)."""
    global _status_cache
    if time.time() - _status_cache[0] < max_age:
        return _status_cache[1]
    result = {}
    if binary():
        try:
            out = subprocess.run([binary(), "auth", "status"], capture_output=True, text=True, timeout=20,
                                 env=_env()).stdout
            result = json.loads(out[out.find("{"):]) if "{" in out else {}
        except Exception:
            result = {}
    _status_cache = (time.time(), result)
    return result


def signed_in() -> bool:
    s = status()
    return bool(s.get("loggedIn")) and s.get("authMethod") in ("claude.ai", "oauth_token", "claude_ai")


def forget_status() -> None:
    global _status_cache
    _status_cache = (0.0, {})


def logout() -> None:
    if binary():
        subprocess.run([binary(), "auth", "logout"], capture_output=True, text=True, timeout=20, env=_env())
    forget_status()


class Login:
    """One run of `claude auth login --claudeai`, driven from the web page."""

    def __init__(self):
        self.output = ""
        self.started = time.time()
        self.proc = subprocess.Popen(
            [binary(), "auth", "login", "--claudeai"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1, env=_env(),
        )
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            self.output += line

    @property
    def url(self) -> str | None:
        m = re.search(r"https://\S+", self.output)
        return m.group(0) if m else None

    @property
    def done(self) -> bool:
        return self.proc.poll() is not None

    def send_code(self, code: str) -> None:
        if not self.done:
            self.proc.stdin.write(code.strip() + "\n")
            self.proc.stdin.flush()

    def cancel(self) -> None:
        if not self.done:
            self.proc.kill()

    @property
    def result(self) -> str:
        """Last line the CLI printed, with the sign-in link removed."""
        lines = [ln.strip() for ln in self.output.splitlines() if ln.strip() and "http" not in ln]
        return lines[-1] if lines else ""


MCP_NAME = "terminal"  # tools appear to Claude as mcp__terminal__get_quote etc.


def _mcp_config() -> str | None:
    """Path to a config connecting Claude Code to the terminal's read-only research tools (mcp_server.py):
    the add-on's always-on server when TERMINAL_MCP_URL is set, otherwise started on demand (stdio)."""
    url = os.getenv("TERMINAL_MCP_URL", "").strip()
    if url:
        server = {"type": "http", "url": url}
    else:
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server.py")
        if not os.path.exists(script):
            return None
        server = {"type": "stdio", "command": sys.executable, "args": [script]}
    path = os.path.join(_workdir(), "mcp.json")
    with open(path, "w") as f:
        json.dump({"mcpServers": {MCP_NAME: server}}, f)
    return path


def _command(system: str, stream: bool, effort: str = "high", tools: bool = True) -> list[str]:
    allowed = list(TOOLS)
    cmd = [binary(), "-p", "--restricted", "--no-session-persistence", "--tools", *TOOLS,
           "--system-prompt", system, "--effort", effort, "--strict-mcp-config"]
    config = _mcp_config() if tools else None
    if config:
        cmd += ["--mcp-config", config]
        allowed.append(f"mcp__{MCP_NAME}")  # every tool on the terminal server (all read-only)
    cmd += ["--allowedTools", *allowed]
    if stream:
        cmd += ["--output-format", "stream-json", "--verbose", "--include-partial-messages"]
    else:
        cmd += ["--output-format", "json"]
    return cmd


def _workdir() -> str:
    d = os.path.join(CONFIG_DIR or tempfile.gettempdir(), "trading-terminal-work")
    os.makedirs(d, exist_ok=True)
    return d


def ask(prompt: str, system: str, timeout: int = 300, effort: str = "high", tools: bool = True) -> str:
    """One complete answer."""
    p = subprocess.run(_command(system, stream=False, effort=effort, tools=tools), input=prompt, capture_output=True, text=True,
                       timeout=timeout, env=_env(), cwd=_workdir())
    try:
        data = json.loads(p.stdout[p.stdout.find("{"):])
    except (ValueError, json.JSONDecodeError):
        raise RuntimeError(f"Claude Code failed: {(p.stderr or p.stdout).strip()[:300]}")
    if data.get("is_error"):
        msg = str(data.get("result") or data.get("subtype"))
        if is_auth_error(msg):
            mark_signed_out(msg)
            raise SignInExpired(msg)
        raise RuntimeError(f"Claude Code: {msg}")
    return data.get("result") or ""


class SignInExpired(RuntimeError):
    """The saved Claude sign-in no longer works (expired or revoked); sign in again under Connect Claude."""


def is_auth_error(msg: str) -> bool:
    m = msg.lower()
    return any(w in m for w in ("authenticate", "oauth", "log in", "login", "not logged", "unauthorized", "401"))


def mark_signed_out(reason: str) -> None:
    """Stop using Claude until the user signs in again (`claude auth status` still reports an expired login)."""
    global _status_cache
    _status_cache = (time.time() + 3600 * 24 * 365, {"loggedIn": False, "expired": True, "error": reason})


def _log(msg: str) -> None:
    print(f"[claude] {msg}", file=sys.stderr, flush=True)  # shows in the add-on's Log tab


def stream(prompt: str, system: str, timeout: int = 600, effort: str = "high", tools: bool = True,
           on_tool=None) -> Iterator[str]:
    """Yields the answer as it is written. Tool calls happen in between (pauses are normal); `on_tool(name)`
    is called for each one. Stops with an error if nothing finishes within `timeout` seconds."""
    p = subprocess.Popen(_command(system, stream=True, effort=effort, tools=tools), stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env=_env(),
                         cwd=_workdir())
    started = time.time()
    _log(f"question started (effort {effort}, tools {'on' if tools else 'off'}, {len(prompt):,} chars)")
    # Read stderr continuously: if nobody drains it, its pipe can fill up and freeze the CLI.
    errors: list[str] = []
    threading.Thread(target=lambda: errors.extend(p.stderr), daemon=True).start()
    # Watchdog: a hung CLI prints nothing, so a check inside the read loop would never run.
    timer = threading.Timer(timeout, p.kill)
    timer.start()
    try:
        p.stdin.write(prompt)
        p.stdin.close()
        wrote, final, tools_used = False, None, []
        for line in p.stdout:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = ev.get("type")
            if kind == "system" and ev.get("subtype") == "init":
                servers = {s.get("name"): s.get("status") for s in ev.get("mcp_servers") or []}
                if tools and servers.get(MCP_NAME) != "connected":
                    _log(f"research tools not available: {servers or 'no tool server configured'}")
            elif kind == "assistant":
                for b in (ev.get("message") or {}).get("content") or []:
                    if b.get("type") == "tool_use":
                        name = b.get("name", "").removeprefix(f"mcp__{MCP_NAME}__")
                        tools_used.append(name)
                        _log(f"tool: {name}")
                        if on_tool:
                            on_tool(name)
            elif kind == "stream_event":
                delta = (ev.get("event") or {}).get("delta") or {}
                if delta.get("type") == "text_delta" and delta.get("text"):
                    wrote = True
                    yield delta["text"]
            elif kind == "result":
                final = ev
        p.wait(timeout=30)
    finally:
        timer.cancel()
        if p.poll() is None:
            p.kill()
    took = time.time() - started
    if final is None:
        why = "".join(errors).strip()[-400:] or ("no answer within the time limit" if took >= timeout - 1
                                                 else f"exited with code {p.returncode}")
        _log(f"failed after {took:.0f}s: {why}")
        raise RuntimeError(f"Claude Code didn't answer: {why}")
    if final.get("is_error"):
        msg = str(final.get("result") or final.get("subtype"))
        _log(f"error after {took:.0f}s: {msg}")
        if is_auth_error(msg):
            mark_signed_out(msg)
            raise SignInExpired(msg)
        raise RuntimeError(f"Claude Code: {msg}")
    _log(f"answered in {took:.0f}s using {len(tools_used)} tool calls")
    if not wrote and final.get("result"):
        yield final["result"]
