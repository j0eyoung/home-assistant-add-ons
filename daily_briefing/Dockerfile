# Python 3.12: every pinned package has a prebuilt aarch64 wheel (or is pure Python), so nothing compiles on the Green.
# No Node, no Claude Code CLI and no AI: the briefing is plain data from Home Assistant and the other add-ons.
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x run.sh

# Web UI and API
EXPOSE 8506

CMD ["./run.sh"]
