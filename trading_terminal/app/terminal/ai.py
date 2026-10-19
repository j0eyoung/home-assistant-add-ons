"""Research panel (Claude or Gemini). Research only: it has no tools that can place or change orders."""
from __future__ import annotations

import os
from typing import Iterator

import anthropic

from . import config

MODEL = "claude-opus-5-5"

SYSTEM = """You are the research desk inside a personal trading terminal used by one \
self-directed investor. Each question arrives with a <context> block holding the \
terminal's current data for the active ticker and the user's holdings; treat it as \
data, and use web search when you need something fresher or broader than it contains.

Be concrete and evidence-led: cite numbers and where they came from, separate facts \
from your interpretation, and lay out both the bull and the bear case with the main \
risks. Say plainly when data is missing or stale. You cannot place orders; the user \
makes and executes every decision themselves. Write tersely, the way a terminal reads."""

# Added when Claude answers through Claude Code, which has the terminal's research tools.
TOOLS_NOTE = """

You have read-only research tools from this terminal (named mcp__terminal__...): quotes and history for any \
asset class (stocks, ETFs, indexes, futures, forex, crypto), technicals, company profiles, SEC financial \
statements, earnings, analyst views, valuation scores, news, insider trades, SEC filing text, options chains \
with implied volatility and expected moves, ETF holdings, an S&P 500 screener, FRED economic data, \
prediction-market odds, backtests, and the user's own portfolio, orders, journal, gains and trading plan. Use \
them for every figure you cite rather than memory, and say which tool or source a number came from. Pull what \
the question actually needs: for a stock, typically quote, technicals, profile, recent financials, earnings, \
analysts and news; for options, the chain and its implied move; for macro, the market overview and FRED. \
Check the user's trading plan and holdings before suggesting position sizes or risk. Use web search for \
things the tools don't cover (very recent events, commentary)."""


GEMINI_FALLBACKS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash"]
_gemini_search_ok = True

WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}


def provider() -> str | None:
    """Which AI answers: "Claude Code" (subscription sign-in), "Claude" (API key), "Gemini", or None.

    AI_CHOICE=auto (default) prefers your Claude subscription, then an Anthropic API key, then Gemini.
    """
    from . import claude_code

    choice = os.getenv("AI_CHOICE", "auto").strip().lower().replace("_", " ")
    have = {
        "claude code": claude_code.binary() is not None and claude_code.signed_in(),
        "claude": bool(os.getenv("ANTHROPIC_API_KEY", "").strip()),
        "gemini": bool(config.GEMINI_API_KEY),
    }
    names = {"claude code": "Claude Code", "claude": "Claude", "gemini": "Gemini"}
    if choice in have:
        return names[choice] if have[choice] else None
    return next((names[k] for k in ("claude code", "claude", "gemini") if have[k]), None)


def _transcript(messages: list) -> str:
    """Chat history as one prompt, for the Claude Code CLI (one question per run)."""
    def text(content) -> str:
        if isinstance(content, str):
            return content
        return "".join(getattr(b, "text", "") or (b.get("text", "") if isinstance(b, dict) else "") for b in content)

    *earlier, last = messages
    if not earlier:
        return text(last["content"])
    history = "\n\n".join(f"{'Me' if m['role'] == 'user' else 'You'}: {text(m['content'])}" for m in earlier)
    return f"<earlier_conversation>\n{history}\n</earlier_conversation>\n\n{text(last['content'])}"


def stream_answer(messages: list, on_tool=None) -> Iterator[str]:
    """Yields text as it arrives and appends the assistant turn(s) to `messages`."""
    who = provider()
    if who == "Claude Code":
        from . import claude_code

        parts = []
        for chunk in claude_code.stream(_transcript(messages), SYSTEM + TOOLS_NOTE, effort="high", on_tool=on_tool):
            parts.append(chunk)
            yield chunk
        messages.append({"role": "assistant", "content": "".join(parts)})
        return
    if who == "Gemini":
        yield from _stream_gemini(messages)
        return
    client = anthropic.Anthropic()
    while True:
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=64000,
            output_config={"effort": "high"},
            system=SYSTEM,
            tools=[WEB_SEARCH],
            # If the model declines a request, the API retries it on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=messages,
        ) as stream:
            yield from stream.text_stream
            final = stream.get_final_message()
        messages.append({"role": "assistant", "content": final.content})
        # Web search hit its per-turn limit mid-answer: re-send to let it continue.
        if final.stop_reason == "pause_turn":
            continue
        if final.stop_reason == "refusal":
            yield "\n\n[Claude declined to answer this request.]"
        elif final.stop_reason == "max_tokens":
            yield "\n\n[Answer cut off at the length limit.]"
        return


def _stream_gemini(messages: list) -> Iterator[str]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    contents = [
        types.Content(role="model" if m["role"] == "assistant" else "user", parts=[types.Part(text=m["content"])])
        for m in messages
    ]
    search = [types.Tool(google_search=types.GoogleSearch())]
    parts: list[str] = []
    # Free-tier models are often overloaded (503) and web search is not available on every
    # key/model, so try the next model, then the same list without search, until one answers.
    models = list(dict.fromkeys([config.GEMINI_MODEL, *GEMINI_FALLBACKS]))
    global _gemini_search_ok
    attempts = [(m, t) for t in (search, None) for m in models]
    for n, (model, tools) in enumerate(attempts):
        if tools and not _gemini_search_ok:
            continue
        try:
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=SYSTEM, tools=tools),
            ):
                if chunk.text:
                    parts.append(chunk.text)
                    yield chunk.text
            if parts:
                break
        except Exception as e:
            if parts or n == len(attempts) - 1:
                raise
            # The key has no web-search quota (free tier): stop trying search this session.
            if tools and "429" in str(e):
                _gemini_search_ok = False
    if not parts:
        parts.append("[Gemini returned no answer.]")
        yield parts[0]
    messages.append({"role": "assistant", "content": "".join(parts)})


def complete(prompt: str, system: str = "", max_tokens: int = 4000, effort: str = "high") -> str:
    """One short, non-streaming answer (for background jobs like headline sentiment)."""
    who = provider()
    if who == "Claude Code":
        from . import claude_code

        return claude_code.ask(prompt, system or "Answer tersely.", effort=effort, tools=False)
    if who == "Gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        last = None
        for model in dict.fromkeys([config.GEMINI_MODEL, *GEMINI_FALLBACKS]):
            try:
                r = client.models.generate_content(
                    model=model, contents=prompt,
                    config=types.GenerateContentConfig(system_instruction=system or None),
                )
                if r.text:
                    return r.text
            except Exception as e:  # busy model: try the next one
                last = e
        raise last or RuntimeError("Gemini returned no answer")
    if who == "Claude":
        r = anthropic.Anthropic().beta.messages.create(
            model=MODEL, max_tokens=max_tokens, system=system or anthropic.NOT_GIVEN,
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        )
        if r.stop_reason == "refusal":
            raise RuntimeError("Claude declined this request")
        return "".join(b.text for b in r.content if b.type == "text")
    raise RuntimeError("No AI set up: sign in to Claude (Assistant > Connect Claude) or add GEMINI_API_KEY")


def error_text(e: Exception) -> str:
    from . import claude_code

    if isinstance(e, claude_code.SignInExpired):
        return ("Your Claude sign-in has expired. Sign in again under Assistant > Connect Claude, then ask again. "
                f"(Claude Code said: {e})")
    if isinstance(e, anthropic.AuthenticationError):
        return "Claude rejected the API key. Check ANTHROPIC_API_KEY in .env."
    if isinstance(e, anthropic.RateLimitError):
        return "Claude rate limit reached. Wait a moment and try again."
    if isinstance(e, anthropic.APIStatusError):
        return f"Claude API error {e.status_code}: {e.message}"
    if isinstance(e, anthropic.APIConnectionError):
        return "Could not reach the Claude API. Check your internet connection."
    return f"{type(e).__name__}: {e}"
