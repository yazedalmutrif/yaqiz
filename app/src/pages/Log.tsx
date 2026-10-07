import { useState } from 'react'
import { IconDownload } from '../components/Icons'
import { Lightbox } from '../components/Widgets'
import { api } from '../lib/api'
import { camCode, eventTitle, eventsAr, fmtDuration, fmtTime, KIND_LABEL, SEVERITY_LABEL, todayRiyadh } from '../lib/format'
import { useApi } from '../lib/hooks'
import { useLive } from '../lib/live'
import type { EventKind, SafetyEvent } from '../lib/types'

const PAGE = 50
const nextDay = (d: string) => {
  const t = new Date(`${d}T12:00:00Z`)
  t.setUTCDate(t.getUTCDate() + 1)
  return t.toISOString().slice(0, 10)
}

/** S-05: what happened, when and where. Filterable, acknowledgeable, exportable. */
export function Log() {
  const { upsert } = useLive()
  const zones = useApi(api.zones)
  const cams = useApi(api.cameras)
  const [day, setDay] = useState(todayRiyadh())
  const [kind, setKind] = useState<EventKind | ''>('')
  const [zone, setZone] = useState('')
  const [cam, setCam] = useState('')
  const [unacked, setUnacked] = useState(false)
  const [page, setPage] = useState(0)
  const [zoom, setZoom] = useState<string | null>(null)
  const query = { since: `${day}T00:00:00`, until: `${nextDay(day)}T00:00:00`, kind, zone_id: zone, camera_id: cam, unacked: unacked || undefined }
  const data = useApi(() => api.events({ ...query, limit: PAGE, offset: page * PAGE }), [day, kind, zone, cam, unacked, page])

  const zoneName = (e: SafetyEvent) => e.detail.zone_name ?? zones.data?.find((z) => z.id === e.zone_id)?.name ?? 'خارج المناطق'
  const camName = (id: number | null) => cams.data?.find((c) => c.id === id)?.name ?? camCode(id)

  const ack = async (e: SafetyEvent) => {
    const updated = await api.ack(e.id)
    upsert(updated)
    data.setData((d) => d && { ...d, items: d.items.map((x) => (x.id === e.id ? updated : x)) })
  }

  const exportCsv = async () => {
    const all = await api.events({ ...query, limit: 500 })
    const head = ['الوقت', 'الحدث', 'الخطورة', 'المنطقة', 'الكاميرا', 'المدة (ث)', 'تم الاطلاع', 'رقم الحدث']
    const rows = all.items.map((e) => [fmtTime(e.ts), eventTitle(e), SEVERITY_LABEL[e.severity], zoneName(e), camName(e.camera_id), e.duration_s, e.acknowledged ? 'نعم' : 'لا', e.id])
    const csv = [head, ...rows].map((r) => r.map((v) => `"${String(v).replaceAll('"', '""')}"`).join(',')).join('\r\n')
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }))
    const a = Object.assign(document.createElement('a'), { href: url, download: `yaqiz-events-${day}.csv` })
    a.click()
    URL.revokeObjectURL(url)
  }

  const total = data.data?.total ?? 0
  return (
    <div className="stack">
      <div className="row-gap" style={{ alignItems: 'flex-end' }}>
        <label className="field"><span>اليوم</span><input className="input" type="date" value={day} max={todayRiyadh()} onChange={(e) => { setDay(e.target.value); setPage(0) }} /></label>
        <label className="field"><span>نوع الحدث</span>
          <select className="input" value={kind} onChange={(e) => { setKind(e.target.value as EventKind | ''); setPage(0) }}>
            <option value="">الكل</option>
            {(Object.keys(KIND_LABEL) as EventKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
          </select>
        </label>
        <label className="field"><span>المنطقة</span>
          <select className="input" value={zone} onChange={(e) => { setZone(e.target.value); setPage(0) }}>
            <option value="">الكل</option>
            {zones.data?.map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
          </select>
        </label>
        <label className="field"><span>الكاميرا</span>
          <select className="input" value={cam} onChange={(e) => { setCam(e.target.value); setPage(0) }}>
            <option value="">الكل</option>
            {cams.data?.map((c) => <option key={c.id} value={c.id}>{camCode(c.id)} {c.name}</option>)}
          </select>
        </label>
        <label className="check"><input type="checkbox" checked={unacked} onChange={(e) => { setUnacked(e.target.checked); setPage(0) }} /><span><b>بانتظار الاطلاع فقط</b></span></label>
        <button type="button" className="btn" style={{ marginInlineStart: 'auto' }} onClick={exportCsv} disabled={!total}><IconDownload />تصدير CSV</button>
      </div>

      {data.error && <p className="notice notice--err">{data.error}</p>}
      <div className="table-scroll">
      <table className="schedule">
        <thead><tr><th>الوقت</th><th>الحدث</th><th>الخطورة</th><th>المنطقة</th><th>الكاميرا</th><th>المدة</th><th>الحالة</th><th>اللقطة</th></tr></thead>
        <tbody>
          {(data.data?.items ?? []).map((e) => (
            <tr key={e.id}>
              <td className="ltr num nowrap">{fmtTime(e.ts)}</td>
              <td className="nowrap" style={{ fontWeight: 600 }}>{eventTitle(e)}</td>
              <td className="nowrap"><span style={{ color: e.severity === 'critical' ? 'var(--red-ink)' : 'var(--orange-ink)', fontWeight: 600 }}>{SEVERITY_LABEL[e.severity]}</span></td>
              <td style={{ minWidth: '10em' }}>{zoneName(e)}</td>
              <td className="ltr nowrap" title={camName(e.camera_id)}>{camCode(e.camera_id)}</td>
              <td className="nowrap">{e.ended_at ? fmtDuration(e.duration_s) : <span className="muted">مستمر</span>}</td>
              <td className="nowrap">{e.acknowledged ? <span className="muted">تم الاطلاع</span> : <button type="button" className="btn btn--sm" onClick={() => void ack(e)}>تم الاطلاع</button>}</td>
              <td>{e.snapshot_url && <button type="button" className="thumb-btn" aria-label={`تكبير لقطة: ${eventTitle(e)}`} onClick={() => setZoom(e.snapshot_url)}><img src={e.snapshot_url} alt="" loading="lazy" width={84} height={52} /></button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      {!data.loading && total === 0 && <div className="empty">لا أحداث بهذه المعايير.</div>}
      {total > PAGE && (
        <div className="row-gap">
          <button type="button" className="btn btn--sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>السابق</button>
          <span className="muted">صفحة {page + 1} من {Math.ceil(total / PAGE)} ({eventsAr(total)})</span>
          <button type="button" className="btn btn--sm" disabled={(page + 1) * PAGE >= total} onClick={() => setPage((p) => p + 1)}>التالي</button>
        </div>
      )}
      <Lightbox url={zoom} onClose={() => setZoom(null)} />
    </div>
  )
}
