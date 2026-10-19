# Python 3.12: every pinned package has a prebuilt aarch64 wheel (or is pure Python), so nothing compiles on the Green.
# No Node or Claude Code CLI here: openers are drafted through the Anthropic API directly.
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x run.sh

# Web UI and API
EXPOSE 8503

CMD ["./run.sh"]
