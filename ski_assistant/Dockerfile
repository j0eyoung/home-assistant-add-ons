# Node 22 for the Claude Code CLI, copied from the official image (same Debian release)
FROM node:22-bookworm-slim AS node

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

EXPOSE 8099

CMD ["./run.sh"]
