# Base image fixed here on purpose: Home Assistant passes its own Alpine base as BUILD_FROM
# (no Python), so that argument is deliberately not used.
FROM python:3.12-slim-bookworm

ENV PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 DATA_DIR=/data \
    PATH=/root/.local/bin:$PATH DISABLE_AUTOUPDATER=1
WORKDIR /app

# Claude Code CLI, so the app can use a Claude subscription sign-in (Assistant > Connect Claude).
# Not fatal: without it the app falls back to Gemini or an API key.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && (curl -fsSL https://claude.ai/install.sh | bash || echo "Claude Code install failed; continuing without it")

# Dependencies first so code-only updates rebuild quickly
COPY app/requirements.txt .
RUN pip install -r requirements.txt

COPY app/ .
COPY addon_entry.py shared_secrets.py ./

CMD ["python", "addon_entry.py"]
