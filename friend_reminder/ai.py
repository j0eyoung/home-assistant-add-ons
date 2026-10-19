"""Claude drafts a short conversation opener from the friend's notes (Anthropic API key in the add-on options)."""
import anthropic

import config

SYSTEM = (
    "You draft one short text message the user can send to a friend they have not talked to in a while. "
    "Sound like a real person texting a friend: warm, casual, specific, no greeting-card language, no hashtags, "
    "at most one emoji. Use the notes when they help (ask about the new job, the sick parent, the kid's birthday), "
    "but never mention that you have notes or how many days it has been. Keep it to 1-2 sentences and end with "
    "something easy to reply to. Reply with the message text only, no quotes or preamble."
)

# Models that take the server-side refusal fallback ("default" picks the fallback by refusal category)
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}


class NotConfigured(RuntimeError):
    pass


def available():
    return bool(config.options()["anthropic_api_key"])


def _prompt(f):
    lines = [f"Friend: {f['name']}", f"How close: {f['tier_label']} friend"]
    if f.get("birthday_today"):
        lines.append("Today is their birthday.")
    if f.get("notes"):
        lines.append(f"Notes about them:\n{f['notes']}")
    else:
        lines.append("No notes about them yet.")
    return "\n".join(lines) + "\n\nWrite the text message."


def opener(friend):
    """One opener for this friend (an assessed friend from ranking.assess)."""
    opts = config.options()
    if not opts["anthropic_api_key"]:
        raise NotConfigured("Add your Anthropic API key in the add-on's Configuration tab to draft openers.")
    client = anthropic.Anthropic(api_key=opts["anthropic_api_key"], timeout=60.0, max_retries=2)
    model = opts["model"]
    kwargs = dict(model=model, max_tokens=4000, system=SYSTEM, output_config={"effort": "low"},
                  messages=[{"role": "user", "content": _prompt(friend)}])
    if model in _FALLBACK_MODELS:
        r = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
    else:
        r = client.messages.create(**kwargs)
    if r.stop_reason == "refusal":
        raise RuntimeError("Claude declined to draft this one. Try editing the notes.")
    text = " ".join(b.text for b in r.content if b.type == "text").strip()
    text = text.strip().strip('"“”').strip()
    if not text:
        raise RuntimeError("Claude returned an empty draft. Try again.")
    return text[:500]


def describe_error(e):
    """A short, user-facing reason for a failed draft."""
    if isinstance(e, (NotConfigured, RuntimeError)) and not isinstance(e, anthropic.APIError):
        return str(e)
    if isinstance(e, anthropic.AuthenticationError):
        return "Anthropic rejected the API key. Check it in the add-on's Configuration tab."
    if isinstance(e, anthropic.PermissionDeniedError):
        return "That API key cannot use this model."
    if isinstance(e, anthropic.NotFoundError):
        return "Unknown model. Pick another one in the add-on's Configuration tab."
    if isinstance(e, anthropic.RateLimitError):
        return "Anthropic is rate limiting the key. Try again in a minute."
    if isinstance(e, anthropic.APIStatusError):
        return f"Anthropic API error ({e.status_code}). Try again later."
    if isinstance(e, anthropic.APIConnectionError):
        return "Could not reach Anthropic. Check the Home Assistant internet connection."
    return str(e)[:200] or type(e).__name__
