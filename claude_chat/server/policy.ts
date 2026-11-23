// Which tool calls need the user's OK, and how an approval card describes them.
// Reading never asks; changing files, calling services, restarting and running
// commands always do (unless the chat's mode or an "allow for this chat" says otherwise).

export const EDIT_TOOLS = new Set(['Edit', 'Write', 'MultiEdit', 'NotebookEdit'])

// Built-in tools that only read. Claude Code already allows most of these;
// listing them keeps reads outside the working folder (/share, /addon_configs) quiet too.
// Skill only loads a skill's instructions (such as the bundled Home Assistant best practices).
export const READ_TOOLS = ['Read', 'Glob', 'Grep', 'LS', 'TodoWrite', 'WebSearch', 'WebFetch', 'ToolSearch', 'ListMcpResourcesTool', 'ReadMcpResourceTool', 'Skill']

const MCP_WRITE = /(call|set|create|update|delete|remove|restart|reload|rename|enable|disable|toggle|turn|trigger|fire|install|uninstall|write|save|execute|run|start|stop|backup|restore|edit|add|assign|import|apply|move|reset|purge|send|notify)/i
const MCP_READ = /(get|list|search|find|read|fetch|describe|overview|history|logbook|trace|check|render|status|info|state|statistics|logs|query|show|summar|evaluate|explain|count|validate)/i

// ha-mcp and other MCP tools: allow ones whose names say they only read.
export function isReadOnlyMcp(toolName: string): boolean {
  if (!toolName.startsWith('mcp__')) return false
  const name = toolName.split('__').slice(2).join('__') || toolName
  return MCP_READ.test(name) && !MCP_WRITE.test(name)
}

const RESTART_RE = /(supervisor\/core\/restart|supervisor\/host\/reboot|supervisor\/host\/shutdown|\bha\s+(core|host)\s+(restart|reboot|shutdown|stop)|services\/homeassistant\/(restart|stop)|homeassistant\.(restart|stop))/i

export function isRestart(toolName: string, input: any): boolean {
  if (toolName.startsWith('mcp__') && /restart|reboot|shutdown/i.test(toolName)) return true
  if (toolName.startsWith('mcp__') && /call_service|service/i.test(toolName)) {
    const s = JSON.stringify(input ?? {})
    if (/homeassistant["'.\s,:]*(restart|stop)|"service":\s*"(restart|stop)"/i.test(s) && /homeassistant/i.test(s)) return true
  }
  if (toolName === 'Bash') return RESTART_RE.test(String(input?.command ?? ''))
  return false
}

export function filePathOf(input: any): string {
  return String(input?.file_path ?? input?.notebook_path ?? input?.path ?? '')
}

const base = (p: string) => p.split(/[\\/]/).pop() || p

export function describe(toolName: string, input: any, sdkTitle?: string): { title: string; risk?: string } {
  const restart = isRestart(toolName, input)
  if (restart) return { title: 'Claude wants to restart Home Assistant', risk: 'Home Assistant will be offline for a minute or two. The add-on checks the configuration first.' }
  if (EDIT_TOOLS.has(toolName)) {
    const p = filePathOf(input)
    const name = base(p)
    const risk = /\.storage[\\/]/.test(p)
      ? 'This file is Home Assistant’s internal storage. Editing it while Home Assistant runs can lose changes or break things.'
      : /secrets\.yaml$/.test(p)
        ? 'This file holds your passwords and keys.'
        : undefined
    return { title: toolName === 'Write' ? `Claude wants to write ${name}` : `Claude wants to edit ${name}`, risk }
  }
  if (toolName === 'Bash') {
    const cmd = String(input?.command ?? '')
    const risk = /\brm\s+-|\bmv\s|\bdd\s|\bmkfs|\bchmod\s|\bchown\s/.test(cmd)
      ? 'This command deletes, moves or changes permissions on files.'
      : /curl[^|]*-X\s*(POST|PUT|DELETE)|--data|\s-d\s/.test(cmd) && /supervisor/.test(cmd)
        ? 'This command changes something in Home Assistant through its API.'
        : undefined
    return { title: sdkTitle || 'Claude wants to run a command', risk }
  }
  if (toolName.startsWith('mcp__')) {
    const [, server, ...rest] = toolName.split('__')
    const action = rest.join('__').replace(/^ha_/, '').replace(/_/g, ' ')
    const svc = input?.domain && input?.service ? ` (${input.domain}.${input.service})` : ''
    return { title: sdkTitle || `Claude wants to use ${server === 'home-assistant' ? 'Home Assistant' : server}: ${action}${svc}` }
  }
  return { title: sdkTitle || `Claude wants to use ${toolName}` }
}

// The key "Allow for this chat" remembers, and the button text for it.
export function alwaysKey(toolName: string): { key: string; label: string } {
  if (EDIT_TOOLS.has(toolName)) return { key: 'edits', label: 'Allow file edits in this chat' }
  if (toolName === 'Bash') return { key: 'Bash', label: 'Allow commands in this chat' }
  if (toolName.startsWith('mcp__')) {
    const action = toolName.split('__').slice(2).join(' ').replace(/^ha_/, '').replace(/_/g, ' ')
    return { key: toolName, label: `Allow “${action}” in this chat` }
  }
  return { key: toolName, label: `Allow ${toolName} in this chat` }
}
