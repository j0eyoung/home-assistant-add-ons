# Node 22 for the Claude Code CLI, copied from the official image (same Debian release)
FROM node:22-bookworm-slim AS node

# Python 3.12: garminconnect 0.3.x needs >= 3.12, and every pinned package has a
# prebuilt 3.12 wheel, so nothing compiles from source
FROM python:3.12-slim-bookworm

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN npm install -g @anthropic-ai/claude-code && npm cache clean --force

COPY . .

RUN chmod +x run.sh

# Web UI and API
EXPOSE 8501

CMD ["./run.sh"]
