# Debian rather than Alpine: Claude Code and ha-mcp's Python both want glibc.
FROM node:24-bookworm-slim

# Tools Claude uses in Home Assistant the way Claude Terminal has them: git, jq,
# ripgrep, curl. python3 runs the sign-in helper; uv (pinned, from PyPI) runs ha-mcp.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git jq less nano procps python3 python3-pip ripgrep tree yq \
    && pip3 install --no-cache-dir --break-system-packages uv==0.11.28 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV npm_config_cache=/tmp/npm-cache
COPY package*.json ./
RUN npm ci --no-audit --no-fund && npm cache clean --force
COPY . .
RUN npm run build \
    && npm prune --omit=dev --no-audit --no-fund \
    && node scripts/link-claude.mjs \
    && rm -rf /tmp/npm-cache

ENV PORT=8099 NODE_ENV=production
EXPOSE 8099
CMD ["sh", "-c", "node shared_secrets.mjs; exec node server/index.ts"]
