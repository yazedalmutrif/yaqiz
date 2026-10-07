import { useState } from 'react'
import { Toast } from '../components/Widgets'
import { api } from '../lib/api'
import { fmtNum, LEVEL_LABEL, todayRiyadh } from '../lib/format'
import { useApi, useNow, useToast } from '../lib/hooks'
import { useLive } from '../lib/live'

const KIND_AR: Record<string, string> = { zone_intrusion: 'دخول منطقة خطر', ppe_missing: 'نقص معدات الوقاية', man_down: 'سقوط عامل', sos: 'نداء استغاثة', midday_exposure: 'عمل وقت الحظر', machine_proximity: 'اقتراب من معدة' }

/** S-06: where is the risk concentrated, hour by hour? Built transparently from the event log. */
export function Risk() {
  const [day, setDay] = useState(todayRiyadh())
  const [shift, setShift] = useState<'day' | 'full'>('day')
  const grid = useApi(() => api.risk(day, shift), [day, shift])
  const { state, setHeat } = useLive()
  const { toast, show } = useToast()
  const now = useNow(60_000)
  const [manual, setManual] = useState({ t: '', rh: '' })
  const heat = state.heat
  const currentHour = Number(new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Riyadh', hour: '2-digit', hour12: false }).format(now))
  const isToday = day === todayRiyadh()

  const applyManual = async () => {
    const t = Number(manual.t)
    const rh = Number(manual.rh)
    if (!Number.isFinite(t) || !Number.isFinite(rh) || manual.t === '' || manual.rh === '') return show('أدخل الحرارة والرطوبة أرقامًا', 'err')
    try {
      setHeat(await api.setHeat(t, rh))
      show('اعتُمدت القراءة اليدوية')
    } catch (e) {
      show(e instanceof Error ? e.message : 'تعذّر الحفظ', 'err')
    }
  }

  return (
    <div className="stack">
      <div className="row-gap" style={{ alignItems: 'flex-end' }}>
        <label className="field"><span>اليوم</span><input className="input" type="date" value={day} max={todayRiyadh()} onChange={(e) => setDay(e.target.value)} /></label>
        <div className="field">
          <span>الفترة</span>
          <div className="seg" role="group">
            <button type="button" aria-pressed={shift === 'day'} onClick={() => setShift('day')}>الوردية النهارية 06:00–18:00</button>
            <button type="button" aria-pressed={shift === 'full'} onClick={() => setShift('full')}>24 ساعة</button>
          </div>
        </div>
        {grid.data?.top && (
          <p className="notice" style={{ marginInlineStart: 'auto' }}>الأعلى خطرًا: <b>{grid.data.top.name}</b> بمجموع <b className="num">{fmtNum(grid.data.top.total, 1)}</b> نقطة</p>
        )}
      </div>

      {grid.error && <p className="notice notice--err">{grid.error}</p>}
      {grid.data && (
        <div style={{ overflowX: 'auto' }}>
          <table className="riskgrid">
            <thead>
              <tr>
                <th style={{ minWidth: 150 }}>المنطقة</th>
                {grid.data.hours.map((h) => <th key={h} className="ltr" style={{ minWidth: 40 }}>{String(h).padStart(2, '0')}</th>)}
                <th style={{ minWidth: 64 }}>المجموع</th>
              </tr>
            </thead>
            <tbody>
              {grid.data.zones.map((r) => (
                <tr key={String(r.zone_id)}>
                  <th scope="row">{r.name}</th>
                  {r.scores.map((s, i) => (
                    <td key={i} className={`lv${r.levels[i]} ${s === 0 ? 'is-empty' : ''} ${isToday && grid.data!.hours[i] === currentHour ? 'now' : ''}`}
                      title={`${String(grid.data!.hours[i]).padStart(2, '0')}:00 مستوى ${LEVEL_LABEL[r.levels[i]]} (${fmtNum(s, 1)} نقطة)`}>
                      {s ? fmtNum(s, 0) : ''}
                    </td>
                  ))}
                  <td className="total">{fmtNum(r.total, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="legend">
        {[1, 2, 3, 4].map((l) => <span key={l}><i style={{ background: `var(--lv${l})`, borderColor: 'var(--ink)' }} />{LEVEL_LABEL[l]}</span>)}
        <span className="muted">الخلية المؤطرة هي الساعة الحالية.</span>
      </div>

      <div className="cols-2">
        <section className="panel">
          <div className="panel__head"><h2>كيف يُحسب المؤشر؟</h2></div>
          <div className="panel__body stack" style={{ fontSize: 14 }}>
            <p>مجموع أوزان الأحداث في كل منطقة وكل ساعة، ويضاف {grid.data?.critical_bonus ?? 2} للحدث الحرج. في المناطق المكشوفة يرتفع الوزن 25% عن كل درجة من فئة الحرارة.</p>
            <table className="schedule">
              <thead><tr><th>الحدث</th><th className="num">الوزن</th></tr></thead>
              <tbody>{Object.entries(grid.data?.weights ?? {}).map(([k, v]) => <tr key={k}><td>{KIND_AR[k] ?? k}</td><td className="num">{v}</td></tr>)}</tbody>
            </table>
            <p className="muted">المستويات: أقل من 3 منخفض، 3–7.9 متوسط، 8–14.9 مرتفع، 15 فأكثر حرج. الأوزان نقطة بداية شفافة تُضبط ببيانات الموقع.</p>
          </div>
        </section>

        <section className="panel">
          <div className="panel__head"><h2>الحرارة وحظر الظهيرة</h2><span className="aside">{heat?.source === 'manual' ? 'إدخال يدوي' : heat?.source === 'open-meteo' ? 'Open-Meteo' : 'غير متاح'}</span></div>
          <div className="panel__body stack">
            <div className="kpis" style={{ gridTemplateColumns: 'repeat(3, minmax(0,1fr))', marginBottom: 0 }}>
              <div className="kpi"><b>{heat?.temperature_c != null ? `${fmtNum(heat.temperature_c, 1)}°` : '–'}</b><span>الحرارة</span></div>
              <div className="kpi"><b>{heat?.humidity != null ? `${fmtNum(heat.humidity, 0)}%` : '–'}</b><span>الرطوبة</span></div>
              <div className="kpi"><b>{heat?.heat_index_c != null ? `${fmtNum(heat.heat_index_c, 0)}°` : '–'}</b><span>مؤشر الحرارة ({heat?.category_ar ?? '–'})</span></div>
            </div>
            <p style={{ fontSize: 14 }}>
              حظر العمل تحت أشعة الشمس: من {heat?.midday_ban.start_hour ?? 12}:00 إلى {heat?.midday_ban.end_hour ?? 15}:00، من {heat?.midday_ban.from ?? '06-15'} إلى {heat?.midday_ban.to ?? '09-15'} (شهر-يوم).{' '}
              <b style={{ color: heat?.midday_ban_active ? 'var(--orange-ink)' : undefined }}>{heat?.midday_ban_active ? 'ساري الآن.' : 'غير ساري الآن.'}</b>
            </p>
            <div className="row-gap" style={{ alignItems: 'flex-end' }}>
              <label className="field" style={{ width: 110 }}><span>الحرارة °م</span><input className="input" inputMode="decimal" value={manual.t} onChange={(e) => setManual({ ...manual, t: e.target.value })} /></label>
              <label className="field" style={{ width: 110 }}><span>الرطوبة %</span><input className="input" inputMode="decimal" value={manual.rh} onChange={(e) => setManual({ ...manual, rh: e.target.value })} /></label>
              <button type="button" className="btn" onClick={applyManual}>اعتماد قراءة يدوية</button>
              {heat?.source === 'manual' && <button type="button" className="btn btn--sm" onClick={async () => setHeat(await api.clearHeat())}>العودة للقراءة الآلية</button>}
            </div>
            <p className="muted" style={{ fontSize: 12 }}>مؤشر الحرارة بمعادلة هيئة الأرصاد الأمريكية (NWS). القراءة اليدوية مفيدة حين لا يتوفر الإنترنت في الموقع.</p>
          </div>
        </section>
      </div>
      <Toast toast={toast} />
    </div>
  )
}
