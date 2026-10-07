import { useMemo, useState } from 'react'
import { SitePlan } from '../components/SitePlan'
import { api } from '../lib/api'
import { ago, camCode, cloudPath, eventTitle, eventsAr, pointInPolygon, todayRiyadh, workersAr } from '../lib/format'
import { useApi, useNow } from '../lib/hooks'
import { useLive, useTracks } from '../lib/live'
import type { SafetyEvent } from '../lib/types'

/** S-02: where is everyone, and where are the alerts? Live positions projected from every calibrated camera. */
export function PlanLive() {
  const site = useApi(api.site)
  const zones = useApi(api.zones)
  const now = useNow(500)
  const tracks = useTracks(now)
  const { state } = useLive()
  const [heatmap, setHeatmap] = useState(false)
  const today = todayRiyadh()
  const todayEvents = useApi(() => api.events({ since: `${today}T00:00:00`, limit: 500 }), [today, heatmap])

  const counts = useMemo(() => Object.fromEntries((zones.data ?? []).map((z) => [z.id, tracks.filter((t) => pointInPolygon(t.x, t.y, z.points)).length])), [zones.data, tracks])
  const eventsByZone = useMemo(() => {
    const m: Record<string, number> = {}
    for (const e of todayEvents.data?.items ?? []) m[String(e.zone_id)] = (m[String(e.zone_id)] ?? 0) + 1
    return m
  }, [todayEvents.data])
  // One revision cloud per area: open (or just-closed) unacknowledged alerts, clustered so repeats don't pile up.
  const clouds = useMemo(() => {
    const w0 = site.data?.plan_width ?? 1600
    const out: SafetyEvent[] = []
    for (const e of state.events) {
      if (!e.plan || e.acknowledged || (e.ended_at && now - Date.parse(e.ended_at) > 30_000)) continue
      if (out.some((c) => Math.hypot(c.plan![0] - e.plan![0], c.plan![1] - e.plan![1]) < w0 / 22)) continue
      out.push(e)
      if (out.length >= 8) break
    }
    return out
  }, [state.events, now, site.data])

  if (site.error || zones.error) return <p className="notice notice--err">{site.error ?? zones.error}</p>
  if (!site.data || !zones.data) return <div className="empty">جارٍ التحميل…</div>
  const w = site.data.plan_width

  return (
    <div className="split">
      <div>
        <SitePlan site={site.data} zones={zones.data} zoneCounts={counts} label="مخطط الموقع مع مواقع العاملين الحية ومناطق الخطر والتنبيهات">
          {heatmap && (todayEvents.data?.items ?? []).filter((e) => e.plan).map((e) => (
            <circle key={`h${e.id}`} className="heat-blob" cx={e.plan![0]} cy={e.plan![1]} r={w / 28} />
          ))}
          {clouds.map((e) => <path key={`c${e.id}`} className="revcloud" d={cloudPath(e.plan![0], e.plan![1], w / 30)} />)}
          {tracks.map((t) => (
            <g key={`${t.camera_id}-${t.id}`}>
              {t.status !== 'ok' && <circle className="worker-ring" cx={t.x} cy={t.y} r={w / 120} />}
              <circle className={`worker-dot worker-dot--${t.status}`} cx={t.x} cy={t.y} r={w / 140} />
            </g>
          ))}
        </SitePlan>
        <div className="legend" style={{ marginTop: 12 }}>
          <span><i className="lg-no" />منطقة محظورة فعّالة</span>
          <span><i className="lg-off" />منطقة محظورة متوقفة</span>
          <span><i className="lg-ppe" />منطقة معدات وقاية</span>
          <span><i className="lg-dot" />عامل (من الكاميرات المعايَرة)</span>
          <span><svg width="22" height="16" viewBox="0 0 44 32" aria-hidden="true"><path d={cloudPath(22, 16, 12, 9)} fill="none" stroke="#dc2e26" strokeWidth="2.5" /></svg>تنبيه بانتظار الاطلاع</span>
        </div>
      </div>

      <aside className="stack">
        <section className="panel">
          <div className="panel__head"><h2>الآن على الموقع</h2><span className="aside">{workersAr(tracks.length)}</span></div>
          <table className="schedule" style={{ border: 0 }}>
            <thead><tr><th>المنطقة</th><th className="num">الآن</th><th className="num">أحداث اليوم</th></tr></thead>
            <tbody>
              {zones.data.map((z) => (
                <tr key={z.id}>
                  <td>{z.name}{z.kind === 'no_entry' && !z.active && <small className="muted"> (متوقفة)</small>}</td>
                  <td className="num" style={{ color: counts[z.id] && z.kind === 'no_entry' && z.active ? '#b42318' : undefined, fontWeight: 600 }}>{counts[z.id] ?? 0}</td>
                  <td className="num">{eventsByZone[String(z.id)] ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="panel">
          <div className="panel__head"><h2>تنبيهات على المخطط</h2><span className="aside">{clouds.length}</span></div>
          <div className="panel__body">
            {clouds.length === 0 && <p className="muted">لا توجد تنبيهات مفتوحة بموقع على المخطط.</p>}
            {clouds.map((e) => (
              <div key={e.id} className="paper-alert">
                <span className="state-dot" style={{ background: e.severity === 'critical' ? '#dc2e26' : '#ff5b1f' }} />
                <span style={{ fontWeight: 600 }}>{eventTitle(e)}</span>
                <span className="muted">{e.detail.zone_name ?? ''}</span>
                <span className="muted ltr">{camCode(e.camera_id)}</span>
                <span className="muted" style={{ marginInlineStart: 'auto' }}>{ago(e.ts, now)}</span>
              </div>
            ))}
          </div>
        </section>

        <label className="check">
          <input type="checkbox" checked={heatmap} onChange={(e) => setHeatmap(e.target.checked)} />
          <span><b>خريطة حرارية لأحداث اليوم</b><small>تجمّع مواقع الأحداث المسجّلة اليوم على المخطط ({eventsAr(todayEvents.data?.items.filter((e) => e.plan).length ?? 0)} بموقع معروف).</small></span>
        </label>
        <p className="muted" style={{ fontSize: 13 }}>تظهر مواقع العاملين من الكاميرات المعايَرة فقط، ولا تُحفظ هويات: الرقم مؤقت يعطيه نظام التتبّع.</p>
      </aside>
    </div>
  )
}
