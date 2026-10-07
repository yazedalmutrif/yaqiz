import { useState } from 'react'
import { IconPrint } from '../components/Icons'
import { api } from '../lib/api'
import { LEVEL_LABEL, camCode, dayToDate, eventTitle, fmtDate, fmtNum, fmtTime, minutesAr, todayRiyadh } from '../lib/format'
import { useApi } from '../lib/hooks'

/** S-07: the daily HSE report, printed from the browser (correct Arabic shaping; "Save as PDF"). */
export function Report() {
  const [day, setDay] = useState(todayRiyadh())
  const site = useApi(api.site)
  const rep = useApi(() => api.report(day), [day])
  const r = rep.data
  const maxHour = Math.max(1, ...(r?.by_hour ?? [0]))
  const busiest = r ? r.by_hour.indexOf(Math.max(...r.by_hour)) : -1

  return (
    <div className="stack">
      <div className="row-gap no-print" style={{ alignItems: 'flex-end' }}>
        <label className="field"><span>يوم التقرير</span><input className="input" type="date" value={day} max={todayRiyadh()} onChange={(e) => setDay(e.target.value)} /></label>
        <button type="button" className="btn btn--ink" onClick={() => window.print()} disabled={!r}><IconPrint />طباعة أو حفظ PDF</button>
        <span className="muted" style={{ fontSize: 13 }}>في نافذة الطباعة اختر «حفظ بصيغة PDF».</span>
      </div>
      {rep.error && <p className="notice notice--err">{rep.error}</p>}
      {!r && !rep.error && <div className="empty">جارٍ إعداد التقرير…</div>}
      {r && (
        <article className="report">
          <header className="report__head">
            <div>
              <p className="muted" style={{ fontSize: 14 }}>تقرير السلامة اليومي</p>
              <h1>{site.data?.name ?? 'الموقع'}</h1>
              <p style={{ marginTop: 4 }}>{fmtDate(dayToDate(r.date))}</p>
            </div>
            <div className="titleblock" aria-label="بيانات التقرير">
              <span>المنظومة</span><span>يقظ</span>
              <span>التاريخ</span><span className="ltr">{r.date}</span>
              <span>أُعدّ في</span><span className="ltr">{fmtTime(r.generated_at)}</span>
              <span>الكاميرات</span><span>{r.coverage.length}</span>
            </div>
          </header>

          <section>
            <h2>ملخص اليوم</h2>
            <div className="kpis" style={{ gridTemplateColumns: 'repeat(5, minmax(0,1fr))' }}>
              <div className="kpi"><b>{r.totals.events}</b><span>إجمالي الأحداث</span></div>
              <div className="kpi"><b style={{ color: r.totals.critical ? 'var(--red-ink)' : undefined }}>{r.totals.critical}</b><span>أحداث حرجة</span></div>
              <div className="kpi"><b>{r.totals.events ? fmtNum((100 * r.totals.acknowledged) / r.totals.events, 0) + '%' : '–'}</b><span>نسبة ما اطُّلع عليه</span></div>
              <div className="kpi"><b>{r.compliance.helmet_pct != null ? `${fmtNum(r.compliance.helmet_pct, 0)}%` : '–'}</b><span>الالتزام بالخوذة</span></div>
              <div className="kpi"><b>{r.compliance.vest_pct != null ? `${fmtNum(r.compliance.vest_pct, 0)}%` : '–'}</b><span>الالتزام بالسترة</span></div>
            </div>
            <p className="muted" style={{ fontSize: 12.5 }}>نسب الالتزام محسوبة من {fmtNum(r.compliance.observations)} مشاهدة رصد فيها النموذج حالة الخوذة بوضوح. الأحداث تُسجَّل آليًا من الكاميرات.</p>
          </section>

          <section className="cols-2">
            <div>
              <h2>الأحداث حسب النوع</h2>
              <table className="schedule">
                <thead><tr><th>النوع</th><th className="num">العدد</th></tr></thead>
                <tbody>
                  {r.by_kind.map((k) => <tr key={k.kind}><td>{k.label}</td><td className="num">{k.count}</td></tr>)}
                  {r.by_kind.length === 0 && <tr><td colSpan={2} className="muted">لم تُسجَّل أحداث.</td></tr>}
                </tbody>
              </table>
            </div>
            <div>
              <h2>الأحداث حسب المنطقة</h2>
              <table className="schedule">
                <thead><tr><th>المنطقة</th><th className="num">العدد</th></tr></thead>
                <tbody>
                  {r.by_zone.map((z) => <tr key={String(z.zone_id)}><td>{z.name}</td><td className="num">{z.count}</td></tr>)}
                  {r.by_zone.length === 0 && <tr><td colSpan={2} className="muted">لا شيء.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2>توزيع الأحداث على ساعات اليوم</h2>
            <div className="bars" role="img" aria-label={busiest >= 0 && r.totals.events ? `أكثر ساعة أحداثًا ${busiest}:00` : 'لا أحداث'}>
              {r.by_hour.map((n, h) => <div key={h} className={h === busiest && n ? 'is-hot' : ''} style={{ height: `${(n / maxHour) * 100}%` }} title={`${String(h).padStart(2, '0')}:00 = ${n}`} />)}
            </div>
            <div className="bars-axis">{r.by_hour.map((_, h) => <span key={h}>{h % 3 === 0 ? String(h).padStart(2, '0') : ''}</span>)}</div>
          </section>

          <section>
            <h2>مؤشر الخطر للمناطق</h2>
            <table className="schedule">
              <thead><tr><th>المنطقة</th><th className="num">المجموع</th><th>أعلى مستوى خلال الوردية</th></tr></thead>
              <tbody>
                {r.risk.zones.map((z) => <tr key={String(z.zone_id)}><td>{z.name}</td><td className="num">{fmtNum(z.total, 1)}</td><td>{LEVEL_LABEL[Math.max(...z.levels)]}</td></tr>)}
              </tbody>
            </table>
          </section>

          <section>
            <h2>الأحداث الحرجة ({r.critical_events.length})</h2>
            {r.critical_events.length === 0 ? <p className="muted">لم تُسجَّل أحداث حرجة.</p> : (
              <div className="critical-list">
                {r.critical_events.slice(0, 12).map((e) => (
                  <figure key={e.id}>
                    {e.snapshot_url && <img src={e.snapshot_url} alt={`لقطة: ${eventTitle(e)}`} />}
                    <figcaption><b>{eventTitle(e)}</b><br />{e.detail.zone_name ?? 'خارج المناطق'}<br /><span className="ltr">{fmtTime(e.ts)} {camCode(e.camera_id)}</span>{e.acknowledged ? ' (تم الاطلاع)' : ''}</figcaption>
                  </figure>
                ))}
              </div>
            )}
          </section>

          <section>
            <h2>تغطية الكاميرات</h2>
            <p style={{ fontSize: 14 }}>{r.coverage.length ? r.coverage.map((c) => `${c.name}: ${minutesAr(c.minutes)}`).join('، ') : 'لا بيانات تشغيل لهذا اليوم.'}</p>
            {r.heat?.heat_index_c != null && <p style={{ fontSize: 14 }}>مؤشر الحرارة عند إعداد التقرير: {fmtNum(r.heat.heat_index_c, 0)}° ({r.heat.category_ar}).</p>}
          </section>
          <p className="muted" style={{ fontSize: 11.5, marginTop: 24 }}>الوجوه في اللقطات مموّهة آليًا. يعمل يقظ على كاميرات الموقع ومعالج داخل الموقع، ولا يخرج من الموقع إلا الحدث.</p>
        </article>
      )}
    </div>
  )
}
