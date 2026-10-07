import { useMemo, useState } from 'react'
import { AlertCard, CameraTile, Kpi, Lightbox } from '../components/Widgets'
import { api } from '../lib/api'
import { todayRiyadh } from '../lib/format'
import { useApi, useNow } from '../lib/hooks'
import { useLive } from '../lib/live'
import type { SafetyEvent } from '../lib/types'

const dayOf = (iso: string) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Riyadh' }).format(new Date(iso))

/** S-01: is the site safe right now? Live cameras, the numbers that matter, and alerts to act on. */
export function Monitor() {
  const { state, upsert } = useLive()
  const cams = useApi(api.cameras)
  const now = useNow(1000)
  const [focus, setFocus] = useState<number | null>(null)
  const [zoom, setZoom] = useState<string | null>(null)
  const [show, setShow] = useState<'open' | 'all'>('open')

  const kpi = useMemo(() => {
    const list = Object.values(state.stats)
    const sum = (k: 'people' | 'in_zone' | 'helmet_yes' | 'helmet_no') => list.reduce((s, x) => s + (x[k] ?? 0), 0)
    const yes = sum('helmet_yes')
    const no = sum('helmet_no')
    const today = todayRiyadh()
    return {
      people: list.length ? sum('people') : null,
      inZone: list.length ? sum('in_zone') : null,
      helmet: yes + no ? (100 * yes) / (yes + no) : null,
      pending: state.events.filter((e) => !e.acknowledged).length,
      today: state.events.filter((e) => dayOf(e.ts) === today).length,
      online: Object.values(state.cameraStatus).filter((c) => c.state === 'running').length,
    }
  }, [state.stats, state.events, state.cameraStatus])

  const ack = async (e: SafetyEvent) => {
    try {
      upsert(await api.ack(e.id))
    } catch {
      /* the card stays; next update will retry */
    }
  }

  const cameras = (cams.data ?? []).slice().sort((a, b) => (a.id === focus ? -1 : b.id === focus ? 1 : a.id - b.id))
  const events = show === 'open' ? state.events.filter((e) => !e.acknowledged) : state.events

  return (
    <>
      <section className="kpis" aria-label="مؤشرات اللحظة">
        <Kpi value={kpi.people} label="عامل في مجال الكاميرات الآن" />
        <Kpi value={kpi.inZone} label="داخل مناطق الخطر الآن" tone={kpi.inZone ? 'alert' : undefined} />
        <Kpi value={kpi.helmet} label="الالتزام بالخوذة الآن" suffix="%" />
        <Kpi value={kpi.pending} label="تنبيهات بانتظار الاطلاع" tone={kpi.pending ? 'warn' : undefined} />
        <Kpi value={kpi.today} label="أحداث اليوم" />
        <Kpi value={kpi.online} label={`كاميرات تعمل من ${cams.data?.length ?? 0}`} />
      </section>

      <div className="monitor">
        <section aria-label="الكاميرات">
          {cams.error && <p className="notice notice--err">{cams.error}</p>}
          <div className="tiles">
            {cameras.map((c) => (
              <CameraTile key={c.id} cam={c} status={state.cameraStatus[c.id] ?? c.status} focus={c.id === focus}
                onFocus={() => setFocus((f) => (f === c.id ? null : c.id))} />
            ))}
          </div>
          {cams.data && cams.data.length === 0 && <div className="empty">لا توجد كاميرات. أضف كاميرا من «الإعدادات».</div>}
        </section>

        <aside className="panel" aria-label="التنبيهات">
          <div className="panel__head">
            <h2>التنبيهات</h2>
            <div className="seg aside" role="group" aria-label="عرض التنبيهات">
              <button type="button" aria-pressed={show === 'open'} onClick={() => setShow('open')}>بانتظار الاطلاع</button>
              <button type="button" aria-pressed={show === 'all'} onClick={() => setShow('all')}>الكل</button>
            </div>
          </div>
          <div className="panel__body">
            <div className="feed-list">
              {events.slice(0, 60).map((e) => <AlertCard key={e.id} e={e} now={now} onAck={ack} onZoom={setZoom} />)}
              {events.length === 0 && <div className="empty">{show === 'open' ? 'لا توجد تنبيهات بانتظار الاطلاع.' : 'لم تُسجَّل أحداث بعد.'}</div>}
            </div>
          </div>
        </aside>
      </div>
      <Lightbox url={zoom} onClose={() => setZoom(null)} />
    </>
  )
}
