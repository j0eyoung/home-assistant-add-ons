import type { ClientMsg, ServerMsg } from '../../shared/types.ts'

// All URLs stay relative so the page works behind Home Assistant ingress.

export async function api<T = any>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init
  const r = await fetch(`api/${path}`, {
    ...rest,
    headers: json !== undefined ? { 'Content-Type': 'application/json', ...(rest.headers ?? {}) } : rest.headers,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data?.error || `Request failed (${r.status})`)
  return data as T
}

type Listener = (msg: ServerMsg) => void

// One websocket for the page, reconnecting on its own.
export class Socket {
  ws: WebSocket | null = null
  listeners = new Set<Listener>()
  onOpen: (() => void) | null = null
  onState: ((connected: boolean) => void) | null = null
  queue: string[] = []
  delay = 500
  closed = false

  constructor() {
    this.connect()
    document.addEventListener('visibilitychange', () => this.send({ t: 'visible', visible: document.visibilityState === 'visible' }))
  }

  connect(): void {
    const url = new URL('ws', window.location.href)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(url)
    this.ws = ws
    ws.onopen = () => {
      this.delay = 500
      this.onState?.(true)
      ws.send(JSON.stringify({ t: 'visible', visible: document.visibilityState === 'visible' }))
      this.onOpen?.()
      for (const m of this.queue.splice(0)) ws.send(m)
    }
    ws.onmessage = (ev) => {
      let msg: ServerMsg
      try {
        msg = JSON.parse(String(ev.data))
      } catch {
        return
      }
      for (const l of this.listeners) l(msg)
    }
    ws.onclose = () => {
      this.onState?.(false)
      if (this.closed) return
      setTimeout(() => this.connect(), this.delay)
      this.delay = Math.min(this.delay * 2, 8000)
    }
  }

  send(msg: ClientMsg): void {
    const data = JSON.stringify(msg)
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(data)
    else if (msg.t !== 'visible') this.queue.push(data)
  }

  listen(l: Listener): () => void {
    this.listeners.add(l)
    return () => this.listeners.delete(l)
  }
}

// Shrink a picture in the browser before it goes to Claude (long side 1568 px).
export async function readImage(file: File): Promise<{ data: string; mediaType: string; url: string } | null> {
  if (!file.type.startsWith('image/')) return null
  const url = URL.createObjectURL(file)
  const img = new Image()
  await new Promise((res, rej) => {
    img.onload = res
    img.onerror = rej
    img.src = url
  }).catch(() => null)
  if (!img.width) return null
  const scale = Math.min(1, 1568 / Math.max(img.width, img.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(img.width * scale)
  canvas.height = Math.round(img.height * scale)
  canvas.getContext('2d')!.drawImage(img, 0, 0, canvas.width, canvas.height)
  const png = file.type === 'image/png' && canvas.width * canvas.height < 1_500_000
  const mediaType = png ? 'image/png' : 'image/jpeg'
  const dataUrl = canvas.toDataURL(mediaType, 0.88)
  return { data: dataUrl.split(',')[1], mediaType, url: dataUrl }
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    ta.remove()
    return ok
  }
}
