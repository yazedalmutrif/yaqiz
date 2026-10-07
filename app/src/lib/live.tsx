import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api } from './api'
import type { CameraStatus, Heat, SafetyEvent, Stats, Track } from './types'
import { voice } from './voice'

interface LiveState {
  connected: boolean
  stats: Record<number, Stats>
  positions: Record<number, { at: number; tracks: Track[] }>
  events: SafetyEvent[]
  heat: Heat | null
  cameraStatus: Record<number, CameraStatus>
}
type Listener = (e: SafetyEvent, action: string) => void
interface LiveApi {
  state: LiveState
  onEvent: (fn: Listener) => () => void
  upsert: (e: SafetyEvent) => void
  setHeat: (h: Heat) => void
}

const LiveCtx = createContext<LiveApi | null>(null)
const MAX_EVENTS = 200

function merge(incoming: SafetyEvent[], current: SafetyEvent[]): SafetyEvent[] {
  const byId = new Map(current.map((e) => [e.id, e]))
  for (const e of incoming) byId.set(e.id, e)
  return [...byId.values()].sort((a, b) => b.ts.localeCompare(a.ts) || b.id - a.id).slice(0, MAX_EVENTS)
}

export function LiveProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LiveState>({ connected: false, stats: {}, positions: {}, events: [], heat: null, cameraStatus: {} })
  const listeners = useRef(new Set<Listener>())
  const lastStats = useRef<Record<number, number>>({})

  // A camera that says "running" but sends no live numbers for 6 s is shown as stalled.
  useEffect(() => {
    const id = setInterval(() => {
      const now = Date.now()
      setState((s) => {
        let changed = false
        const cs = { ...s.cameraStatus }
        for (const c of Object.values(cs)) {
          const last = lastStats.current[c.id]
          if (c.state === 'running' && last && now - last > 6000) {
            cs[c.id] = { ...c, state: 'stalled' }
            changed = true
          }
        }
        return changed ? { ...s, cameraStatus: cs } : s
      })
    }, 2000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    let ws: WebSocket | null = null
    let stopped = false
    let retry = 0
    let timer: ReturnType<typeof setTimeout> | undefined

    api.events({ limit: 80 }).then((r) => setState((s) => ({ ...s, events: merge(r.items, s.events) }))).catch(() => undefined)
    api.heat().then((h) => setState((s) => ({ ...s, heat: h }))).catch(() => undefined)

    const handle = (msg: { type: string; [k: string]: unknown }) => {
      switch (msg.type) {
        case 'hello': {
          const cams = (msg.cameras as CameraStatus[]) ?? []
          setState((s) => ({ ...s, cameraStatus: Object.fromEntries(cams.map((c) => [c.id, c])) }))
          break
        }
        case 'camera_status': {
          const c = msg.camera as CameraStatus
          setState((s) => ({ ...s, cameraStatus: { ...s.cameraStatus, [c.id]: c } }))
          break
        }
        case 'stats': {
          const st = msg as unknown as Stats
          lastStats.current[st.camera_id] = Date.now()
          setState((s) => ({
            ...s,
            stats: { ...s.stats, [st.camera_id]: st },
            cameraStatus: { ...s.cameraStatus, [st.camera_id]: { ...(s.cameraStatus[st.camera_id] ?? { id: st.camera_id }), state: st.state, fps: st.fps, people: st.people, in_zone: st.in_zone, latency_ms: st.latency_ms, latency_p95_ms: st.latency_p95_ms } },
          }))
          break
        }
        case 'positions':
          setState((s) => ({ ...s, positions: { ...s.positions, [msg.camera_id as number]: { at: Date.now(), tracks: msg.tracks as Track[] } } }))
          break
        case 'heat':
          setState((s) => ({ ...s, heat: msg.heat as Heat }))
          break
        case 'event': {
          const e = msg.event as SafetyEvent
          const action = msg.action as string
          setState((s) => ({ ...s, events: merge([e], s.events) }))
          if (action === 'open') voice.announce(e.kind, e.item, e.severity === 'critical')
          listeners.current.forEach((fn) => fn(e, action))
          break
        }
      }
    }

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/api/ws`)
      ws.onopen = () => {
        retry = 0
        setState((s) => ({ ...s, connected: true }))
        api.events({ limit: 80 }).then((r) => setState((s) => ({ ...s, events: merge(r.items, s.events) }))).catch(() => undefined)
      }
      ws.onmessage = (m) => {
        try {
          handle(JSON.parse(m.data))
        } catch {
          /* ignore malformed */
        }
      }
      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }))
        if (!stopped) timer = setTimeout(connect, Math.min(10_000, 1000 * 2 ** retry++))
      }
    }
    connect()
    return () => {
      stopped = true
      clearTimeout(timer)
      ws?.close()
    }
  }, [])

  const onEvent = useCallback((fn: Listener) => {
    listeners.current.add(fn)
    return () => void listeners.current.delete(fn)
  }, [])
  const upsert = useCallback((e: SafetyEvent) => setState((s) => ({ ...s, events: merge([e], s.events) })), [])
  const setHeat = useCallback((h: Heat) => setState((s) => ({ ...s, heat: h })), [])
  const value = useMemo(() => ({ state, onEvent, upsert, setHeat }), [state, onEvent, upsert, setHeat])
  return <LiveCtx.Provider value={value}>{children}</LiveCtx.Provider>
}

export function useLive(): LiveApi {
  const ctx = useContext(LiveCtx)
  if (!ctx) throw new Error('useLive must be used inside LiveProvider')
  return ctx
}

/** Fresh plan positions from all calibrated cameras (stale tracks drop after 1.5 s). */
export function useTracks(now: number) {
  const { state } = useLive()
  return useMemo(() => {
    const out: (Track & { camera_id: number })[] = []
    for (const [cid, p] of Object.entries(state.positions)) {
      if (now - p.at < 1500) for (const t of p.tracks) out.push({ ...t, camera_id: Number(cid) })
    }
    return out
  }, [state.positions, now])
}
