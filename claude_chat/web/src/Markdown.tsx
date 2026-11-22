import { memo, useMemo } from 'react'
import { Marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js/lib/core'
import yaml from 'highlight.js/lib/languages/yaml'
import json from 'highlight.js/lib/languages/json'
import bash from 'highlight.js/lib/languages/bash'
import python from 'highlight.js/lib/languages/python'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import ini from 'highlight.js/lib/languages/ini'
import diff from 'highlight.js/lib/languages/diff'
import plaintext from 'highlight.js/lib/languages/plaintext'
import { copyText } from './api.ts'

hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('json', json)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('python', python)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('ini', ini)
hljs.registerLanguage('diff', diff)
hljs.registerLanguage('plaintext', plaintext)
hljs.registerAliases(['yml', 'jinja', 'jinja2'], { languageName: 'yaml' })
hljs.registerAliases(['sh', 'shell', 'console', 'zsh'], { languageName: 'bash' })
hljs.registerAliases(['js'], { languageName: 'javascript' })
hljs.registerAliases(['ts'], { languageName: 'typescript' })
hljs.registerAliases(['html', 'svg'], { languageName: 'xml' })
hljs.registerAliases(['toml', 'conf'], { languageName: 'ini' })
hljs.registerAliases(['text', 'txt', 'log'], { languageName: 'plaintext' })

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

export function highlight(code: string, lang?: string): string {
  const l = (lang ?? '').toLowerCase()
  if (l && hljs.getLanguage(l)) {
    try {
      return hljs.highlight(code, { language: l, ignoreIllegals: true }).value
    } catch {
      return esc(code)
    }
  }
  return esc(code)
}

const marked = new Marked({ gfm: true, breaks: false })
marked.use({
  renderer: {
    code(token: any) {
      const lang = String(token.lang ?? '').split(/\s/)[0]
      return `<div class="codeblock"><div class="codehead"><span>${esc(lang || 'code')}</span><button type="button" class="copybtn" data-copy>Copy</button></div><pre><code class="hljs">${highlight(token.text, lang)}</code></pre></div>`
    },
  },
})

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

export function renderMarkdown(text: string): string {
  const html = marked.parse(text, { async: false }) as string
  return DOMPurify.sanitize(html, { ADD_ATTR: ['target', 'data-copy'] })
}

function onClick(e: React.MouseEvent<HTMLDivElement>) {
  const btn = (e.target as HTMLElement).closest('[data-copy]') as HTMLElement | null
  if (!btn) return
  const code = btn.closest('.codeblock')?.querySelector('code')?.textContent ?? ''
  void copyText(code).then((ok) => {
    btn.textContent = ok ? 'Copied' : 'Copy failed'
    setTimeout(() => (btn.textContent = 'Copy'), 1500)
  })
}

export const Markdown = memo(function Markdown({ text, className }: { text: string; className?: string }) {
  const html = useMemo(() => renderMarkdown(text), [text])
  return <div className={`md ${className ?? ''}`} onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} />
})
