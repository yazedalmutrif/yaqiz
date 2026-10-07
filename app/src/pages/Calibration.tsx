import { useEffect, useMemo, useState, type MouseEvent } from 'react'
import { IconTrash } from '../components/Icons'
import { SitePlan } from '../components/SitePlan'
import { Toast } from '../components/Widgets'
import { api, frameUrl } from '../lib/api'
import { camCode, fmtCoord, fmtNum } from '../lib/format'
import { useApi, useToast } from '../lib/hooks'
import type { CalibPair, Pt } from '../lib/types'

/** S-04: tie a camera to the plan with ≥4 point pairs (the same ground point on the plan and in the frame). */
export function Calibration() {
  const site = useApi(api.site)
  const zones = useApi(api.zones)
  const cams = useApi(api.cameras)
  const { toast, show } = useToast()
  const [camId, setCamId] = useState<number | null>(null)
  const [pairs, setPairs] = useState<CalibPair[]>([])
  const [pending, setPending] = useState<{ plan?: Pt; image?: Pt }>({})
  const [frame, setFrame] = useState<{ url: string; w: number; h: number } | null>(null)
  const [frameError, setFrameError] = useState<string | null>(null)
  const [preview, setPreview] = useState<Record<string, [number, number][]>>({})
  const [errorPx, setErrorPx] = useState<number | null>(null)

  const cam = useMemo(() => cams.data?.find((c) => c.id === camId) ?? null, [cams.data, camId])

  useEffect(() => {
    if (camId === null && cams.data?.length) setCamId(cams.data[0].id)
  }, [cams.data, camId])

  useEffect(() => {
    if (!cam) return
    setPairs(cam.calib_pairs ?? [])
    setPending({})
    setErrorPx(cam.calib_error_px)
    loadFrame(cam.id)
    fetch(`/api/cameras/${cam.id}/calibration/preview`).then((r) => r.json()).then((j) => setPreview(j.zones_in_view ?? {})).catch(() => setPreview({}))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cam?.id])

  const loadFrame = (id: number) => {
    setFrameError(null)
    const url = frameUrl(id)
    const img = new Image()
    img.onload = () => setFrame({ url, w: img.naturalWidth, h: img.naturalHeight })
    img.onerror = () => { setFrame(null); setFrameError('لا تصل صورة من هذه الكاميرا. شغّلها من «الإعدادات» ثم أعد المحاولة.') }
    img.src = url
  }

  const add = (next: { plan?: Pt; image?: Pt }) => {
    const p = { ...pending, ...next }
    if (p.plan && p.image) {
      setPairs((list) => [...list, { plan: p.plan!, image: p.image! }])
      setPending({})
    } else setPending(p)
  }

  const onFrameClick = (e: MouseEvent<SVGSVGElement>) => {
    if (!frame) return
    const r = e.currentTarget.getBoundingClientRect()
    add({ image: [Math.round(((e.clientX - r.left) / r.width) * frame.w), Math.round(((e.clientY - r.top) / r.height) * frame.h)] })
  }

  const compute = async () => {
    if (!cam) return
    try {
      const res = await api.calibrate(cam.id, pairs)
      setPreview(res.zones_in_view)
      setErrorPx(res.error_px)
      await cams.reload()
      show(`حُفظت المعايرة. متوسط خطأ الإسقاط ${fmtNum(res.error_px, 2)} بكسل`)
    } catch (e) {
      show(e instanceof Error ? e.message : 'تعذّرت المعايرة', 'err')
    }
  }

  const clear = async () => {
    if (!cam || !window.confirm('إزالة معايرة هذه الكاميرا؟ ستتوقف عن تطبيق مناطق المخطط.')) return
    await api.clearCalibration(cam.id)
    setPairs([])
    setPreview({})
    setErrorPx(null)
    await cams.reload()
    show('أزيلت المعايرة')
  }

  if (site.error || zones.error || cams.error) return <p className="notice notice--err">{site.error ?? zones.error ?? cams.error}</p>
  if (!site.data || !zones.data || !cams.data) return <div className="empty">جارٍ التحميل…</div>
  const pr = site.data.plan_width / 110
  const fr = frame ? frame.w / 70 : 10

  return (
    <div className="stack">
      <div className="row-gap">
        <label className="field" style={{ minWidth: 280 }}>
          <span>الكاميرا</span>
          <select className="input" value={camId ?? ''} onChange={(e) => setCamId(Number(e.target.value))}>
            {cams.data.map((c) => <option key={c.id} value={c.id}>{camCode(c.id)} {c.name}{c.calibrated ? ' (معايَرة)' : ''}</option>)}
          </select>
        </label>
        <ol className="steps-inline" style={{ flex: 1, minWidth: 320 }}>
          <li>انقر نقطة أرضية واضحة على المخطط (زاوية عمود، حافة بلاطة).</li>
          <li>انقر النقطة نفسها في صورة الكاميرا. كرّر لأربع نقاط على الأقل، موزّعة على أرض المشهد.</li>
          <li>اضغط «احسب المعايرة»، فتظهر المناطق المسقطة على الصورة للتحقق.</li>
        </ol>
      </div>

      <div className="calib">
        <section>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 17, marginBottom: 8 }}>المخطط</h2>
          <SitePlan site={site.data} zones={zones.data} picking onPick={(p) => add({ plan: p })} label="انقر لتحديد نقطة على المخطط">
            {pairs.map((p, i) => (
              <g key={i} className="pair-mark" transform={`translate(${p.plan[0]} ${p.plan[1]})`}>
                <circle r={pr} /><text fontSize={pr * 1.1}>{i + 1}</text>
              </g>
            ))}
            {pending.plan && <g className="pair-mark pair-mark--pending" transform={`translate(${pending.plan[0]} ${pending.plan[1]})`}><circle r={pr} /><text fontSize={pr * 1.1}>{pairs.length + 1}</text></g>}
          </SitePlan>
        </section>
        <section>
          <div className="row-gap" style={{ marginBottom: 8 }}>
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 17 }}>صورة الكاميرا</h2>
            <button type="button" className="btn btn--sm" style={{ marginInlineStart: 'auto' }} onClick={() => cam && loadFrame(cam.id)}>تحديث الصورة</button>
          </div>
          {frameError && <p className="notice notice--err">{frameError}</p>}
          {frame && (
            <div className="calib__frame">
              <img src={frame.url} alt={`صورة حالية من ${cam?.name ?? 'الكاميرا'} (الوجوه مموّهة)`} draggable={false} />
              <svg viewBox={`0 0 ${frame.w} ${frame.h}`} onClick={onFrameClick} role="img" aria-label="انقر لتحديد النقطة المقابلة في الصورة">
                {Object.entries(preview).map(([zid, pts]) => <polygon key={zid} className="proj-zone" points={pts.map((p) => p.join(',')).join(' ')} />)}
                {pairs.map((p, i) => (
                  <g key={i} className="pair-mark" transform={`translate(${p.image[0]} ${p.image[1]})`}><circle r={fr} /><text fontSize={fr * 1.1}>{i + 1}</text></g>
                ))}
                {pending.image && <g className="pair-mark pair-mark--pending" transform={`translate(${pending.image[0]} ${pending.image[1]})`}><circle r={fr} /><text fontSize={fr * 1.1}>{pairs.length + 1}</text></g>}
              </svg>
            </div>
          )}
        </section>
      </div>

      <section className="panel">
        <div className="panel__head">
          <h2>أزواج النقاط</h2>
          <span className="aside">{pairs.length} من 4 على الأقل{errorPx !== null && `، خطأ الإسقاط ${fmtNum(errorPx, 2)} بكسل`}</span>
        </div>
        <div className="panel__body stack">
          {pairs.length === 4 && cam?.calibrated && (
            <p className="notice">بأربع نقاط فقط تمرّ المعايرة بها تمامًا، فيظهر الخطأ صفرًا دائمًا ولا يدل على الدقة. أضف نقطة خامسة أو سادسة موزّعة على أرض المشهد ليُقاس الخطأ فعلًا.</p>
          )}
          {pairs.length > 0 && (
            <table className="schedule">
              <thead><tr><th>#</th><th>على المخطط <bdi dir="ltr">(x, y)</bdi></th><th>في الصورة <bdi dir="ltr">(u, v)</bdi></th><th /></tr></thead>
              <tbody>
                {pairs.map((p, i) => (
                  <tr key={i}>
                    <td className="num">{i + 1}</td>
                    <td className="ltr">{fmtCoord(p.plan[0], p.plan[1])}</td>
                    <td className="ltr">{fmtCoord(p.image[0], p.image[1])}</td>
                    <td><button type="button" className="btn btn--sm btn--icon" aria-label={`حذف الزوج ${i + 1}`} onClick={() => setPairs((l) => l.filter((_, j) => j !== i))}><IconTrash /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="row-gap">
            <button type="button" className="btn btn--ink" disabled={pairs.length < 4} onClick={compute}>احسب المعايرة</button>
            <button type="button" className="btn" disabled={!pairs.length && !pending.plan && !pending.image} onClick={() => { setPairs([]); setPending({}) }}>مسح النقاط</button>
            {cam?.calibrated && <button type="button" className="btn btn--danger" onClick={clear}>إزالة المعايرة</button>}
            <span className="muted" style={{ fontSize: 13 }}>المعايرة صالحة لأرض الموقع قرب النقاط المختارة؛ لذلك وزّعها على كامل المنطقة التي تراها الكاميرا.</span>
          </div>
        </div>
      </section>
      <Toast toast={toast} />
    </div>
  )
}
