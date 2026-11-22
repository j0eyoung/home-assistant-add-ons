# Claude Chat

Chat with Claude Code about your Home Assistant, the way you would in the Claude desktop app. Claude can read and change your configuration, look at states, history, traces and the log, and call services. You approve each change.

## Signing in

You need a Claude Pro or Max plan (or an Anthropic API key, billed to that API account). Any of these works:

1. **addon_secrets.json.** If the shared secrets file in your config folder has `claude_code_oauth_token`, Claude Chat uses it and you're signed in from the start.
2. **Sign in with Claude.** Open the panel, choose **Sign in with Claude**, open the Claude page, approve, and paste the code it shows back into the panel. The add-on keeps the token (valid for a year) in its own storage.
3. **Paste a token or API key.** Make a token with `claude setup-token` on any computer where Claude Code is installed, or paste an API key (`sk-ant-api…`).

Settings › Account shows which sign-in is in use. Signing in on the page takes over from the add-on option and addon_secrets.json.

## Using it

- **Home screen.** Cards show today's log errors, unavailable entities, waiting updates and your last backup. They come straight from Home Assistant and use no Claude usage until you tap one, which starts a chat about it.
- **@ mentions.** Type `@` and pick an entity or area. Claude gets its current state and attributes with your message.
- **Slash commands.** Type `/` for Claude Code commands such as `/compact` (summarize a long chat) and your own commands in `/config/.claude/commands`.
- **Pictures.** Paste, drop or attach screenshots.
- **Model, effort and approvals** are in the chat box. New chats start with the add-on's options (Sonnet, high effort, "Ask before edits").

### Approval modes

| Mode | What happens |
|---|---|
| Ask before edits | Reading never asks. File edits, commands and service calls each show a card. |
| Edit automatically | File edits go ahead; commands and service calls still ask. |
| Plan mode | Claude looks around and writes a plan. You approve it before anything changes. |
| Don't ask | Everything runs without asking. Use with care. |

"Allow for this chat" on a card stops that kind of action from asking again in that chat. A restart always asks.

## Safety

- After Claude edits a YAML file, Home Assistant's configuration check runs and Claude sees the result. A restart is refused while the check fails.
- Each file edit has **Undo this change**. If the file has changed again since, Claude Chat tells you and offers to undo anyway.
- Settings › Safety can make a partial backup (configuration only, no database) before Claude's first edit in each chat.
- Claude is told not to edit `/config/.storage` while Home Assistant runs, and to reload what changed rather than restart.

## Settings

- **Phone notifications.** Pick your phone's `notify.mobile_app_…` service. You get a push when Claude needs your OK or finishes a job that took more than a minute, either only when you aren't looking at that chat or always.
- **Health check.** Claude reviews errors, unavailable devices, failed automations, updates and backups, and replies with a summary. It only reads. Run it from the home screen, or schedule it daily or weekly. Each run uses some of your plan.
- **House memory.** Notes Claude reads in every chat (`/config/CLAUDE.md`): room names, who lives here, how you like automations written. Say "remember …" in a chat and Claude adds a line.
- **Ask Claude from a dashboard.** Type a question and copy the button card it makes. Tapping the button opens Claude Chat with the question typed in, ready to send.

## Add-on options

| Option | Meaning |
|---|---|
| `claude_code_oauth_token` | A token from `claude setup-token`. Optional; filled from addon_secrets.json when blank. |
| `model` | Model for new chats: `sonnet`, `opus`, `haiku` or a full model id. |
| `effort` | Effort for new chats: low, medium, high, xhigh or max. |
| `permission_mode` | Approval mode for new chats (see above). |
| `working_directory` | Folder Claude works in. Blank means `/config`. |
| `enable_ha_mcp` | Give Claude the ha-mcp Home Assistant tools. Without them Claude uses the Home Assistant API directly. |
| `ha_mcp_version` | ha-mcp version to run. |

## What it can reach

The same as Claude Terminal: Home Assistant's configuration at `/config`, other add-ons' configuration at `/addon_configs`, `/share`, the Supervisor API and the Home Assistant API. The panel is only reachable through Home Assistant's sidebar (ingress) and only for administrators.

Chats, settings and the sign-in live in the add-on's own storage and are included in Home Assistant backups. Downloads that come back on their own (ha-mcp's Python) are left out.
