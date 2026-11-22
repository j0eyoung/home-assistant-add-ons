import { useEffect, useState } from 'react'
import type { AppState, HomeCard } from '../../shared/types.ts'
import { api } from './api.ts'
import { Icon, Spark } from './Icon.tsx'
import { Composer } from './Composer.tsx'
import type { Outgoing } from './Composer.tsx'
import { SignIn } from './SignIn.tsx'

type Props = {
  state: AppState | null
  draft: { text: string; n: number } | null
  setDraft: (text: string) => void
  settings: { model: string; effort: string; mode: string }
  setSettings: (s: { model?: string; effort?: string; mode?: string }) => void
  onSend: (o: Outgoing) => void
  onAuthChanged: () => void
  onOpenChat: (id: string) => void
}

const SUGGESTIONS = [
  { label: 'Write an automation', text: 'Write an automation that ' },
  { label: 'Explain an error', text: 'Explain this error from my log and how to fix it: ' },
  { label: 'Tidy up my dashboards', text: 'Look at my dashboards and suggest how to make them tidier and easier to use on a phone.' },
  { label: 'Find entities I never use', text: 'Find entities that no automation, script or dashboard uses, and devices that look abandoned. Just list them; don’t delete anything.' },
]

function greeting(name: string): string {
  const h = new Date().getHours()
  const part = h < 5 ? 'Good evening' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
  return name ? `${part}, ${name}` : part
}

export function Home(p: Props) {
  const [cards, setCards] = useState<HomeCard[] | null>(null)
  const [loading, setLoading] = useState(false)
  const signedIn = p.state?.auth.signedIn ?? false

  const load = async (refresh = false) => {
    setLoading(true)
    const c = await api<HomeCard[]>(`home${refresh ? '?refresh=1' : ''}`).catch(() => [])
    setCards(c)
    setLoading(false)
  }

  useEffect(() => {
    void load()
  }, [])

  return (
    <div className="home">
      <h1 className="greet">
        <Spark size={30} />
        {greeting(p.state?.user ?? '')}
      </h1>
      {p.state && !signedIn ? (
        <div className="card signincard">
          <SignIn info={p.state.auth} onChanged={p.onAuthChanged} compact />
        </div>
      ) : (
        <Composer
          big
          placeholder="How can I help with your home?"
          running={false}
          models={p.state?.models ?? []}
          commands={p.state?.commands ?? []}
          model={p.settings.model}
          effort={p.settings.effort}
          mode={p.settings.mode}
          onChange={p.setSettings}
          onSend={p.onSend}
          onStop={() => {}}
          draft={p.draft}
        />
      )}
      {cards && cards.length > 0 && (
        <div className="cardsec">
          <div className="cardsechead">
            <span>Your home right now</span>
            <button type="button" className="iconbtn" aria-label="Refresh" title="Refresh" onClick={() => void load(true)} disabled={loading}>
              <Icon name="refresh" size={14} className={loading ? 'spinning' : ''} />
            </button>
          </div>
          <div className="homecards">
            {cards.map((c) => (
              <button type="button" key={c.key} className="homecard" onClick={() => signedIn && p.onSend({ text: c.prompt, images: [], mentions: [] })} disabled={!signedIn}>
                <span className="hctitle">
                  <span className={`sev ${c.level}`} />
                  {c.title}
                </span>
                <span className="hcdetail">{c.detail}</span>
                <span className="hcaction">
                  {c.action} <Icon name="right" size={12} />
                </span>
              </button>
            ))}
          </div>
          {p.state?.ha.demo && <p className="hint center">Sample data: this copy isn’t running on Home Assistant.</p>}
        </div>
      )}
      {cards && !cards.length && p.state && !p.state.ha.connected && <p className="hint center">The cards about your home appear when Claude Chat runs on Home Assistant.</p>}
      <div className="suggest">
        {SUGGESTIONS.map((s) => (
          <button type="button" key={s.label} className="chipbtn" onClick={() => p.setDraft(s.text)}>
            {s.label}
          </button>
        ))}
        <button
          type="button"
          className="chipbtn"
          disabled={!signedIn}
          onClick={async () => {
            const r = await api<{ ok: boolean; chatId?: string }>('health/run', { method: 'POST' }).catch(() => null)
            if (r?.chatId) p.onOpenChat(r.chatId)
          }}
        >
          <Icon name="heart" size={14} /> Run a health check
        </button>
      </div>
    </div>
  )
}
