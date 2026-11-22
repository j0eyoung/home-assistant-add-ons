# Claude Chat add-on

A desktop-style chat for Claude Code inside Home Assistant. Node 24 server (TypeScript run directly, no build step) + React/Vite page. The server drives Claude Code through the Claude Agent SDK (`@anthropic-ai/claude-agent-sdk`, pinned): one `query()` per open chat in streaming-input mode, approvals through `canUseTool`, safety through `PreToolUse`/`PostToolUse` hooks, chat history from Claude Code's own session files (`listSessions`, `getSessionMessages`). All commands run from `claude_chat/`.

## Commands

- `npm run build` then `node --env-file=.env server/index.ts` from the repo root as in `../.claude/launch.json` (`claude-chat`, port 8098). `.env` sets `DEMO_HA=1` for sample Home Assistant data and `DATA_DIR`. Away from Home Assistant the server keeps your own HOME, so it uses your local Claude Code sign-in.
- `npm run typecheck`
- `python scripts/make_icon.py`: redraw `icon.png`/`logo.png` after changing `web/public/icon.svg`

## Layout

- `server/chat.ts`: one conversation (`Chat`): streaming, items, approvals, AskUserQuestion, ExitPlanMode, hooks (config check after YAML edits, restart guard, backup before first edit, undo snapshots).
- `server/hub.ts`: open chats, websocket clients, chat list, model list, usage meter, phone notifications, scheduled health check.
- `server/auth.ts`: which credential Claude Code gets, and "Sign in with Claude" (`claude setup-token` run in a pseudo-terminal by `server/pty_helper.py`, because its paste prompt needs a TTY).
- `server/ha.ts`: Supervisor and Home Assistant API: home cards, context for the system prompt, @ mentions, notify, backups, config check.
- `server/policy.ts`: what needs approval and how approval cards describe it.
- `shared/types.ts`: types and websocket messages shared by server and page.

## Constraints

- Server code must stay erasable-syntax-only TypeScript (no enums, no parameter properties) and import with `.ts` extensions, because Node runs it directly.
- Page URLs stay relative (`api/...`, `ws`, Vite `base: './'`) so it works behind ingress. The page asks Home Assistant for its route with `home-assistant/subscribe-properties`; dashboard links use `/<slug>/ask/<question>`.
- Only the ingress proxy (172.30.32.2) may reach the server on Home Assistant: the page has no login of its own.
- Reading must never ask for approval; anything that changes files, calls services or restarts must. A restart always asks, even after "Allow for this chat".
- Never cut text off in the page (no ellipsis, no fixed widths): titles and values wrap; long tool output scrolls inside its box.
- Target hardware is a Home Assistant Green (ARM, 4 GB): idle chat processes close after 15 minutes.
- Every version bump needs a `CHANGELOG.md` entry (newest first, plain words for the user).
