import { useEffect, useRef, useState, type PointerEvent as RPointerEvent } from 'react'
import { IconPlus, IconTrash, IconUpload } from '../components/Icons'
import { SitePlan } from '../components/SitePlan'
import { Toast } from '../components/Widgets'
import { api } from '../lib/api'
import { useApi, useToast } from '../lib/hooks'
import type { Pt, Zone, ZoneInput } from '../lib/types'

const BLANK: ZoneInput = { name: 'منطقة جديدة', kind: 'no_entry', points: [], active: true, outdoor: true, require_helmet: false, require_vest: false, require_harness: false, interlock: false }

/** S-03: draw zones once on the site plan; every calibrated camera picks them up. */
export function Zones() {
  const site = useApi(api.site)
  const zones = useApi(api.zones)
  const health = useApi(api.health)
  const { toast, show } = useToast()
  const [selected, setSelected] = useState<number | null>(null)
  const [drawing, setDrawing] = useState(false)
  const [draft, setDraft] = useState<Pt[]>([])
  const [form, setForm] = useState<ZoneInput | null>(null)
  const [busy, setBusy] = useState(false)
  const drag = useRef<number | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const canHarness = !!health.data?.capabilities?.includes('harness')

  const select = (z: Zone | null) => {
    setDrawing(false)
    setDraft([])
    setSelected(z?.id ?? null)
    setForm(z ? { ...z } : null)
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!drawing) return
      if (e.key === 'Escape') { setDrawing(false); setDraft([]); setForm(null) }
      if (e.key === 'Enter' && draft.length >= 3) finishDraft()
      if (e.key === 'Backspace') setDraft((d) => d.slice(0, -1))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const startDraft = () => { setSelected(null); setForm(null); setDraft([]); setDrawing(true) }
  const finishDraft = () => { setDrawing(false); setForm({ ...BLANK, points: draft }) }

  const save = async () => {
    if (!form) return
    const pts = selected ? form.points : draft
    if (pts.length < 3) return show('ارسم ثلاث نقاط على الأقل', 'err')
    setBusy(true)
    try {
      const body = { ...form, points: pts }
      const z = selected ? await api.updateZone(selected, body) : await api.createZone(body)
      await zones.reload()
      setDraft([])
      select(z)
      show('حُفظت المنطقة، وتطبّقها الكاميرات فورًا')
    } catch (e) {
      show(e instanceof Error ? e.message : 'تعذّر الحفظ', 'err')
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!selected || !form || !window.confirm(`حذف «${form.name}»؟ لن تُحذف الأحداث المسجّلة.`)) return
    try {
      await api.deleteZone(selected)
      await zones.reload()
      select(null)
      show('حُذفت المنطقة')
    } catch (e) {
      show(e instanceof Error ? e.message : 'تعذّر الحذف', 'err')
    }
  }

  const upload = async (file: File | undefined) => {
    if (!file) return
    try {
      const s = await api.uploadPlan(file)
      await site.reload()
      show(s.warning ?? 'رُفع المخطط الجديد', s.warning ? 'err' : 'ok')
    } catch (e) {
      show(e instanceof Error ? e.message : 'تعذّر رفع المخطط', 'err')
    }
  }

  // vertex dragging (edit mode)
  const toPlan = (e: RPointerEvent<SVGCircleElement>): Pt => {
    const svg = e.currentTarget.ownerSVGElement!
    const r = svg.getBoundingClientRect()
    const vb = svg.viewBox.baseVal
    return [Math.round(((e.clientX - r.left) / r.width) * vb.width), Math.round(((e.clientY - r.top) / r.height) * vb.height)]
  }

  if (site.error || zones.error) return <p className="notice notice--err">{site.error ?? zones.error}</p>
  if (!site.data || !zones.data) return <div className="empty">جارٍ التحميل…</div>
  const r = site.data.plan_width / 150
  const editing = selected !== null && form

  return (
    <div className="split">
      <div>
        <div className="row-gap" style={{ marginBottom: 12 }}>
          <button type="button" className="btn btn--ink" onClick={startDraft} disabled={drawing}><IconPlus />منطقة جديدة</button>
          {drawing && (
            <>
              <button type="button" className="btn btn--hi" onClick={finishDraft} disabled={draft.length < 3}>إنهاء الرسم ({draft.length} نقاط)</button>
              <button type="button" className="btn" onClick={() => setDraft((d) => d.slice(0, -1))} disabled={!draft.length}>تراجع</button>
              <button type="button" className="btn" onClick={() => { setDrawing(false); setDraft([]) }}>إلغاء</button>
              <span className="muted">انقر على المخطط لإضافة نقاط المنطقة. Enter للإنهاء، Esc للإلغاء.</span>
            </>
          )}
          <span style={{ marginInlineStart: 'auto' }} />
          <input ref={fileRef} type="file" accept="image/png,image/jpeg" hidden onChange={(e) => void upload(e.target.files?.[0])} />
          <button type="button" className="btn" onClick={() => fileRef.current?.click()}><IconUpload />رفع مخطط الموقع</button>
        </div>

        <SitePlan site={site.data} zones={zones.data} selectedZoneId={selected} picking={drawing}
          onPick={(p) => setDraft((d) => [...d, p])} onZoneClick={(z) => select(z)}>
          {drawing && draft.length > 0 && (
            <>
              <polygon className="draft" points={draft.map((p) => p.join(',')).join(' ')} />
              {draft.map((p, i) => <circle key={i} className="vertex" cx={p[0]} cy={p[1]} r={r} />)}
            </>
          )}
          {editing && form.points.map((p, i) => (
            <circle key={i} className="vertex" cx={p[0]} cy={p[1]} r={r}
              onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); drag.current = i }}
              onPointerMove={(e) => {
                if (drag.current !== i) return
                const pt = toPlan(e)
                setForm((f) => f && { ...f, points: f.points.map((q, j) => (j === i ? pt : q)) })
              }}
              onPointerUp={() => { drag.current = null }} />
          ))}
        </SitePlan>
        <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>اختر منطقة لتعديلها، واسحب نقاطها البرتقالية لتغيير شكلها. الإحداثيات بوحدة بكسل المخطط ({site.data.plan_width}×{site.data.plan_height}).</p>
      </div>

      <aside className="stack">
        {form ? (
          <section className="panel">
            <div className="panel__head"><h2>{selected ? 'تعديل المنطقة' : 'منطقة جديدة'}</h2></div>
            <div className="panel__body stack">
              <label className="field"><span>الاسم</span><input className="input" value={form.name} maxLength={80} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
              <div className="field">
                <span>النوع</span>
                <div className="seg" role="group">
                  <button type="button" aria-pressed={form.kind === 'no_entry'} onClick={() => setForm({ ...form, kind: 'no_entry' })}>محظورة الدخول</button>
                  <button type="button" aria-pressed={form.kind === 'ppe'} onClick={() => setForm({ ...form, kind: 'ppe' })}>تشترط معدات وقاية</button>
                </div>
              </div>
              {form.kind === 'no_entry' && (
                <>
                  <label className="check"><input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} /><span><b>فعّالة الآن</b><small>أوقفها حين يزول الخطر، مثل نطاق الرافعة حين تتوقف.</small></span></label>
                  <label className="check"><input type="checkbox" checked={form.interlock} onChange={(e) => setForm({ ...form, interlock: e.target.checked })} /><span><b>إشارة لمشغّل المعدة</b><small>ترسل تنبيهًا لمشغّل المعدة القريبة (محاكاة حتى يُربط عتاد فعلي).</small></span></label>
                </>
              )}
              <label className="check"><input type="checkbox" checked={form.require_helmet} onChange={(e) => setForm({ ...form, require_helmet: e.target.checked })} /><span><b>تشترط الخوذة</b></span></label>
              <label className="check"><input type="checkbox" checked={form.require_vest} onChange={(e) => setForm({ ...form, require_vest: e.target.checked })} /><span><b>تشترط السترة العاكسة</b></span></label>
              <label className={`check ${canHarness ? '' : 'is-disabled'}`}><input type="checkbox" disabled={!canHarness} checked={form.require_harness} onChange={(e) => setForm({ ...form, require_harness: e.target.checked })} /><span><b>تشترط حزام الأمان</b><small>{canHarness ? 'للعمل على الحواف والارتفاعات.' : 'يحتاج نموذجًا مدرّبًا على حزام الأمان (بيانات التدريب قيد التجهيز).'}</small></span></label>
              <label className="check"><input type="checkbox" checked={form.outdoor} onChange={(e) => setForm({ ...form, outdoor: e.target.checked })} /><span><b>مكشوفة للشمس</b><small>تُرصد فيها مخالفات حظر العمل وقت الظهيرة، ويرتفع مؤشر خطرها مع الحرارة.</small></span></label>
              <div className="row-gap">
                <button type="button" className="btn btn--ink" onClick={save} disabled={busy}>{selected ? 'حفظ التعديلات' : 'حفظ المنطقة'}</button>
                {selected && <button type="button" className="btn btn--danger" onClick={remove}><IconTrash />حذف</button>}
                <button type="button" className="btn" onClick={() => select(null)}>إغلاق</button>
              </div>
            </div>
          </section>
        ) : (
          <section className="panel">
            <div className="panel__head"><h2>المناطق</h2><span className="aside">{zones.data.length}</span></div>
            <div className="panel__body">
              {zones.data.map((z) => (
                <button key={z.id} type="button" className="paper-alert" style={{ width: '100%', background: 'none', border: 0, borderBottom: '1px solid var(--line-faint)', cursor: 'pointer', textAlign: 'start' }} onClick={() => select(z)}>
                  <span className="state-dot" style={{ background: z.kind === 'ppe' ? '#9a8f00' : z.active ? '#dc2e26' : '#6b747a' }} />
                  <span style={{ fontWeight: 600 }}>{z.name}</span>
                  <span className="muted" style={{ marginInlineStart: 'auto', fontSize: 13 }}>{z.kind === 'ppe' ? 'معدات وقاية' : z.active ? 'محظورة' : 'متوقفة'}</span>
                </button>
              ))}
              {zones.data.length === 0 && <p className="muted">لا توجد مناطق بعد. اضغط «منطقة جديدة» وارسمها على المخطط.</p>}
            </div>
          </section>
        )}
      </aside>
      <Toast toast={toast} />
    </div>
  )
}
