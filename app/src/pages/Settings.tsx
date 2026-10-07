import { useEffect, useState } from 'react'
import { IconPlay, IconPlus, IconTrash } from '../components/Icons'
import { Toast } from '../components/Widgets'
import { api } from '../lib/api'
import { camCode, STATE_LABEL } from '../lib/format'
import { useApi, useToast } from '../lib/hooks'
import { useLive } from '../lib/live'
import type { RuntimeSettings } from '../lib/types'
import { voice } from '../lib/voice'

const NUM_FIELDS: { key: keyof RuntimeSettings; label: string; help: string; step: number }[] = [
  { key: 'enter_frames', label: 'إطارات تأكيد الدخول', help: 'عدد الإطارات المتتالية داخل المنطقة قبل التنبيه (يقلل الإنذار الكاذب).', step: 1 },
  { key: 'escalate_s', label: 'تصعيد البقاء (ث)', help: 'يتحول التنبيه إلى حرج إن بقي العامل داخل المنطقة هذه المدة.', step: 1 },
  { key: 'ppe_hold_s', label: 'مهلة معدات الوقاية (ث)', help: 'مدة غياب المعدّة قبل التنبيه.', step: 0.5 },
  { key: 'man_down_s', label: 'مهلة رصد السقوط (ث)', help: 'مدة بقاء العامل ساقطًا دون حركة قبل التنبيه.', step: 0.5 },
  { key: 'sos_hold_s', label: 'مدة إشارة الاستغاثة (ث)', help: 'مدة رفع الذراعين متقاطعتين المطلوبة.', step: 0.1 },
  { key: 'cooldown_s', label: 'فاصل التكرار (ث)', help: 'لا يتكرر التنبيه نفسه للعامل نفسه خلال هذه المدة.', step: 1 },
  { key: 'det_conf', label: 'حد ثقة معدات الوقاية', help: 'بين 0 و1. الأعلى يعني تنبيهات أقل وأدق.', step: 0.05 },
  { key: 'pose_conf', label: 'حد ثقة رصد الأشخاص', help: 'بين 0 و1.', step: 0.05 },
  { key: 'machine_gap', label: 'مسافة الاقتراب من المعدات', help: 'بوحدة طول العامل في الصورة: 1 تعني نحو 1.7 م. تقدير من الصورة، ويعمل حين يتعرّف نموذج الوقاية على المعدات.', step: 0.1 },
  { key: 'min_person_px', label: 'أدنى طول للعامل (بكسل)', help: 'لا يُحكم بغياب السترة على عامل أصغر من هذا في الصورة.', step: 5 },
]

/** S-08: cameras, alerts and voice, detection thresholds, privacy and the site. */
export function SettingsPage() {
  const cams = useApi(api.cameras)
  const site = useApi(api.site)
  const voices = useApi(api.voices)
  const { state } = useLive()
  const { toast, show } = useToast()
  const [rt, setRt] = useState<RuntimeSettings | null>(null)
  const [newCam, setNewCam] = useState({ name: '', source: '' })
  const [siteForm, setSiteForm] = useState({ name: '', lat: '', lon: '' })

  useEffect(() => { api.settings().then(setRt).catch((e) => show(e.message, 'err')) }, [show])
  useEffect(() => { if (site.data) setSiteForm({ name: site.data.name, lat: String(site.data.lat), lon: String(site.data.lon) }) }, [site.data])

  const saveRt = async () => {
    if (!rt) return
    try {
      const saved = await api.saveSettings(rt)
      setRt(saved)
      voice.languages = saved.voice_languages
      show('حُفظت الإعدادات وطُبّقت على الكاميرات')
    } catch (e) {
      show(e instanceof Error ? e.message : 'تعذّر الحفظ', 'err')
    }
  }

  const addCam = async () => {
    if (!newCam.name.trim() || !newCam.source.trim()) return show('أدخل اسم الكاميرا ومصدرها', 'err')
    try {
      await api.createCamera({ name: newCam.name.trim(), source: newCam.source.trim() })
      setNewCam({ name: '', source: '' })
      await cams.reload()
      show('أضيفت الكاميرا وبدأ تشغيلها')
    } catch (e) {
      show(e instanceof Error ? e.message : 'تعذّرت الإضافة', 'err')
    }
  }

  const toggleCam = async (id: number, enabled: boolean) => {
    try {
      await (enabled ? api.stopCamera(id) : api.startCamera(id))
      await cams.reload()
    } catch (e) {
      show(e instanceof Error ? e.message : 'تعذّر التنفيذ', 'err')
    }
  }

  const removeCam = async (id: number, name: string) => {
    if (!window.confirm(`حذف «${name}»؟ تبقى أحداثها في السجل.`)) return
    await api.deleteCamera(id)
    await cams.reload()
  }

  const saveSite = async () => {
    try {
      await api.updateSite({ name: siteForm.name, lat: Number(siteForm.lat), lon: Number(siteForm.lon) })
      await site.reload()
      show('حُفظت بيانات الموقع')
    } catch (e) {
      show(e instanceof Error ? e.message : 'تعذّر الحفظ', 'err')
    }
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="panel__head"><h2>الكاميرات</h2><span className="aside">{cams.data?.length ?? 0}</span></div>
        <div className="panel__body stack">
          <div className="table-scroll">
          <table className="schedule">
            <thead><tr><th>الرمز</th><th>الاسم</th><th>المصدر</th><th>الحالة</th><th>المعايرة</th><th /></tr></thead>
            <tbody>
              {cams.data?.map((c) => {
                const st = state.cameraStatus[c.id]?.state ?? c.status.state
                return (
                  <tr key={c.id}>
                    <td className="ltr nowrap">{camCode(c.id)}</td>
                    <td style={{ fontWeight: 600, minWidth: '9em' }}>{c.name}</td>
                    <td className="ltr" style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={c.source}>{c.source}</td>
                    <td className="nowrap">{c.enabled ? STATE_LABEL[st] ?? st : 'متوقفة'}</td>
                    <td className="nowrap">{c.calibrated ? <span title={`متوسط خطأ الإسقاط ${c.calib_error_px ?? 0} بكسل`}>معايَرة</span> : <span className="muted">غير معايَرة</span>}</td>
                    <td>
                      <div className="row-gap" style={{ flexWrap: 'nowrap' }}>
                        <button type="button" className="btn btn--sm" onClick={() => void toggleCam(c.id, c.enabled)}>{c.enabled ? 'إيقاف' : 'تشغيل'}</button>
                        <button type="button" className="btn btn--sm btn--icon btn--danger" aria-label={`حذف ${c.name}`} onClick={() => void removeCam(c.id, c.name)}><IconTrash /></button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          </div>
          <div className="row-gap" style={{ alignItems: 'flex-end' }}>
            <label className="field" style={{ width: 220 }}><span>اسم الكاميرا</span><input className="input" value={newCam.name} onChange={(e) => setNewCam({ ...newCam, name: e.target.value })} placeholder="مثال: البوابة الشمالية" /></label>
            <label className="field" style={{ flex: 1, minWidth: 280 }}><span>المصدر</span><input className="input ltr" style={{ width: '100%' }} value={newCam.source} onChange={(e) => setNewCam({ ...newCam, source: e.target.value })} placeholder="rtsp://… أو http://… أو 0 لكاميرا الحاسب" /></label>
            <button type="button" className="btn btn--ink" onClick={addCam}><IconPlus />إضافة</button>
          </div>
          <p className="muted" style={{ fontSize: 13 }}>يقبل المصدر: رابط RTSP لكاميرا شبكية، أو رابط بث HTTP من تطبيق كاميرا على الجوال، أو رقم كاميرا الحاسب (0)، أو ملف فيديو. بعد الإضافة عايِر الكاميرا من صفحة «معايرة الكاميرات».</p>
        </div>
      </section>

      {rt && (
        <div className="cols-2">
          <section className="panel">
            <div className="panel__head"><h2>التنبيه الصوتي والخصوصية</h2></div>
            <div className="panel__body stack">
              <div className="field">
                <span>لغات التنبيه على مكبر الموقع</span>
                <div className="stack" style={{ gap: 4 }}>
                  {(voices.data?.languages ?? []).map((l) => (
                    <div key={l.code} className="row-gap">
                      <label className="check" style={{ flex: 1 }}>
                        <input type="checkbox" checked={rt.voice_languages.includes(l.code)} onChange={(e) => setRt({ ...rt, voice_languages: e.target.checked ? [...rt.voice_languages, l.code] : rt.voice_languages.filter((x) => x !== l.code) })} />
                        <span><b>{l.name}</b><small><bdi>{voices.data?.phrases.zone?.[l.code]?.text}</bdi></small></span>
                      </label>
                      <button type="button" className="btn btn--sm btn--icon" aria-label={`استماع: ${l.name}`} disabled={!voices.data?.phrases.zone?.[l.code]?.available} onClick={() => voice.preview('zone', l.code)}><IconPlay /></button>
                    </div>
                  ))}
                </div>
                <small>✍️ تحتاج عبارات الأردية والهندية والبنغالية مراجعة من متحدث أصلي قبل الاستخدام الفعلي.</small>
              </div>
              <label className="check"><input type="checkbox" checked={rt.blur_stream} onChange={(e) => setRt({ ...rt, blur_stream: e.target.checked })} /><span><b>تمويه الوجوه في البث المباشر</b><small>اللقطات المحفوظة مموّهة دائمًا. أوقفه فقط إن احتاج المشرف تمييز الحالة.</small></span></label>
              <label className="check"><input type="checkbox" checked={rt.site_require_helmet} onChange={(e) => setRt({ ...rt, site_require_helmet: e.target.checked })} /><span><b>الخوذة إلزامية في كامل الموقع</b></span></label>
              <label className="check"><input type="checkbox" checked={rt.site_require_vest} onChange={(e) => setRt({ ...rt, site_require_vest: e.target.checked })} /><span><b>السترة العاكسة إلزامية في كامل الموقع</b></span></label>
            </div>
          </section>

          <section className="panel">
            <div className="panel__head"><h2>حساسية الرصد</h2></div>
            <div className="panel__body">
              <div className="form-grid">
                {NUM_FIELDS.map((f) => (
                  <label key={f.key} className="field">
                    <span>{f.label}</span>
                    <input className="input ltr" type="number" step={f.step} value={rt[f.key] as number} onChange={(e) => setRt({ ...rt, [f.key]: Number(e.target.value) })} />
                    <small>{f.help}</small>
                  </label>
                ))}
              </div>
            </div>
          </section>
        </div>
      )}
      <div className="row-gap"><button type="button" className="btn btn--ink" onClick={saveRt} disabled={!rt}>حفظ الإعدادات</button></div>

      <section className="panel">
        <div className="panel__head"><h2>الموقع</h2></div>
        <div className="panel__body row-gap" style={{ alignItems: 'flex-end' }}>
          <label className="field" style={{ width: 280 }}><span>اسم الموقع</span><input className="input" value={siteForm.name} onChange={(e) => setSiteForm({ ...siteForm, name: e.target.value })} /></label>
          <label className="field" style={{ width: 140 }}><span>خط العرض</span><input className="input ltr" value={siteForm.lat} onChange={(e) => setSiteForm({ ...siteForm, lat: e.target.value })} /></label>
          <label className="field" style={{ width: 140 }}><span>خط الطول</span><input className="input ltr" value={siteForm.lon} onChange={(e) => setSiteForm({ ...siteForm, lon: e.target.value })} /></label>
          <button type="button" className="btn" onClick={saveSite}>حفظ</button>
          <span className="muted" style={{ fontSize: 13 }}>الإحداثيات تحدد قراءة الطقس لمؤشر الحرارة.</span>
        </div>
      </section>
      <Toast toast={toast} />
    </div>
  )
}
