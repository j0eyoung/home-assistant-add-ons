# Changelog

## 0.2.0 - Quotes and Best Practices

### 🌟 Features
* **Quote part of a reply.** Select any text in the conversation and tap **Quote**. It sits above your next message so you can ask about that exact line, and it shows as a quote in the chat afterwards. You can add several quotes to one message and remove one with ×.
* **Home Assistant best practices built in.** Claude now has the Home Assistant best-practices skill from homeassistant-ai/skills, the people behind ha-mcp. Before writing or changing automations, scripts, scenes, helpers, templates, blueprints or dashboards, Claude reads it: native triggers and conditions instead of templates, the right helper, the right automation mode, checking what uses an entity before renaming it, and safe backups.

### 🔧 Improvements
* Loading a skill never asks for approval, and it shows in the chat as "Used skill home assistant best practices".
* A chat that starts with a quote is named after your question, not the quoted text.

## 0.1.1 - Health Check Takeover

### 🐞 Fixes
* **Act on the health check in its own chat.** The scheduled health check still only reads. Once you reply in its chat, Claude can make the changes you ask for there, and each one shows the usual approval card. Before, every change in that chat was refused with "This is an unattended health check: read only".

## 0.1.0 - Claude Chat

### 🌟 Features
* **Chat with Claude like the Claude desktop app.** Your chats on the left, a conversation in the middle, Claude's replies streaming in as it writes. Each step Claude takes (reading a file, searching, running a command, asking Home Assistant) folds into a one-line row you can open. Chats are kept across restarts and you can rename, search and delete them.
* **A home screen that reads your Home Assistant.** Cards show today's log errors, unavailable devices, waiting updates and your last backup. Tap one to start a chat about it with the details already attached.
* **Sign in without a terminal.** It uses the `claude_code_oauth_token` in `addon_secrets.json` if you have one. Otherwise use "Sign in with Claude" (open the Claude page, approve, paste the code back), or paste a token or an API key.
* **Approvals you can read.** When Claude wants to edit a file, run a command or call a service, a card shows exactly what will change (a diff for files) with Allow, Allow for this chat, or Deny. Reading never asks. A restart is labeled as one.
* **Configuration check guard.** After Claude edits any YAML file, Home Assistant's configuration check runs and the result goes back to Claude. A restart is blocked while the check fails.
* **Undo each change.** Every file edit gets an "Undo this change" link. Optionally, a backup of your configuration is made before Claude's first edit in a chat (Settings › Safety).
* **@ mentions.** Type @ to pick an entity or area. Its current state goes along with your message.
* **Phone notifications.** Get a push when Claude needs your OK or finishes a long job (Settings › Phone notifications).
* **House memory.** Notes Claude reads in every chat, kept in `/config/CLAUDE.md`. Edit them in Settings, or say "remember …" in a chat.
* **Pictures.** Paste or drop a screenshot into the chat box.
* **Health check.** Claude reviews errors, unavailable devices, failed automations, updates and backups, then sends you a summary. Run it from the home screen, or schedule it daily or weekly.
* **Ask Claude from a dashboard.** Settings builds a button card that opens Claude Chat with a question already typed in.
* **Slash commands.** Type / for Claude Code's commands, such as /compact, plus your own from `/config/.claude/commands`.
* **Usage meter.** Shows how much of your plan's 5-hour limit is used and when it resets.
* **Knows Home Assistant like Claude Terminal does.** The same folders (/config, /addon_configs, /share), the Supervisor and Home Assistant APIs, and the ha-mcp tools. New chats start on Sonnet at high effort; switch model, effort and approval mode from the chat box.
