# Changelog

## [0.2.0] - 2026-05-22

### Skill content

- `references/yaml-configs.md`: added pin advanced schema, time duration formats, expanded filter catalogue (27+ types: `median`, `delta`, `throttle`, `debounce`, `calibrate_linear`, etc.), packages `!extend`/`!remove`, remote GitHub packages, `disabled_by_default`, `expire_after`, `on_raw_value`
- `references/home-assistant.md`: fixed critical error (HA disables device actions by default — must be enabled per device); added `reboot_timeout` gotcha, `api.connected` condition, action responses (ESPHome 2025.10.0+), device replacement (ESPHome 2025.4.0+)
- `references/debugging.md`: added `fast_connect` for hidden SSIDs, CPU frequency tuning, log level impact on single-core networking, USB charging-only cable checklist, NVS overflow recovery for `restore_value` failures

### Repo structure

- Single canonical location per skill: everything (SKILL.md, references, README, CHANGELOG, LICENSE, scripts) now lives under `skills/<name>/` — no separate wrapper directory
- Native runtime discovery wired up: `.claude/skills/` symlink (Claude Code), `.opencode/skills/` symlink (OpenCode), `GEMINI.md` (Gemini CLI), `AGENTS.md` (Codex)
- OpenCode plugin support: `package.json` + `.opencode/plugins/agent-skills.js` — install via `opencode.json` plugin entry
- CI workflow path updated to match consolidated layout

## [0.1.0] - 2026-05-22

Initial release.

### Skill content

- `SKILL.md` (~70 lines): three-layer router (YAML / external components / Home Assistant integration) plus a debugging cross-cut
- `references/yaml-configs.md`: device YAML structure, lambdas, filters, naming, sensor entity setup, framework choice (Arduino vs ESP-IDF)
- `references/external-components.md`: aligned with the canonical [ESPHome Developer Documentation](https://developers.esphome.io/architecture/components/). Covers Python schema + codegen, C++ class structure (C++17 nested-namespace style), the full lifecycle (`setup`/`loop`/`update`/`dump_config`), module-level flags (`AUTO_LOAD`, `DEPENDENCIES`, `MULTI_CONF`, `FINAL_VALIDATE_SCHEMA`), the four-method shutdown sequence (`on_safe_shutdown`/`on_shutdown`/`teardown`/`on_powerdown`), `get_setup_priority` with the standard values, bus device classes (I²C, SPI, UART), and current ESPHome 2026.x breaking-change notes.
- `references/home-assistant.md`: native API vs MQTT, `device_class`/`state_class` for proper HA integration, on-device vs HA-side automation guidance, pulling state from HA into the device, Bluetooth proxy.
- `references/debugging.md`: boot loops, WiFi instability, OTA failures, sensor garbage, memory exhaustion, with concrete first-questions to ask the user.

### Repo infrastructure

- Standalone `scripts/validate_skill.py` (no Anthropic-internal dependencies — just PyYAML)
- GitHub Actions workflow that validates the skill format and builds a `.skill` bundle as an artifact on every push
- MIT license
