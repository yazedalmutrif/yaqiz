import { gsap } from 'gsap'
import { useEffect, useRef, useState } from 'react'
import { streamUrl } from '../lib/api'
import { STATE_LABEL, ago, camCode, eventTitle, fmtDuration, fmtNum, fmtTime, workersAr } from '../lib/format'
import { useReducedMotion } from '../lib/hooks'
import type { Camera, CameraStatus, SafetyEvent } from '../lib/types'
import { IconCheck, IconExpand } from './Icons'

/** A number that eases to its new value (GSAP), so changing counts read as change, not flicker. */
export function Kpi({ value, label, digits = 0, suffix = '', tone }: { value: number | null; label: string; digits?: number; suffix?: string; tone?: 'alert' | 'warn' }) {
  const ref = useRef<HTMLElement>(null)
  const prev = useRef(value ?? 0)
  const reduce = useReducedMotion()
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (value === null) {
      el.textContent = '–'
      return
    }
    const from = { v: prev.current }
    prev.current = value
    if (reduce) {
      el.textContent = fmtNum(value, digits) + suffix
      return
    }
    const tw = gsap.to(from, { v: value, duration: 0.6, ease: 'power2.out', onUpdate: () => { el.textContent = fmtNum(from.v, digits) + suffix } })
    return () => { tw.kill() }
  }, [value, digits, suffix, reduce])
  return (
    <div className={`kpi ${tone ? `kpi--${tone}` : ''}`}>
      <b ref={ref}>{value === null ? '–' : fmtNum(value, digits) + suffix}</b>
      <span>{label}</span>
    </div>
  )
}

export function CameraTile({ cam, status, focus, onFocus }: { cam: Camera; status?: CameraStatus; focus?: boolean; onFocus?: () => void }) {
  const [nonce, setNonce] = useState(0)
  const state = status?.state ?? (cam.enabled ? 'starting' : 'stopped')
  const inZone = status?.in_zone ?? 0
  return (
    <figure className={`tile ${focus ? 'tile--focus' : ''}`}>
      <div className="tile__bar">
        <span className={`state-dot state-dot--${state}`} title={STATE_LABEL[state] ?? state} />
        <span className="code">{camCode(cam.id)}</span>
        <span className="name">{cam.name}</span>
        <span className="meta">
          <span className="ltr">{fmtNum(status?.fps ?? null, 1)} FPS</span>
          {status?.latency_ms != null && <span className="ltr" title="من التقاط الإطار حتى نشر التنبيهات وصورة البث (الوسيط)">{fmtNum(status.latency_ms, 0)} ms</span>}
          <span>{workersAr(status?.people ?? 0)}</span>
          {inZone > 0 && <span style={{ color: '#ff6b63', fontWeight: 600 }}>{inZone} داخل منطقة خطر</span>}
        </span>
        {onFocus && (
          <button type="button" onClick={onFocus} aria-label={focus ? 'تصغير' : 'تكبير'} title={focus ? 'تصغير' : 'تكبير'}>
            <IconExpand />
          </button>
        )}
      </div>
      <div className="tile__view">
        {cam.enabled && (
          <img src={`${streamUrl(cam.id)}?n=${nonce}`} alt={`بث مباشر من ${cam.name}`} onError={() => setTimeout(() => setNonce((n) => n + 1), 3000)} />
        )}
        {state !== 'running' && (
          <div className="tile__state">
            <div>
              {STATE_LABEL[state] ?? state}
              {status?.error && (<><br /><small>{status.error}</small></>)}
            </div>
          </div>
        )}
      </div>
    </figure>
  )
}

export function AlertCard({ e, now, onAck, onZoom }: { e: SafetyEvent; now: number; onAck: (e: SafetyEvent) => void; onZoom: (url: string) => void }) {
  const signal = e.detail.operator_signal
  return (
    <article className={`alert ${e.severity === 'critical' ? 'alert--critical' : ''} ${e.acknowledged ? 'alert--acked' : ''}`}>
      <div>
        <h3>{eventTitle(e)}</h3>
        <p className="row" style={{ marginTop: 2 }}>
          <span>{e.detail.zone_name ?? 'خارج المناطق'}</span>
          <span className="ltr">{camCode(e.camera_id)}</span>
          <span title={fmtTime(e.ts)}>{ago(e.ts, now)}</span>
        </p>
        <div className="row">
          {e.ended_at ? <span style={{ fontSize: 12 }}>المدة {fmtDuration(e.duration_s)}</span> : <span className="tag">مستمر</span>}
          {e.detail.escalated && <span className="tag" style={{ color: '#ff6b63' }}>تصعيد</span>}
          {signal && <span className="tag tag--sim">إشارة لمشغّل المعدة {signal.mode === 'simulated' ? '(محاكاة)' : ''}</span>}
          {!e.acknowledged ? (
            <button type="button" className="btn btn--sm" onClick={() => onAck(e)}><IconCheck />تم الاطلاع</button>
          ) : (
            <span style={{ fontSize: 12 }}>تم الاطلاع</span>
          )}
        </div>
      </div>
      {e.snapshot_url ? (
        <img src={e.snapshot_url} alt={`لقطة: ${eventTitle(e)}`} loading="lazy" onClick={() => onZoom(e.snapshot_url!)} />
      ) : (
        <div />
      )}
    </article>
  )
}

export function Lightbox({ url, onClose }: { url: string | null; onClose: () => void }) {
  useEffect(() => {
    if (!url) return
    const onKey = (ev: KeyboardEvent) => ev.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [url, onClose])
  if (!url) return null
  return (
    <div className="lightbox" role="dialog" aria-modal="true" aria-label="لقطة الحدث" onClick={onClose}>
      <img src={url} alt="لقطة الحدث مكبّرة (الوجوه مموّهة)" />
    </div>
  )
}

export function Toast({ toast }: { toast: { text: string; kind: 'ok' | 'err' } | null }) {
  if (!toast) return null
  return <div className={`toast ${toast.kind === 'err' ? 'toast--err' : ''}`} role="status">{toast.text}</div>
}
